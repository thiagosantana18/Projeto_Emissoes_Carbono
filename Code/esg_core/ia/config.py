"""Configuração da IA online, lida de variáveis de ambiente / .env (ver .env.example). Chaves nunca aparecem em repr/logs."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("esg.ia")

PROVEDORES = ("openai", "anthropic")
OPENAI_URL_PADRAO = "https://api.openai.com/v1"
ANTHROPIC_URL_PADRAO = "https://api.anthropic.com"


@dataclass(frozen=True)
class ConfigIA:
    provedor_padrao: str = "openai"
    openai_chave: Optional[str] = field(default=None, repr=False)
    openai_modelo: str = "gpt-5-mini"
    openai_base_url: str = OPENAI_URL_PADRAO
    anthropic_chave: Optional[str] = field(default=None, repr=False)
    anthropic_modelo: str = "claude-haiku-5-5"
    anthropic_base_url: str = ANTHROPIC_URL_PADRAO
    timeout_s: float = 90.0
    max_tokens: int = 3000                  # modelos de raciocínio gastam tokens "invisíveis": não use valores baixos
    temperatura: Optional[float] = None     # None = padrão do modelo (alguns modelos rejeitam valores customizados)
    retentativas: int = 2
    max_chars_entrada: int = 60000
    max_chamadas_hora: int = 60
    max_docs: int = 40
    cache_ativo: bool = True

    def openai_local(self) -> bool:
        """True se a URL base não é a da OpenAI (ex.: Ollama/LM Studio): nesse caso a chave é opcional."""
        return self.openai_base_url.rstrip("/") != OPENAI_URL_PADRAO

    def configurado(self, provedor: str) -> bool:
        if provedor == "openai":
            return bool(self.openai_chave) or self.openai_local()
        if provedor == "anthropic":
            return bool(self.anthropic_chave)
        return False

    def modelo(self, provedor: str) -> str:
        return self.openai_modelo if provedor == "openai" else self.anthropic_modelo

    def provedor_efetivo(self, preferido: Optional[str] = None) -> str:
        if preferido:
            return preferido
        if self.configurado(self.provedor_padrao):
            return self.provedor_padrao
        for p in PROVEDORES:
            if self.configurado(p):
                return p
        return self.provedor_padrao


def _num(nome: str, padrao, tipo):
    v = os.environ.get(nome)
    if v is None or v.strip() == "":
        return padrao
    try:
        return tipo(v)
    except ValueError:
        log.warning("Valor inválido em %s; usando o padrão.", nome)
        return padrao


def carregar_config_ia() -> ConfigIA:
    e = os.environ
    prov = e.get("ESG_IA_PROVIDER", "openai").strip().lower()
    return ConfigIA(
        provedor_padrao=prov if prov in PROVEDORES else "openai",
        openai_chave=(e.get("OPENAI_API_KEY") or "").strip() or None,
        openai_modelo=e.get("ESG_OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini",
        openai_base_url=(e.get("ESG_OPENAI_BASE_URL") or OPENAI_URL_PADRAO).strip(),
        anthropic_chave=(e.get("ANTHROPIC_API_KEY") or "").strip() or None,
        anthropic_modelo=e.get("ESG_ANTHROPIC_MODEL", "claude-haiku-5-5").strip() or "claude-haiku-5-5",
        anthropic_base_url=(e.get("ESG_ANTHROPIC_BASE_URL") or ANTHROPIC_URL_PADRAO).strip(),
        timeout_s=_num("ESG_IA_TIMEOUT", 90.0, float),
        max_tokens=max(256, _num("ESG_IA_MAX_TOKENS", 3000, int)),
        temperatura=_num("ESG_IA_TEMPERATURA", None, float),
        retentativas=max(0, _num("ESG_IA_RETENTATIVAS", 2, int)),
        max_chars_entrada=_num("ESG_IA_MAX_CHARS", 60000, int),
        max_chamadas_hora=max(1, _num("ESG_IA_MAX_CHAMADAS_HORA", 60, int)),
        max_docs=_num("ESG_IA_MAX_DOCS", 40, int),
        cache_ativo=e.get("ESG_IA_CACHE", "1").strip().lower() in {"1", "true", "sim", "yes", "on"},
    )
