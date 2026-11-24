"""
Serviço de classificação de sentimento com modelo Hugging Face executado LOCALMENTE.

Decisões de projeto (detalhes em Docs/Project/LLM_Model_Selection.md e Decision_Log.md):
  * Carga preguiçosa (lazy) e protegida por lock: a API sobe rápido e as demais rotas funcionam
    mesmo sem torch/transformers instalados.
  * Offline por padrão: nenhuma requisição dispara download; o modelo é baixado uma vez por
    `python Code/llm/baixar_modelo.py` e depois tudo roda sem internet.
  * Inferência em thread única com timeout e limite de requisições pendentes (máquina modesta).
  * Toda saída do modelo é validada (rótulos conhecidos, probabilidades em [0,1] somando ~1).
  * O "carregador" é injetável: nos testes usamos um pipeline falso, sem baixar nada.
"""
from __future__ import annotations

import importlib.util
import logging
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoTimeout
from datetime import datetime
from typing import Callable, Optional, Sequence

from .config import ConfigLLM, carregar_config
from .errors import (ErroLLM, FalhaInferenciaError, ModeloIndisponivelError, ModeloOcupadoError,
                     TempoLimiteError, TextoInvalidoError)

log = logging.getLogger("esg.llm")

TIPO_ANALISE = "classificacao_sentimento"
ROTULOS = ("positivo", "neutro", "negativo")
_MAPA_ROTULOS = {"positive": "positivo", "positivo": "positivo", "neutral": "neutro", "neutro": "neutro",
                 "negative": "negativo", "negativo": "negativo"}


# ---------------------------------------------------------------- utilidades puras (testáveis)
def normalizar_texto(texto: str) -> str:
    """Colapsa espaços/quebras de linha: 'a \\n  b' -> 'a b'."""
    return " ".join(str(texto).split())


def dependencias_instaladas() -> bool:
    return all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers"))


def cache_presente(cfg: ConfigLLM) -> bool:
    return (cfg.pasta_cache / ("models--" + cfg.modelo_id.replace("/", "--"))).is_dir()


def normalizar_saida_pipeline(saida, n: int) -> list:
    """
    Uniformiza o retorno do pipeline para `lista (1 por texto) de listas de {label, score}`.
    O formato varia entre versões do transformers (dict, lista de dicts ou lista de listas).
    """
    if isinstance(saida, dict):
        saida = [[saida]]
    elif isinstance(saida, (list, tuple)) and saida and isinstance(saida[0], dict):
        saida = [list(saida)] if n == 1 else [[d] for d in saida]
    if not isinstance(saida, (list, tuple)) or len(saida) != n:
        raise FalhaInferenciaError(
            f"O modelo devolveu {len(saida) if hasattr(saida, '__len__') else '?'} resultado(s) para {n} texto(s).")
    return [list(item) for item in saida]


