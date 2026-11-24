"""Download único do modelo para o cache local (a partir daí a API roda 100% offline)."""
from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from .config import ConfigLLM, carregar_config


def tamanho_pasta_mb(pasta: Path) -> float:
    return round(sum(f.stat().st_size for f in pasta.rglob("*") if f.is_file()) / 1024 ** 2, 1) if pasta.exists() else 0.0


def baixar_modelo(cfg: ConfigLLM = None) -> dict:
    """Baixa tokenizador e pesos para `cfg.pasta_cache`. Requer internet e `transformers` instalado."""
    cfg = replace(cfg or carregar_config(), offline=False)
    from transformers import AutoModelForSequenceClassification, AutoTokenizer  # importação tardia

    cfg.pasta_cache.mkdir(parents=True, exist_ok=True)
    comuns = {"cache_dir": str(cfg.pasta_cache)}
    if cfg.revisao:
        comuns["revision"] = cfg.revisao
    t0 = time.perf_counter()
    AutoTokenizer.from_pretrained(cfg.modelo_id, **comuns)
    AutoModelForSequenceClassification.from_pretrained(cfg.modelo_id, **comuns)
    return {"modelo": cfg.modelo_id, "pasta": str(cfg.pasta_cache),
            "tamanho_mb": tamanho_pasta_mb(cfg.pasta_cache), "tempo_s": round(time.perf_counter() - t0, 1)}
