"""
Acesso a dados (CSV/JSONL) com schema defensivo.

Lição aprendida (KeyError 'data_publicacao'): scripts de coleta e app
evoluem em ritmos diferentes. Todo loader aqui GARANTE as colunas esperadas,
preenchendo com NA quando faltarem, em vez de deixar o consumidor quebrar.
"""
from __future__ import annotations

import csv
import json
import os
import threading
from pathlib import Path
from typing import Optional

import pandas as pd

from . import paths
from .validation import COLUNAS_EMISSOES

COLUNAS_NOTICIAS = ["titulo", "data_publicacao", "url_materia", "data_coleta", "fonte", "resumo", "tags"]
COLUNAS_ODS = ["ods", "titulo_pagina", "secao", "trecho", "url_fonte", "data_coleta"]

_LOCK_ESCRITA = threading.Lock()


def _garantir_colunas(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    for c in colunas:
        if c not in df.columns:
            df[c] = pd.NA
    return df[colunas + [c for c in df.columns if c not in colunas]]


def _ler_csv(caminho: Path, colunas: list[str]) -> pd.DataFrame:
    if not caminho.is_file() or caminho.stat().st_size == 0:
        return pd.DataFrame(columns=colunas)
    try:
        df = pd.read_csv(caminho)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=colunas)
    return _garantir_colunas(df, colunas)


# ----------------------------------------------------------------- emissões
def carregar_emissoes_base() -> pd.DataFrame:
    df = _ler_csv(paths.caminho_emissoes_base(), COLUNAS_EMISSOES)
    df["origem"] = "base"
    return df


def carregar_emissoes_enviadas() -> pd.DataFrame:
    df = _ler_csv(paths.caminho_emissoes_enviadas(), COLUNAS_EMISSOES)
    df["origem"] = "api"
    return df


def carregar_emissoes(incluir_enviadas: bool = True) -> pd.DataFrame:
    partes = [carregar_emissoes_base()]
    if incluir_enviadas:
        enviadas = carregar_emissoes_enviadas()
        if not enviadas.empty:
            partes.append(enviadas)
    return pd.concat(partes, ignore_index=True)


def anexar_emissoes_enviadas(registros: list[dict]) -> int:
    """Acrescenta registros (já validados) em Data/raw/emissoes_enviadas_api.csv."""
    if not registros:
        return 0
    caminho = paths.caminho_emissoes_enviadas()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK_ESCRITA:
        novo = not caminho.is_file() or caminho.stat().st_size == 0
        with open(caminho, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUNAS_EMISSOES, extrasaction="ignore")
            if novo:
                w.writeheader()
            w.writerows(registros)
    return len(registros)


def template_emissoes_csv() -> str:
    """CSV de exemplo (cabeçalho + 1 linha) para o usuário preencher e enviar."""
    return (",".join(COLUNAS_EMISSOES) + "\n"
            "2026-09,Matriz - SP,Administrativo,Eletricidade (rede),8500.0,kWh,0.0817,694.45,Climatiq API\n")


def assinatura_arquivos(*caminhos: Path) -> tuple:
    """(caminho, mtime) de cada arquivo — usada como chave para invalidar caches."""
    return tuple((str(c), os.path.getmtime(c) if c.exists() else 0.0) for c in caminhos)


def assinatura_emissoes() -> tuple:
    return assinatura_arquivos(paths.caminho_emissoes_base(), paths.caminho_emissoes_enviadas())


# ----------------------------------------------------------------- textos
def carregar_noticias(preencher_data: bool = True) -> pd.DataFrame:
    """
    Manchetes coletadas.

    preencher_data=True  (padrão, uso em UI/API): quando data_publicacao falta, usa data_coleta
                         só para exibir/ordenar sem quebrar.
    preencher_data=False (uso no corpus p/ LLM): mantém NA — uma data de coleta NUNCA deve ser
                         apresentada como data de publicação em dados rastreáveis.
    """
    df = _ler_csv(paths.caminho_noticias(), COLUNAS_NOTICIAS)
    if preencher_data:
        df["data_publicacao"] = df["data_publicacao"].fillna(df["data_coleta"])
    return df


