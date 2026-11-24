"""
Orquestrador da IA online: escolhe provedor, aplica limite de custo, usa cache, registra auditoria e chama os casos de uso
(sumarização de texto e de corpus, perguntas e respostas, insights de emissões). Sem dependência de FastAPI.
"""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Callable, Optional

import pandas as pd

from .. import corpus as corpus_mod
from .. import data_access as da
from .. import paths
from ..previsao import prever_emissoes
from . import insights as insights_mod
from . import qa as qa_mod
from . import sumarizacao as sum_mod
from .config import PROVEDORES, ConfigIA, carregar_config_ia
from .controle import AuditoriaIA, CacheIA, ClienteMedido, LimiteUso
from .errors import DadosIndisponiveisError, TextoInvalidoError
from .prompts import OBJETIVO_PADRAO, VERSAO_INSIGHTS, VERSAO_QA, VERSAO_SUMARIO, VERSOES_SUMARIO
from .provedores import criar_cliente


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:24]


class ServicoIA:
    def __init__(self, config: Optional[ConfigIA] = None, fabrica: Optional[Callable] = None, cache: Optional[CacheIA] = None,
                 auditoria: Optional[AuditoriaIA] = None, limite: Optional[LimiteUso] = None):
        self.cfg = config or carregar_config_ia()
        self._fabrica = fabrica or (lambda cfg, prov: criar_cliente(cfg, prov))
        self._cache = cache or CacheIA(paths.caminho_ia_cache_dir(), self.cfg.cache_ativo)
        self._auditoria = auditoria or AuditoriaIA(paths.caminho_ia_dir() / "historico.jsonl")
        self._limite = limite or LimiteUso(self.cfg.max_chamadas_hora)

    # ------------------------------------------------------------ estado
    def status(self) -> dict:
        c = self.cfg
        provs = [{"nome": p, "configurado": c.configurado(p), "modelo": c.modelo(p),
                  "url_personalizada": p == "openai" and c.openai_local()} for p in PROVEDORES]
        return {"provedor_padrao": c.provedor_efetivo(), "provedores": provs, "algum_configurado": any(p["configurado"] for p in provs),
                "cache_ativo": c.cache_ativo, "chamadas_ultima_hora": self._limite.usadas(),
                "limites": {"max_chars_entrada": c.max_chars_entrada, "max_chamadas_hora": c.max_chamadas_hora, "max_docs": c.max_docs,
                            "max_tokens": c.max_tokens, "timeout_s": c.timeout_s},
                "versoes_prompt": {"sumario": VERSAO_SUMARIO, "perguntas": VERSAO_QA, "insights": VERSAO_INSIGHTS}}

    def historico(self, limite: int = 50) -> list:
        return self._auditoria.ler(limite)

    # ------------------------------------------------------------ núcleo
    def _executar(self, tipo: str, provedor: Optional[str], partes: list, funcao: Callable, n_chars: int, usar_cache: bool = True) -> dict:
        c = self.cfg
        prov = c.provedor_efetivo(provedor)
        if prov not in PROVEDORES:
            raise TextoInvalidoError(f"Provedor desconhecido: {prov!r}.", sugestao="Use 'openai' ou 'anthropic'.")
        chave = CacheIA.chave(tipo, prov, c.modelo(prov), *partes)
        if usar_cache:
            hit = self._cache.obter(chave)
            if hit is not None:
                hit["cache"] = True
                self._registrar(tipo, hit, n_chars)
                return hit
        cliente = ClienteMedido(self._fabrica(c, prov), self._limite)
        resultado = funcao(cliente)
        resultado["cache"] = False
        if (resultado.get("fidelidade") or {}).get("ok", True):          # não congela uma saída com números suspeitos
            self._cache.salvar(chave, resultado)
        self._registrar(tipo, resultado, n_chars)
        return resultado

    def _registrar(self, tipo: str, r: dict, n_chars: int) -> None:
        saida = ((r.get("resumo") or {}).get("resumo_executivo") or r.get("resposta")
                 or ((r.get("insights") or {}).get("destaques") or [{}])[0].get("titulo") or "")
        self._auditoria.registrar({
            "tipo": tipo, "provedor": r.get("provedor"), "modelo": r.get("modelo"), "versao_prompt": r.get("versao_prompt"),
            "cache": r.get("cache"), "n_chamadas": r.get("n_chamadas"), "tokens_entrada": r.get("tokens_entrada"),
            "tokens_saida": r.get("tokens_saida"), "fidelidade_ok": (r.get("fidelidade") or {}).get("ok"),
            "n_caracteres_entrada": n_chars, "saida": str(saida)[:600]})

    def _versao(self, v: Optional[str]) -> str:
        v = v or VERSAO_SUMARIO
        if v not in VERSOES_SUMARIO:
            raise TextoInvalidoError(f"Versão de prompt desconhecida: {v!r}.", sugestao=f"Opções: {', '.join(VERSOES_SUMARIO)}.")
        return v

    # ------------------------------------------------------------ casos de uso
    def sumarizar_texto(self, texto: str, objetivo: Optional[str] = None, nivel: str = "executivo", titulo: Optional[str] = None,
                        provedor: Optional[str] = None, versao_prompt: Optional[str] = None, usar_cache: bool = True) -> dict:
        t = (texto or "").strip()
        if len(t) < 50:
            raise TextoInvalidoError("O texto é curto demais para resumir (mínimo de 50 caracteres).", sugestao="Envie o trecho ou relatório completo.")
        if len(t) > self.cfg.max_chars_entrada:
            raise TextoInvalidoError(f"O texto tem {len(t)} caracteres; o máximo aceito é {self.cfg.max_chars_entrada}.",
                                     sugestao="Divida o documento em partes ou aumente ESG_IA_MAX_CHARS.")
        v, obj = self._versao(versao_prompt), objetivo or OBJETIVO_PADRAO
        return self._executar("sumario_texto", provedor, [_sha(t), obj, nivel, v], lambda cli: sum_mod.sumarizar_texto(
            cli, t, obj, nivel, titulo or "Texto enviado", versao=v, max_tokens=self.cfg.max_tokens), len(t), usar_cache)

    def _selecionar_corpus(self, tipo, tag, doc_ids, limite) -> list:
        docs = da.carregar_corpus()
        if not docs:
            raise DadosIndisponiveisError("O corpus de documentos ainda não foi gerado.", sugestao="Execute: python Code/data_preparation/build_corpus.py")
        if tipo:
            docs = [d for d in docs if d["tipo"] == tipo]
        if tag:
            docs = [d for d in docs if tag.lower() in [t.lower() for t in d.get("tags", [])]]
        if doc_ids:
            docs = [d for d in docs if d["doc_id"] in set(doc_ids)]
        if not docs:
            raise DadosIndisponiveisError("Nenhum documento atende aos filtros informados.", sugestao="Relaxe os filtros (tipo, tag ou ids).")
        docs = sorted(docs, key=lambda d: d.get("data_publicacao") or "", reverse=True)
        return docs[: max(1, min(limite or 15, self.cfg.max_docs))]

    def sumarizar_corpus(self, tipo: Optional[str] = None, tag: Optional[str] = None, doc_ids: Optional[list] = None, limite: Optional[int] = None,
                         objetivo: Optional[str] = None, nivel: str = "executivo", provedor: Optional[str] = None,
                         versao_prompt: Optional[str] = None, usar_cache: bool = True) -> dict:
        docs = self._selecionar_corpus(tipo, tag, doc_ids, limite)
        entrada = [{"doc_id": d["doc_id"], "titulo": d.get("titulo"), "fonte": d.get("fonte"), "url": d.get("url"),
                    "data": d.get("data_publicacao"), "texto": d["texto"]} for d in docs]
        v, obj = self._versao(versao_prompt), objetivo or OBJETIVO_PADRAO
        n = sum(len(d["texto"]) for d in entrada)
        return self._executar("sumario_corpus", provedor, [",".join(d["doc_id"] for d in docs), obj, nivel, v], lambda cli: sum_mod.sumarizar_documentos(
            cli, entrada, obj, nivel, v, max_tokens=self.cfg.max_tokens), n, usar_cache)

    def _contexto_emissoes(self):
        df = da.carregar_emissoes()
        if df.empty:
            return None, None
        ctx = corpus_mod.construir_contexto_relatorio(df)
        return ctx, insights_mod.renderizar_contexto_emissoes(ctx)

    def perguntar(self, pergunta: str, k: int = 5, provedor: Optional[str] = None, incluir_emissoes: bool = True, usar_cache: bool = True) -> dict:
        docs = [{"doc_id": d["doc_id"], "titulo": d.get("titulo"), "texto": d["texto"], "fonte": d.get("fonte"), "url": d.get("url"),
                 "data": d.get("data_publicacao")} for d in da.carregar_corpus()]
        texto_emis = ""
        if incluir_emissoes:
            _, texto_emis = self._contexto_emissoes()
            if texto_emis:
                docs.append({"doc_id": "EMISSOES", "titulo": "Emissões da empresa (dados agregados)", "texto": texto_emis, "fonte": "base do projeto"})
        if not docs:
            raise DadosIndisponiveisError("Não há documentos nem dados de emissões para consultar.", sugestao="Gere o corpus e a amostra de emissões.")
        p = (pergunta or "").strip()
        base_ids = _sha(",".join(d["doc_id"] for d in docs) + texto_emis)
        k = max(1, min(int(k or 5), 10))
        return self._executar("pergunta", provedor, [p.lower(), k, base_ids, VERSAO_QA], lambda cli: qa_mod.responder(
            cli, p, docs, k, self.cfg.max_tokens), len(p), usar_cache)

    def insights_emissoes(self, foco: Optional[str] = None, incluir_previsao: bool = True, incluir_noticias: bool = False,
                          provedor: Optional[str] = None, usar_cache: bool = True) -> dict:
        ctx, texto = self._contexto_emissoes()
        if ctx is None:
            raise DadosIndisponiveisError("Não há dados de emissões para analisar.", sugestao="Gere a amostra: python Code/data_acquisition/generate_sample_emissions.py")
        previsao, avisos = None, []
        if incluir_previsao:
            try:
                previsao = prever_emissoes(da.carregar_emissoes())
            except ValueError as exc:
                avisos.append(f"Previsão não incluída: {exc}")
        sentimento = self._contagem_sentimento()
        resumo_not = None
        if incluir_noticias:
            try:
                s = self.sumarizar_corpus(tipo="noticia", limite=15, provedor=provedor, usar_cache=usar_cache)["resumo"]
                resumo_not = s["resumo_executivo"] + " " + " ".join(s["pontos_chave"])
            except DadosIndisponiveisError as exc:
                avisos.append(f"Notícias não incluídas: {exc.mensagem}")
        chave = [_sha(texto), foco or "", _sha(str(previsao and previsao["previsoes"])), str(sentimento), _sha(resumo_not or ""), VERSAO_INSIGHTS]
        r = self._executar("insights_emissoes", provedor, chave, lambda cli: insights_mod.gerar_insights(
            cli, ctx, foco, previsao, sentimento, resumo_not, self.cfg.max_tokens), len(texto), usar_cache)
        r["avisos"] = avisos
        return r

    @staticmethod
    def _contagem_sentimento() -> Optional[dict]:
        caminho = paths.processed_dir() / "sentimento_noticias.csv"
        if not caminho.is_file():
            return None
        try:
            c = pd.read_csv(caminho)["rotulo_previsto"].value_counts()
        except (ValueError, KeyError, pd.errors.EmptyDataError):
            return None
        return {r: int(c.get(r, 0)) for r in ("positivo", "neutro", "negativo")} if len(c) else None


_SERVICO: Optional[ServicoIA] = None
_LOCK = threading.Lock()


def obter_servico_ia() -> ServicoIA:
    global _SERVICO
    if _SERVICO is None:
        with _LOCK:
            if _SERVICO is None:
                _SERVICO = ServicoIA()
    return _SERVICO


def definir_servico_ia(s: Optional[ServicoIA]) -> None:
    global _SERVICO
    with _LOCK:
        _SERVICO = s