def converter_scores(itens: list) -> dict:
    """[{'label','score'}, ...] -> {rotulo, confianca, probabilidades{positivo,neutro,negativo}} (validado)."""
    prob: dict = {}
    for it in itens:
        try:
            rotulo = _MAPA_ROTULOS[str(it["label"]).strip().lower()]
            score = float(it["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise FalhaInferenciaError(
                f"Saída inesperada do modelo: {it!r}",
                sugestao="Confirme que ESG_LLM_MODEL é um modelo de sentimento com rótulos positive/neutral/negative.") from exc
        if math.isnan(score) or not 0.0 <= score <= 1.0:
            raise FalhaInferenciaError(f"Probabilidade inválida devolvida pelo modelo: {score!r}")
        prob[rotulo] = score
    if set(prob) != set(ROTULOS):
        raise FalhaInferenciaError(f"O modelo não devolveu os três rótulos esperados (recebidos: {sorted(prob)}).")
    soma = sum(prob.values())
    if not 0.98 <= soma <= 1.02:
        raise FalhaInferenciaError(f"As probabilidades somam {soma:.3f}, e não 1.")
    prob = {r: round(prob[r] / soma, 4) for r in ROTULOS}
    melhor = max(ROTULOS, key=lambda r: prob[r])
    return {"rotulo": melhor, "confianca": prob[melhor], "probabilidades": prob}


# ---------------------------------------------------------------- carregador real (Hugging Face)
def _carregar_pipeline_hf(cfg: ConfigLLM):
    """Carrega tokenizador + modelo do cache local e devolve um pipeline de classificação de texto."""
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch  # noqa: WPS433  (importação tardia: dependência opcional e pesada)
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

    if cfg.threads:
        torch.set_num_threads(cfg.threads)
    dispositivo = -1
    if cfg.dispositivo in ("cuda", "auto") and torch.cuda.is_available():
        dispositivo = 0
    cfg.pasta_cache.mkdir(parents=True, exist_ok=True)
    comuns = dict(cache_dir=str(cfg.pasta_cache), local_files_only=cfg.offline)
    if cfg.revisao:
        comuns["revision"] = cfg.revisao
    tokenizador = AutoTokenizer.from_pretrained(cfg.modelo_id, **comuns)
    modelo = AutoModelForSequenceClassification.from_pretrained(cfg.modelo_id, **comuns)
    modelo.eval()
    return pipeline("text-classification", model=modelo, tokenizer=tokenizador, device=dispositivo)


# ---------------------------------------------------------------- serviço
class ServicoSentimento:
    def __init__(self, config: Optional[ConfigLLM] = None,
                 carregador: Optional[Callable[[ConfigLLM], Callable]] = None,
                 relogio: Callable[[], float] = time.monotonic):
        self._cfg = config or carregar_config()
        self._carregador = carregador or _carregar_pipeline_hf
        self._relogio = relogio
        self._pipe = None
        self._lock_carga = threading.Lock()
        self._lock_contadores = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="esg-llm")
        self._pendentes = threading.BoundedSemaphore(self._cfg.max_pendentes)
        self._dispositivo: Optional[str] = None
        self._tempo_carga_s: Optional[float] = None
        self._carregado_em: Optional[str] = None
        self._ultimo_erro: Optional[str] = None
        self._ultima_falha_ts: Optional[float] = None
        self._requisicoes = 0
        self._erros = 0

    @property
    def config(self) -> ConfigLLM:
        return self._cfg

    # ------------------------------------------------------------ estado
    def esta_carregado(self) -> bool:
        return self._pipe is not None

    def status(self) -> dict:
        c = self._cfg
        return {
            "modelo_id": c.modelo_id, "revisao": c.revisao, "carregado": self.esta_carregado(),
            "dependencias_instaladas": dependencias_instaladas(),
            "dispositivo": self._dispositivo or c.dispositivo, "offline": c.offline,
            "pasta_cache": str(c.pasta_cache), "cache_presente": cache_presente(c),
            "tempo_carga_s": self._tempo_carga_s, "carregado_em": self._carregado_em,
            "ultimo_erro": self._ultimo_erro,
            "total_requisicoes": self._requisicoes, "total_erros": self._erros,
            "limites": {"max_caracteres": c.max_caracteres, "max_tokens": c.max_tokens, "max_lote": c.max_lote,
                        "timeout_s": c.timeout_s, "max_pendentes": c.max_pendentes},
        }

    def _incrementar(self, campo: str) -> None:
        with self._lock_contadores:
            setattr(self, campo, getattr(self, campo) + 1)

    # ------------------------------------------------------------ carga do modelo
    def _sugestao_carga(self) -> str:
        if not dependencias_instaladas():
            return "Instale as dependências: pip install -r requirements-llm.txt"
        if self._cfg.offline and not cache_presente(self._cfg):
            return ("O modelo ainda não foi baixado. Execute uma vez: python Code/llm/baixar_modelo.py "
                    "(ou defina ESG_LLM_OFFLINE=0 para permitir o download automático).")
        return "Verifique memória/disco disponíveis e os logs da API. Diagnóstico: python Code/llm/verificar_modelo.py"

    def _registrar_falha(self, mensagem: str) -> None:
        self._ultimo_erro = mensagem
        self._ultima_falha_ts = self._relogio()
        log.error("Falha ao carregar o modelo: %s", mensagem)

    def carregar(self, forcar: bool = False) -> None:
        """Carrega o modelo (idempotente). Levanta ModeloIndisponivelError se não for possível."""
        if self._pipe is not None and not forcar:
            return
        with self._lock_carga:
            if self._pipe is not None and not forcar:
                return
            if not forcar and self._ultima_falha_ts is not None:
                decorrido = self._relogio() - self._ultima_falha_ts
                if decorrido < self._cfg.cooldown_falha_s:
                    raise ModeloIndisponivelError(
                        f"O modelo está indisponível: {self._ultimo_erro}",
                        sugestao=self._sugestao_carga(),
                        retry_after=int(self._cfg.cooldown_falha_s - decorrido) + 1)
            inicio = time.perf_counter()
            try:
                pipe = self._carregador(self._cfg)
            except ErroLLM as exc:
                self._registrar_falha(exc.mensagem)
                raise
            except ImportError as exc:
                msg = f"Dependências de IA ausentes ({exc})."
                self._registrar_falha(msg)
                raise ModeloIndisponivelError(msg, sugestao=self._sugestao_carga()) from exc
            except Exception as exc:  # noqa: BLE001  (OSError, ValueError, RuntimeError, MemoryError...)
                msg = f"Falha ao carregar o modelo '{self._cfg.modelo_id}': {type(exc).__name__}: {exc}"
                self._registrar_falha(msg)
                raise ModeloIndisponivelError(msg, sugestao=self._sugestao_carga()) from exc
            self._pipe = pipe
            self._dispositivo = str(getattr(pipe, "device", None) or "cpu")
            self._tempo_carga_s = round(time.perf_counter() - inicio, 2)
            self._carregado_em = datetime.now().isoformat(timespec="seconds")
            self._ultimo_erro = None
            self._ultima_falha_ts = None
            log.info("Modelo '%s' carregado em %.2fs (%s).", self._cfg.modelo_id, self._tempo_carga_s, self._dispositivo)

    # ------------------------------------------------------------ validação de entrada
    def _validar(self, texto, campo: str = "texto") -> str:
        det = [{"campo": campo, "problema": ""}]
        if not isinstance(texto, str):
            det[0]["problema"] = "deve ser texto (string)"
            raise TextoInvalidoError("O texto enviado não é uma string.", detalhes=det)
        limpo = normalizar_texto(texto)
        if not limpo:
            det[0]["problema"] = "vazio"
            raise TextoInvalidoError("O texto está vazio.", detalhes=det, sugestao="Envie ao menos uma frase.")
        if not any(ch.isalpha() for ch in limpo):
            det[0]["problema"] = "sem letras"
            raise TextoInvalidoError("O texto não contém letras para analisar.", detalhes=det)
        if len(limpo) > self._cfg.max_caracteres:
            det[0]["problema"] = f"{len(limpo)} caracteres (máximo {self._cfg.max_caracteres})"
            raise TextoInvalidoError(
                f"O texto tem {len(limpo)} caracteres; o máximo aceito é {self._cfg.max_caracteres}.", detalhes=det,
                sugestao="Divida o texto em trechos menores ou resuma-o antes de analisar.")
        return limpo

    # ------------------------------------------------------------ inferência
    def _inferir(self, textos: list) -> tuple:
        t0 = time.perf_counter()
        saida = self._pipe(textos, top_k=None, truncation=True, max_length=self._cfg.max_tokens,
                           batch_size=self._cfg.batch_size)
        return saida, (time.perf_counter() - t0) * 1000.0

    def _contar_tokens(self, textos: list) -> list:
        tok = getattr(self._pipe, "tokenizer", None)
        if tok is None:
            return [None] * len(textos)
        try:
            return [len(tok(t, add_special_tokens=True)["input_ids"]) for t in textos]
        except Exception:  # noqa: BLE001  (metadado opcional: nunca derruba a requisição)
            return [None] * len(textos)

    def _analisar_lote(self, textos: Sequence) -> list:
        if not textos:
            raise TextoInvalidoError("Envie ao menos um texto.")
        if len(textos) > self._cfg.max_lote:
            raise TextoInvalidoError(
                f"Máximo de {self._cfg.max_lote} textos por requisição (recebidos {len(textos)}).",
                sugestao="Divida a lista em lotes menores.")
        limpos = [self._validar(t, f"textos[{i}]" if len(textos) > 1 else "texto") for i, t in enumerate(textos)]

        self.carregar()

        if not self._pendentes.acquire(blocking=False):
            raise ModeloOcupadoError("O modelo está ocupado com outras requisições.",
                                     sugestao="Aguarde alguns segundos e tente novamente.", retry_after=5)
        try:
            futuro = self._executor.submit(self._inferir, limpos)
        except Exception:
            self._pendentes.release()
            raise
        futuro.add_done_callback(lambda _f: self._pendentes.release())   # libera mesmo se der timeout

        try:
            bruto, ms_total = futuro.result(timeout=self._cfg.timeout_s)
        except FuturoTimeout:
            futuro.cancel()
            raise TempoLimiteError(
                f"A análise excedeu o limite de {self._cfg.timeout_s:g} s.",
                sugestao="Envie textos menores, reduza o tamanho do lote ou aumente ESG_LLM_TIMEOUT.",
                retry_after=5) from None
        except ErroLLM:
            raise
        except Exception as exc:  # noqa: BLE001
            raise FalhaInferenciaError(
                f"Erro durante a inferência: {type(exc).__name__}: {exc}",
                sugestao="Tente textos menores. Se persistir, rode: python Code/llm/verificar_modelo.py") from exc

        conv = [converter_scores(item) for item in normalizar_saida_pipeline(bruto, len(limpos))]
        tokens = self._contar_tokens(limpos)
        agora = datetime.now().isoformat(timespec="seconds")
        modelo = {"id": self._cfg.modelo_id, "dispositivo": self._dispositivo or self._cfg.dispositivo,
                  "revisao": self._cfg.revisao}
        resultados = []
        for original, limpo, c, nt in zip(textos, limpos, conv, tokens):
            resultados.append({
                "texto_original": original, "texto_processado": limpo, "tipo_analise": TIPO_ANALISE,
                "resultado": c, "modelo": modelo,
                "metadados": {"tempo_inferencia_ms": round(ms_total / len(limpos), 2), "n_caracteres": len(limpo),
                              "n_tokens": nt, "truncado": bool(nt is not None and nt > self._cfg.max_tokens),
                              "processado_em": agora},
            })
        return resultados

    def analisar_lote(self, textos: Sequence) -> list:
        self._incrementar("_requisicoes")
        try:
            return self._analisar_lote(textos)
        except ErroLLM:
            self._incrementar("_erros")
            raise
        except Exception as exc:  # noqa: BLE001
            self._incrementar("_erros")
            raise FalhaInferenciaError(f"Erro inesperado: {type(exc).__name__}: {exc}") from exc

    def analisar(self, texto: str) -> dict:
        return self.analisar_lote([texto])[0]


# ---------------------------------------------------------------- instância compartilhada
_SERVICO: Optional[ServicoSentimento] = None
_LOCK_SERVICO = threading.Lock()


def obter_servico() -> ServicoSentimento:
    global _SERVICO
    if _SERVICO is None:
        with _LOCK_SERVICO:
            if _SERVICO is None:
                _SERVICO = ServicoSentimento()
    return _SERVICO


def definir_servico(servico: Optional[ServicoSentimento]) -> None:
    """Troca a instância compartilhada (usado em testes)."""
    global _SERVICO
    with _LOCK_SERVICO:
        _SERVICO = servico