def carregar_ods() -> pd.DataFrame:
    return _ler_csv(paths.caminho_ods(), COLUNAS_ODS)


def carregar_corpus() -> list[dict]:
    caminho = paths.caminho_corpus()
    if not caminho.is_file():
        return []
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def carregar_contexto_relatorio() -> Optional[dict]:
    caminho = paths.caminho_contexto_relatorio()
    if not caminho.is_file():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- agregações
def resumo_emissoes(df: pd.DataFrame) -> dict:
    """Totais e agregações usados pela API (/emissoes/resumo) e pelo contexto de relatório."""
    if df.empty:
        return {"n_registros": 0, "total_kgco2e": 0.0, "periodo_inicio": None, "periodo_fim": None,
                "por_unidade": {}, "por_tipo_atividade": {}, "por_mes": {}}

    def agrupar(col: str) -> dict:
        s = df.groupby(col)["emissao_kgco2e"].sum().sort_index()
        return {str(k): round(float(v), 2) for k, v in s.items()}

    return {
        "n_registros": int(len(df)),
        "total_kgco2e": round(float(df["emissao_kgco2e"].sum()), 2),
        "periodo_inicio": str(df["mes_referencia"].min()),
        "periodo_fim": str(df["mes_referencia"].max()),
        "por_unidade": agrupar("unidade"),
        "por_tipo_atividade": agrupar("tipo_atividade"),
        "por_mes": agrupar("mes_referencia"),
    }


def filtrar_emissoes(
    df: pd.DataFrame,
    unidade: Optional[str] = None,
    setor: Optional[str] = None,
    tipo_atividade: Optional[str] = None,
    mes_inicio: Optional[str] = None,
    mes_fim: Optional[str] = None,
    origem: Optional[str] = None,
) -> pd.DataFrame:
    """Filtros usados pelo GET /emissoes (comparação textual case-insensitive)."""
    out = df
    for col, valor in (("unidade", unidade), ("setor", setor), ("tipo_atividade", tipo_atividade), ("origem", origem)):
        if valor:
            out = out[out[col].astype(str).str.lower() == valor.lower()]
    if mes_inicio:
        out = out[out["mes_referencia"] >= mes_inicio]
    if mes_fim:
        out = out[out["mes_referencia"] <= mes_fim]
    return out


def paginar(df: pd.DataFrame, limit: int, offset: int) -> pd.DataFrame:
    return df.iloc[offset: offset + limit]


def df_para_registros(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> lista de dicts JSON-safe (NaN/NA -> None)."""
    limpo = df.astype(object).where(pd.notna(df), None)
    return limpo.to_dict("records")


def filtrar_noticias(df: pd.DataFrame, q: Optional[str] = None, tag: Optional[str] = None) -> pd.DataFrame:
    """Busca textual no título e filtro por tag temática; ordena da mais recente para a mais antiga."""
    out = df
    if q:
        out = out[out["titulo"].astype(str).str.contains(q, case=False, regex=False, na=False)]
    if tag:
        out = out[out["tags"].astype(str).str.split(";").apply(lambda ts: tag.lower() in [t.lower() for t in ts])]
    datas = pd.to_datetime(out["data_publicacao"], errors="coerce", format="mixed", dayfirst=True)
    return out.assign(_d=datas).sort_values("_d", ascending=False, na_position="last").drop(columns="_d")


def filtrar_ods(df: pd.DataFrame, ods: Optional[str] = None, q: Optional[str] = None) -> pd.DataFrame:
    """`ods` aceita '12', 'ods 12', 'ODS-12' etc.; `q` busca no trecho."""
    out = df
    if ods:
        numero = "".join(ch for ch in str(ods) if ch.isdigit())
        out = out[out["ods"].astype(str).str.contains(numero, regex=False)] if numero else out
    if q:
        out = out[out["trecho"].astype(str).str.contains(q, case=False, regex=False, na=False)]
    return out
