"""Regras de validação e diagnóstico de qualidade dos dados de emissões."""
from __future__ import annotations

import re
from typing import Optional

import pandas as pd

COLUNAS_EMISSOES = [
    "mes_referencia",
    "unidade",
    "setor",
    "tipo_atividade",
    "quantidade",
    "unidade_medida",
    "fator_emissao_kgco2e",
    "emissao_kgco2e",
    "fonte_fator",
]
COLUNAS_TEXTO = ["mes_referencia", "unidade", "setor", "tipo_atividade", "unidade_medida", "fonte_fator"]
COLUNAS_NUMERICAS = ["quantidade", "fator_emissao_kgco2e", "emissao_kgco2e"]
REGEX_MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

TOLERANCIA_RELATIVA = 0.01   # 1 %
TOLERANCIA_ABSOLUTA = 0.05   # kgCO2e (cobre arredondamento a 2 casas)


def emissao_consistente(quantidade: float, fator: float, emissao: float) -> bool:
    """Regra de negócio: emissão ≈ quantidade × fator (tolerância de arredondamento)."""
    esperado = quantidade * fator
    return abs(emissao - esperado) <= max(TOLERANCIA_ABSOLUTA, TOLERANCIA_RELATIVA * abs(esperado))


def calcular_emissao(quantidade: float, fator: float) -> float:
    return round(quantidade * fator, 2)


def validar_emissoes_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Valida um DataFrame de emissões (upload de CSV, por exemplo).

    Retorna (linhas_válidas, mensagens_de_erro).
      * Colunas faltando => rejeição do arquivo inteiro (DataFrame vazio).
      * Erros por linha  => só as linhas inválidas são descartadas e listadas.
    Os números de linha referem-se ao arquivo original (cabeçalho = linha 1).
    """
    faltantes = [c for c in COLUNAS_EMISSOES if c not in df.columns]
    if faltantes:
        return pd.DataFrame(columns=COLUNAS_EMISSOES), [
            "Colunas obrigatórias ausentes: " + ", ".join(faltantes)
        ]

    trabalho = df[COLUNAS_EMISSOES].copy()
    erros: list[str] = []
    invalidas: set = set()

    for col in COLUNAS_NUMERICAS:
        trabalho[col] = pd.to_numeric(trabalho[col], errors="coerce")
    for col in COLUNAS_TEXTO:
        trabalho[col] = trabalho[col].astype("string").str.strip()

    for idx, linha in trabalho.iterrows():
        n = int(idx) + 2
        problemas = []
        for col in COLUNAS_TEXTO:
            if pd.isna(linha[col]) or linha[col] == "":
                problemas.append(f"'{col}' vazio")
        if not pd.isna(linha["mes_referencia"]) and not REGEX_MES.match(str(linha["mes_referencia"])):
            problemas.append("'mes_referencia' deve estar no formato AAAA-MM")
        for col in COLUNAS_NUMERICAS:
            if pd.isna(linha[col]):
                problemas.append(f"'{col}' ausente ou não numérico")
        if not problemas:
            if linha["quantidade"] <= 0:
                problemas.append("'quantidade' deve ser > 0")
            if linha["fator_emissao_kgco2e"] < 0 or linha["emissao_kgco2e"] < 0:
                problemas.append("fator/emissão não podem ser negativos")
            elif not emissao_consistente(
                linha["quantidade"], linha["fator_emissao_kgco2e"], linha["emissao_kgco2e"]
            ):
                problemas.append("emissão diverge de quantidade × fator")
        if problemas:
            invalidas.add(idx)
            erros.append(f"Linha {n}: " + "; ".join(problemas))

    validas = trabalho.drop(index=list(invalidas)).reset_index(drop=True)
    for col in COLUNAS_TEXTO:
        validas[col] = validas[col].astype(object)
    return validas, erros


def diagnostico_qualidade_emissoes(df: pd.DataFrame) -> dict:
    """Checks de qualidade usados na página de Estatísticas e no Data Summary Report."""
    if df.empty:
        return {"n_registros": 0, "nulos_por_coluna": {}, "duplicados": 0,
                "meses_faltantes": [], "emissoes_inconsistentes": 0,
                "periodo_inicio": None, "periodo_fim": None}

    nulos = {c: int(df[c].isna().sum()) for c in COLUNAS_EMISSOES if c in df.columns}
    chave = [c for c in ("mes_referencia", "unidade", "setor", "tipo_atividade") if c in df.columns]
    duplicados = int(df.duplicated(subset=chave).sum())

    meses = pd.PeriodIndex(df["mes_referencia"].dropna().astype(str).unique(), freq="M").sort_values()
    esperado = pd.period_range(meses.min(), meses.max(), freq="M")
    faltantes = [str(m) for m in esperado.difference(meses)]

    num = df.dropna(subset=COLUNAS_NUMERICAS)
    inconsistentes = int(sum(
        not emissao_consistente(q, f, e)
        for q, f, e in zip(num["quantidade"], num["fator_emissao_kgco2e"], num["emissao_kgco2e"])
    ))
    return {
        "n_registros": int(len(df)),
        "nulos_por_coluna": nulos,
        "duplicados": duplicados,
        "meses_faltantes": faltantes,
        "emissoes_inconsistentes": inconsistentes,
        "periodo_inicio": str(meses.min()),
        "periodo_fim": str(meses.max()),
    }
