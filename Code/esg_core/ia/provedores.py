"""
Clientes HTTP para APIs de IA online (OpenAI Chat Completions e Anthropic Messages), sem SDKs.

Por que HTTP puro: menos dependências, comportamento explícito e fácil de testar com respostas simuladas.
Cuidados implementados (todos cobertos por testes):
  * retentativas com espera (respeita Retry-After) só para erros transitórios: timeout, rede, 429 de taxa e 5xx;
  * erros definitivos viram exceções específicas (credencial inválida, sem cota, modelo inexistente...);
  * compatibilidade entre modelos: envia `max_completion_tokens` e só envia `temperature` se configurada;
    se o modelo recusar um parâmetro (400), ele é ajustado/removido e a chamada é refeita;
  * chaves nunca aparecem em mensagens de erro (redação de segredos).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from .config import PROVEDORES, ConfigIA
from .errors import (IACotaError, IACredencialError, IALimiteTaxaError, IANaoConfiguradaError, IAProvedorError,
                     IARespostaInvalidaError, IATempoLimiteError, TextoInvalidoError)
from ..llm.errors import ErroLLM

log = logging.getLogger("esg.ia")
_SEGREDOS = re.compile(r"(sk-[A-Za-z0-9_\-.]{6,}|Bearer\s+[A-Za-z0-9_\-.]{8,})")


def redigir_segredos(texto) -> str:
    return _SEGREDOS.sub("***", str(texto))


@dataclass
class RespostaLLM:
    texto: str
    provedor: str
    modelo: str
    tokens_entrada: Optional[int] = None
    tokens_saida: Optional[int] = None
    motivo_fim: Optional[str] = None          # "stop"/"end_turn" = normal; "length"/"max_tokens" = truncada
    tentativas: int = 1
    latencia_ms: float = 0.0

    @property
    def truncada(self) -> bool:
        return self.motivo_fim in ("length", "max_tokens")


def _retry_after(resp) -> Optional[float]:
    try:
        v = float(resp.headers.get("retry-after") or resp.headers.get("Retry-After"))
        return min(max(v, 0.0), 60.0)
    except (TypeError, ValueError, AttributeError):
        return None


class _ClienteBase:
    provedor = ""

    def __init__(self, cfg: ConfigIA, http=None, dormir: Callable[[float], None] = time.sleep):
        self.cfg, self._http, self._dormir = cfg, http or requests, dormir

    @property
    def modelo(self) -> str:
        return self.cfg.modelo(self.provedor)

    def _adaptar(self, corpo: dict, msg_baixo: str) -> bool:        # sobrescrito pelos clientes
        return False

    def _mensagem_erro(self, resp) -> tuple:
        try:
            j = resp.json()
        except Exception:  # noqa: BLE001
            j = None
        msg, cod = "", ""
        if isinstance(j, dict):
            err = j.get("error")
            if isinstance(err, dict):
                msg, cod = str(err.get("message") or ""), str(err.get("code") or err.get("type") or "")
            elif isinstance(err, str):
                msg = err
        if not msg:
            msg = (getattr(resp, "text", "") or "")[:300]
        return redigir_segredos(msg), cod

    def _enviar(self, url: str, headers: dict, corpo: dict) -> tuple:
        """POST com retentativas. Devolve (json, tentativas, latencia_ms)."""
        tentativas, adaptacoes, inicio = 0, 0, time.perf_counter()
        max_tent = 1 + self.cfg.retentativas
        while True:
            tentativas += 1
            espera, erro = None, None
            try:
                resp = self._http.post(url, headers=headers, json=corpo, timeout=self.cfg.timeout_s)
            except requests.exceptions.Timeout:
                erro = IATempoLimiteError(f"O provedor ({self.provedor}) não respondeu em {self.cfg.timeout_s:g} s.",
                                          sugestao="Tente de novo, reduza o texto ou aumente ESG_IA_TIMEOUT.")
            except requests.exceptions.RequestException as exc:
                erro = IAProvedorError(f"Falha de rede ao falar com o provedor ({self.provedor}): {type(exc).__name__}.",
                                       sugestao="Verifique a conexão com a internet e a URL base configurada.")
            else:
                status = resp.status_code
                if 200 <= status < 300:
                    try:
                        return resp.json(), tentativas, (time.perf_counter() - inicio) * 1000.0
                    except ValueError:
                        raise IARespostaInvalidaError("O provedor devolveu uma resposta que não é JSON.") from None
                msg, cod = self._mensagem_erro(resp)
                baixo = msg.lower()
                if status == 400 and adaptacoes < 2 and self._adaptar(corpo, baixo):
                    adaptacoes += 1
                    tentativas -= 1
                    continue
                if status in (401, 403):
                    raise IACredencialError(f"O provedor ({self.provedor}) rejeitou a credencial: {msg}",
                                            sugestao="Confira a chave no arquivo .env e reinicie a API.")
                if cod == "insufficient_quota" or "credit balance" in baixo or "insufficient_quota" in baixo:
                    raise IACotaError(f"Sem crédito ou cota no provedor ({self.provedor}): {msg}",
                                      sugestao="Verifique saldo e faturamento na conta do provedor.")
                if status == 429:
                    espera = _retry_after(resp)
                    erro = IALimiteTaxaError(f"Limite de taxa do provedor ({self.provedor}): {msg}",
                                             sugestao="Aguarde e tente novamente.", retry_after=int(espera or 30))
                elif status >= 500:
                    espera = _retry_after(resp)
                    erro = IAProvedorError(f"O provedor ({self.provedor}) respondeu HTTP {status}: {msg}",
                                           sugestao="Instabilidade do provedor; tente novamente em instantes.")
                else:
                    raise IAProvedorError(
                        f"O provedor ({self.provedor}) recusou a requisição (HTTP {status}): {msg}",
                        sugestao=("Confira o nome do modelo (ESG_OPENAI_MODEL / ESG_ANTHROPIC_MODEL) e a URL base."
                                  if status == 404 else None))
            if tentativas >= max_tent:
                raise erro
            self._dormir(min(espera if espera else 2 ** (tentativas - 1), 20.0))


class ClienteOpenAI(_ClienteBase):
    provedor = "openai"

    def _adaptar(self, corpo, msg):
        if "temperature" in msg and "temperature" in corpo:
            corpo.pop("temperature")
            return True
        if "max_completion_tokens" in msg and "max_completion_tokens" in corpo:     # servidores compatíveis antigos
            corpo["max_tokens"] = corpo.pop("max_completion_tokens")
            return True
        if "max_tokens" in msg and "max_tokens" in corpo:
            corpo["max_completion_tokens"] = corpo.pop("max_tokens")
            return True
        return False

    def gerar(self, sistema: str, usuario: str, max_tokens: Optional[int] = None) -> RespostaLLM:
        corpo = {"model": self.modelo, "max_completion_tokens": max_tokens or self.cfg.max_tokens,
                 "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]}
        if self.cfg.temperatura is not None:
            corpo["temperature"] = self.cfg.temperatura
        headers = {"Authorization": f"Bearer {self.cfg.openai_chave or 'local'}", "Content-Type": "application/json"}
        j, tent, ms = self._enviar(f"{self.cfg.openai_base_url.rstrip('/')}/chat/completions", headers, corpo)
        try:
            escolha = j["choices"][0]
            msg = escolha.get("message") or {}
        except (KeyError, IndexError, TypeError, AttributeError):
            raise IARespostaInvalidaError("A resposta do provedor não contém 'choices'.") from None
        if msg.get("refusal"):
            raise IARespostaInvalidaError("O modelo recusou-se a responder.", sugestao="Reformule o pedido ou revise o texto enviado.")
        conteudo = msg.get("content")
        if isinstance(conteudo, list):
            conteudo = "".join(p.get("text", "") for p in conteudo if isinstance(p, dict))
        texto, motivo = (conteudo or ""), escolha.get("finish_reason")
        if not texto.strip():
            raise IARespostaInvalidaError(
                "O modelo devolveu uma resposta vazia" + (" porque atingiu o limite de tokens (modelos de raciocínio gastam tokens "
                                                          "antes de responder)." if motivo == "length" else "."),
                sugestao="Aumente ESG_IA_MAX_TOKENS (ex.: 6000) ou reduza o texto enviado.")
        uso = j.get("usage") or {}
        return RespostaLLM(texto, self.provedor, self.modelo, uso.get("prompt_tokens"), uso.get("completion_tokens"), motivo, tent, ms)


class ClienteAnthropic(_ClienteBase):
    provedor = "anthropic"

    def _adaptar(self, corpo, msg):
        if "temperature" in msg and "temperature" in corpo:
            corpo.pop("temperature")
            return True
        return False

    def gerar(self, sistema: str, usuario: str, max_tokens: Optional[int] = None) -> RespostaLLM:
        corpo = {"model": self.modelo, "max_tokens": max_tokens or self.cfg.max_tokens, "system": sistema,
                 "messages": [{"role": "user", "content": usuario}]}
        if self.cfg.temperatura is not None:
            corpo["temperature"] = self.cfg.temperatura
        headers = {"x-api-key": self.cfg.anthropic_chave or "", "anthropic-version": "2023-06-01", "content-type": "application/json"}
        j, tent, ms = self._enviar(f"{self.cfg.anthropic_base_url.rstrip('/')}/v1/messages", headers, corpo)
        try:
            texto = "".join(b.get("text", "") for b in j["content"] if isinstance(b, dict) and b.get("type") == "text")
        except (KeyError, TypeError):
            raise IARespostaInvalidaError("A resposta do provedor não contém 'content'.") from None
        if not texto.strip():
            raise IARespostaInvalidaError("O modelo devolveu uma resposta vazia.", sugestao="Tente novamente ou reduza o texto enviado.")
        uso = j.get("usage") or {}
        return RespostaLLM(texto, self.provedor, self.modelo, uso.get("input_tokens"), uso.get("output_tokens"), j.get("stop_reason"), tent, ms)


def criar_cliente(cfg: ConfigIA, provedor: Optional[str] = None, http=None, dormir: Callable[[float], None] = time.sleep):
    prov = cfg.provedor_efetivo(provedor)
    if prov not in PROVEDORES:
        raise TextoInvalidoError(f"Provedor desconhecido: {prov!r}.", sugestao="Use 'openai' ou 'anthropic'.")
    if not cfg.configurado(prov):
        var = "OPENAI_API_KEY" if prov == "openai" else "ANTHROPIC_API_KEY"
        raise IANaoConfiguradaError(f"Nenhuma chave configurada para o provedor '{prov}'.",
                                    sugestao=f"Defina {var} no arquivo .env (veja .env.example) e reinicie a API.")
    return (ClienteOpenAI if prov == "openai" else ClienteAnthropic)(cfg, http, dormir)
