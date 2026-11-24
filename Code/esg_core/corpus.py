"""
Preparação dos dados para tarefas com LLM (SEM chamar nenhum LLM).

Produz:
  * corpus_llm.jsonl          – documentos de texto em schema único e rastreável
  * contexto_relatorio.json   – agregados numéricos (grounding p/ geração de relatórios)
  * avaliacao/*.csv           – gabaritos (templates) para avaliar as tarefas na próxima etapa

Schema de um documento do corpus (uma linha do JSONL):
  doc_id, tipo, fonte, url, titulo, texto, data_publicacao, data_coleta,
  idioma, n_palavras, secao, tags, usos_previstos
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from . import data_access as da
from . import paths
from .text_utils import contar_palavras

USOS_POR_TIPO = {
    "noticia": ["classificacao_sentimento", "resumo", "perguntas_respostas"],
    "ods_trecho": ["perguntas_respostas", "resumo"],
}


def _iso(valor) -> Optional[str]:
    if valor is None or pd.isna(valor) or str(valor).strip() == "":
        return None
    dt = pd.to_datetime(str(valor), errors="coerce", format="mixed", dayfirst=True)
    return None if pd.isna(dt) else dt.strftime("%Y-%m-%d")


def _txt(valor) -> Optional[str]:
    if valor is None or pd.isna(valor):
        return None
    s = str(valor).strip()
    return s or None


def _doc_id(tipo: str, url: Optional[str], texto: str) -> str:
    return hashlib.sha1(f"{tipo}|{url}|{texto}".encode("utf-8")).hexdigest()[:12]


def _dominio(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    partes = url.split("/")
    return partes[2] if len(partes) > 2 else None


def documentos_de_noticias(df: pd.DataFrame) -> list[dict]:
    docs = []
    for _, r in df.iterrows():
        titulo = _txt(r.get("titulo"))
        if not titulo:
            continue
        resumo = _txt(r.get("resumo"))
        texto = f"{titulo}. {resumo}" if resumo else titulo
        url = _txt(r.get("url_materia"))
        docs.append({
            "doc_id": _doc_id("noticia", url, titulo),
            "tipo": "noticia",
            "fonte": _txt(r.get("fonte")) or _dominio(url),
            "url": url,
            "titulo": titulo,
            "texto": texto,
            "data_publicacao": _iso(r.get("data_publicacao")),
            "data_coleta": _txt(r.get("data_coleta")),
            "idioma": "pt",
            "n_palavras": contar_palavras(texto),
            "secao": None,
            "tags": [t for t in (_txt(r.get("tags")) or "").split(";") if t],
            "usos_previstos": USOS_POR_TIPO["noticia"],
        })
    return docs


def documentos_de_ods(df: pd.DataFrame) -> list[dict]:
    docs = []
    for _, r in df.iterrows():
        trecho = _txt(r.get("trecho"))
        if not trecho:
            continue
        url = _txt(r.get("url_fonte"))
        docs.append({
            "doc_id": _doc_id("ods_trecho", url, trecho),
            "tipo": "ods_trecho",
            "fonte": _dominio(url),
            "url": url,
            "titulo": _txt(r.get("ods")) or _txt(r.get("titulo_pagina")),
            "texto": trecho,
            "data_publicacao": None,
            "data_coleta": _txt(r.get("data_coleta")),
            "idioma": "pt",
            "n_palavras": contar_palavras(trecho),
            "secao": _txt(r.get("secao")),
            "tags": [],
            "usos_previstos": USOS_POR_TIPO["ods_trecho"],
        })
    return docs


def construir_corpus() -> list[dict]:
    docs = documentos_de_noticias(da.carregar_noticias(preencher_data=False)) + documentos_de_ods(da.carregar_ods())
    vistos, unicos = set(), []
    for d in docs:                       # deduplicação por doc_id
        if d["doc_id"] not in vistos:
            vistos.add(d["doc_id"])
            unicos.append(d)
    return unicos


def salvar_jsonl(docs: list[dict], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def construir_contexto_relatorio(df_emissoes: pd.DataFrame) -> dict:
    """Agregados numéricos rastreáveis — base para 'geração de texto' com checagem de fidelidade."""
    resumo = da.resumo_emissoes(df_emissoes)
    total = resumo["total_kgco2e"] or 0.0

    def com_percentual(mapa: dict) -> list[dict]:
        itens = [{"nome": k, "kgco2e": v, "percentual": round(100 * v / total, 1) if total else 0.0}
                 for k, v in mapa.items()]
        return sorted(itens, key=lambda x: x["kgco2e"], reverse=True)

    meses = sorted(resumo["por_mes"].items())
    variacao = None
    if len(meses) >= 2 and meses[-2][1]:
        variacao = round(100 * (meses[-1][1] - meses[-2][1]) / meses[-2][1], 1)

    fatores = (df_emissoes[["tipo_atividade", "unidade_medida", "fator_emissao_kgco2e", "fonte_fator"]]
               .drop_duplicates().sort_values("tipo_atividade").to_dict("records")) if not df_emissoes.empty else []

    return {
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "periodo": {"inicio": resumo["periodo_inicio"], "fim": resumo["periodo_fim"]},
        "n_registros": resumo["n_registros"],
        "total_kgco2e": resumo["total_kgco2e"],
        "por_unidade": com_percentual(resumo["por_unidade"]),
        "por_tipo_atividade": com_percentual(resumo["por_tipo_atividade"]),
        "por_mes": [{"mes": m, "kgco2e": v} for m, v in meses],
        "variacao_ultimo_mes_pct": variacao,
        "maiores_fontes": com_percentual(resumo["por_tipo_atividade"])[:3],
        "fatores_utilizados": fatores,
        "observacoes": [
            "Dados de atividade sintéticos (amostra de demonstração).",
            "Fatores de emissão são valores de referência fixos rotulados por fonte; "
            "ainda não vêm de consulta ao vivo à Climatiq API.",
        ],
    }


def gerar_templates_avaliacao(docs: list[dict], pasta: Path) -> list[Path]:
    """Gabaritos vazios para avaliar sentimento e Q&A (preenchidos manualmente depois)."""
    pasta.mkdir(parents=True, exist_ok=True)
    sent = pasta / "sentimento_gold_template.csv"
    qa = pasta / "qa_gold_template.csv"
    with open(sent, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "titulo", "rotulo_humano", "anotador", "observacao"])
        for d in docs:
            if d["tipo"] == "noticia":
                w.writerow([d["doc_id"], d["titulo"], "", "", ""])   # rotulo: positivo | negativo | neutro
    with open(qa, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["pergunta", "resposta_esperada", "doc_id_fonte", "tipo_pergunta"])
    return [sent, qa]
