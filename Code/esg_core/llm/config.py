"""Configuração do LLM local, lida de variáveis de ambiente (ver .env.example)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import paths

log = logging.getLogger("esg.llm")

# Escolha documentada em Docs/Project/LLM_Model_Selection.md
MODELO_PADRAO = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"


@dataclass(frozen=True)
class ConfigLLM:
    modelo_id: str = MODELO_PADRAO
    revisao: Optional[str] = None          # fixe um commit do Hub para reprodutibilidade
    pasta_cache: Path = Path("Models/hf_cache")
    offline: bool = True                   # True: nunca baixa durante uma requisição
    dispositivo: str = "cpu"               # "cpu" | "cuda" | "auto"
    max_caracteres: int = 2000             # entrada aceita por texto
    max_tokens: int = 256                  # truncamento do tokenizador
    max_lote: int = 32                     # textos por requisição em lote
    batch_size: int = 8                    # tamanho de lote interno do pipeline
    timeout_s: float = 30.0                # tempo máximo de uma inferência
    max_pendentes: int = 4                 # requisições simultâneas aceitas (resto recebe 429)
    cooldown_falha_s: float = 30.0         # após falha de carga, espera antes de tentar de novo
    threads: Optional[int] = None          # torch.set_num_threads (útil em CPU modesta)


def _bool(nome: str, padrao: bool) -> bool:
    v = os.environ.get(nome)
    return padrao if v is None else v.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _num(nome: str, padrao, tipo):
    v = os.environ.get(nome)
    if v is None or v.strip() == "":
        return padrao
    try:
        return tipo(v)
    except ValueError:
        log.warning("Valor inválido em %s=%r; usando o padrão %r.", nome, v, padrao)
        return padrao


def carregar_config() -> ConfigLLM:
    env = os.environ
    pasta = env.get("ESG_MODEL_DIR")
    if not pasta:
        try:
            pasta = str(paths.raiz_projeto() / "Models" / "hf_cache")
        except FileNotFoundError:
            pasta = str(Path.cwd() / "Models" / "hf_cache")
    dispositivo = env.get("ESG_LLM_DEVICE", "cpu").strip().lower()
    if dispositivo not in {"cpu", "cuda", "auto"}:
        log.warning("ESG_LLM_DEVICE=%r inválido; usando 'cpu'.", dispositivo)
        dispositivo = "cpu"
    threads = _num("ESG_LLM_THREADS", None, int)
    return ConfigLLM(
        modelo_id=env.get("ESG_LLM_MODEL", MODELO_PADRAO).strip() or MODELO_PADRAO,
        revisao=(env.get("ESG_LLM_REVISION") or "").strip() or None,
        pasta_cache=Path(pasta),
        offline=_bool("ESG_LLM_OFFLINE", True),
        dispositivo=dispositivo,
        max_caracteres=_num("ESG_LLM_MAX_CHARS", 2000, int),
        max_tokens=_num("ESG_LLM_MAX_TOKENS", 256, int),
        max_lote=_num("ESG_LLM_MAX_LOTE", 32, int),
        batch_size=_num("ESG_LLM_BATCH", 8, int),
        timeout_s=_num("ESG_LLM_TIMEOUT", 30.0, float),
        max_pendentes=max(1, _num("ESG_LLM_MAX_PENDENTES", 4, int)),
        cooldown_falha_s=_num("ESG_LLM_COOLDOWN", 30.0, float),
        threads=threads if threads and threads > 0 else None,
    )
