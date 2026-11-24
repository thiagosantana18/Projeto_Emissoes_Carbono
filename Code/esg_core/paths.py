"""Resolução centralizada de caminhos do projeto."""
from __future__ import annotations

import os
from pathlib import Path

_MARCADORES = ("Code", "Data")


def raiz_projeto() -> Path:
    """
    Localiza a raiz do projeto (pasta que contém Code/ e Data/).

    Ordem: variável de ambiente ESG_PROJECT_ROOT -> busca ascendente a partir
    deste arquivo. Evita fixar o número de níveis (causa de um bug anterior de
    'arquivo não encontrado' quando o app.py mudava de pasta).
    """
    env = os.environ.get("ESG_PROJECT_ROOT")
    if env:
        return Path(env).resolve()
    aqui = Path(__file__).resolve()
    for candidato in aqui.parents:
        if all((candidato / m).is_dir() for m in _MARCADORES):
            return candidato
    raise FileNotFoundError(
        "Raiz do projeto não encontrada (esperado: pasta com Code/ e Data/). "
        "Defina ESG_PROJECT_ROOT se estiver executando fora da estrutura padrão."
    )


def data_dir() -> Path:
    """Pasta Data/. Pode ser sobrescrita por ESG_DATA_DIR (útil em testes/deploy)."""
    env = os.environ.get("ESG_DATA_DIR")
    return Path(env).resolve() if env else raiz_projeto() / "Data"


def raw_dir() -> Path:
    return data_dir() / "raw"


def processed_dir() -> Path:
    return data_dir() / "processed"


def interim_dir() -> Path:
    return data_dir() / "interim"


def caminho_emissoes_base() -> Path:
    return processed_dir() / "amostra_emissoes.csv"


def caminho_emissoes_enviadas() -> Path:
    """Registros recebidos via API (POST /emissoes). Dado de usuário: não versionado."""
    return raw_dir() / "emissoes_enviadas_api.csv"


def caminho_noticias() -> Path:
    return raw_dir() / "noticias_esg.csv"


def caminho_ods() -> Path:
    return raw_dir() / "ods_conteudo.csv"


def caminho_corpus() -> Path:
    return processed_dir() / "corpus_llm.jsonl"


def caminho_contexto_relatorio() -> Path:
    return processed_dir() / "contexto_relatorio.json"


def caminho_ia_dir() -> Path:
    """Saídas e histórico de auditoria das gerações com IA (não versionado)."""
    return processed_dir() / "ia"


def caminho_ia_cache_dir() -> Path:
    return interim_dir() / "ia_cache"
