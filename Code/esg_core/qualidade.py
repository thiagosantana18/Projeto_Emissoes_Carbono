"""
Relatório de qualidade dos dados (emissões, notícias, ODS, corpus, sentimento) — insumo do Data Quality Report (TDSP),
da página "Ciclo de dados" do dashboard e da rota GET /qualidade. Tudo calculado sobre os arquivos presentes no momento.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from . import data_access as da
from . import paths
from .validation import diagnostico_qualidade_emissoes


def _estat(serie: pd.Series) -> dict:
    s = pd.to_numeric(serie, errors="coerce").dropna()
    if s.empty:
        return {"min": None, "mediana": None, "max": None}
    return {"min": round(float(s.min()), 2), "mediana": round(float(s.median()), 2), "max": round(float(s.max()), 2)}


def _qualidade_emissoes(df: pd.DataFrame) -> dict:
    diag = diagnostico_qualidade_emissoes(df)
    if df.empty:
        return {**diag, "cobertura_pares_incompletos": [], "outliers": 0, "unidades_medida_por_atividade_ok": True,
                "fatores_estaveis": True, "por_origem": {}}
    meses = df["mes_referencia"].nunique()
    incompletos = []
    for (un, at), g in df.groupby(["unidade", "tipo_atividade"]):
        if g["mes_referencia"].nunique() < meses:
            incompletos.append({"unidade": un, "atividade": at, "meses": int(g["mes_referencia"].nunique()), "esperado": int(meses)})
    outliers = 0
    for _, g in df.groupby(["unidade", "tipo_atividade"]):
        v = np.log(g["emissao_kgco2e"].clip(lower=1e-9))
        if len(v) >= 6 and v.std() > 0:
            outliers += int((np.abs((v - v.mean()) / v.std()) > 3).sum())
    return {**diag, "cobertura_pares_incompletos": incompletos, "outliers": outliers,
            "unidades_medida_por_atividade_ok": bool((df.groupby("tipo_atividade")["unidade_medida"].nunique() == 1).all()),
            "fatores_estaveis": bool((df.groupby("tipo_atividade")["fator_emissao_kgco2e"].nunique() == 1).all()),
            "por_origem": {k: int(v) for k, v in df["origem"].value_counts().items()} if "origem" in df else {},
            "estatistica_emissao_kgco2e": _estat(df["emissao_kgco2e"])}


def _qualidade_noticias(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    titulos = df["titulo"].astype(str)
    datas = pd.to_datetime(df["data_publicacao"], errors="coerce", format="mixed", dayfirst=True)
    prof = df["url_materia"].astype(str).str.replace(r"^https?://[^/]+", "", regex=True).str.strip("/").str.split("/").str.len()
    return {
        "n": int(len(df)), "titulos_duplicados": int(titulos.str.lower().duplicated().sum()),
        "urls_duplicadas": int(df["url_materia"].duplicated().sum()),
        "pct_sem_data_publicacao": round(100 * float(df["data_publicacao"].isna().mean()), 1) if "data_publicacao" in df else 100.0,
        "pct_sem_resumo": round(100 * float(df["resumo"].isna().mean()), 1), "pct_sem_tags": round(100 * float((df["tags"].isna() | (df["tags"].astype(str) == "")).mean()), 1),
        "titulo_caracteres": _estat(titulos.str.len()), "n_fontes": int(df["fonte"].nunique()),
        "periodo_publicacao": [str(datas.min().date()), str(datas.max().date())] if datas.notna().any() else None,
        "ultima_coleta": str(df["data_coleta"].dropna().max()) if df["data_coleta"].notna().any() else None,
        "urls_apontam_para_listagem": int((prof.fillna(0) < 2).sum()),
    }


def _qualidade_ods(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"n": 0}
    return {"n": int(len(df)), "trechos_duplicados": int(df["trecho"].duplicated().sum()),
            "por_ods": {k: int(v) for k, v in df["ods"].value_counts().items()},
            "pct_sem_secao": round(100 * float((df["secao"].isna() | (df["secao"].astype(str) == "")).mean()), 1),
            "trecho_caracteres": _estat(df["trecho"].astype(str).str.len()),
            "ultima_coleta": str(df["data_coleta"].dropna().max()) if df["data_coleta"].notna().any() else None}


def _qualidade_corpus(docs: list) -> dict:
    if not docs:
        return {"n": 0}
    df = pd.DataFrame(docs)
    noticias = df[df["tipo"] == "noticia"]
    return {"n": int(len(df)), "por_tipo": {k: int(v) for k, v in df["tipo"].value_counts().items()},
            "doc_id_duplicados": int(df["doc_id"].duplicated().sum()), "textos_vazios": int((df["texto"].astype(str).str.strip() == "").sum()),
            "sem_fonte_ou_url": int((df["fonte"].isna() | df["url"].isna()).sum()),
            "palavras_por_documento": _estat(df["n_palavras"]), "total_palavras": int(df["n_palavras"].sum()),
            "pct_noticias_sem_data_publicacao": round(100 * float(noticias["data_publicacao"].isna().mean()), 1) if len(noticias) else None,
            "idiomas": sorted(df["idioma"].unique().tolist())}


def _qualidade_sentimento() -> Optional[dict]:
    caminho = paths.processed_dir() / "sentimento_noticias.csv"
    if not caminho.is_file():
        return None
    try:
        df = pd.read_csv(caminho)
        return {"n": int(len(df)), "distribuicao": {k: int(v) for k, v in df["rotulo_previsto"].value_counts().items()},
                "confianca_media": round(float(df["confianca"].mean()), 3), "pct_confianca_abaixo_60": round(100 * float((df["confianca"] < 0.6).mean()), 1)}
    except (KeyError, ValueError, pd.errors.EmptyDataError):
        return None


def relatorio_qualidade() -> dict:
    return {"gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "emissoes": _qualidade_emissoes(da.carregar_emissoes()),
            "noticias": _qualidade_noticias(da.carregar_noticias(preencher_data=False)), "ods": _qualidade_ods(da.carregar_ods()),
            "corpus": _qualidade_corpus(da.carregar_corpus()), "sentimento": _qualidade_sentimento()}


def checks(rel: dict) -> list:
    """Lista de (verificação, passou, detalhe) usada para o resumo 'x de y verificações aprovadas'."""
    e, n, o, c = rel["emissoes"], rel["noticias"], rel["ods"], rel["corpus"]
    cs = []
    if e.get("n_registros"):
        cs += [("Emissões: sem valores nulos", all(v == 0 for v in e["nulos_por_coluna"].values()), f"{sum(e['nulos_por_coluna'].values())} nulos"),
               ("Emissões: sem lacunas mensais", not e["meses_faltantes"], f"{len(e['meses_faltantes'])} meses faltantes"),
               ("Emissões: sem duplicados", e["duplicados"] == 0, f"{e['duplicados']} duplicados"),
               ("Emissões: emissão = quantidade × fator", e["emissoes_inconsistentes"] == 0, f"{e['emissoes_inconsistentes']} inconsistentes"),
               ("Emissões: unidade de medida única por atividade", e["unidades_medida_por_atividade_ok"], ""),
               ("Emissões: sem outliers extremos (z-score absoluto > 3, em log)", e["outliers"] == 0, f"{e['outliers']} outliers")]
    if n.get("n"):
        cs += [("Notícias: sem títulos duplicados", n["titulos_duplicados"] == 0, f"{n['titulos_duplicados']} duplicados"),
               ("Notícias: URLs de matéria (não da listagem)", n["urls_apontam_para_listagem"] == 0, f"{n['urls_apontam_para_listagem']} apontam para listagem"),
               ("Notícias: ≥ 80% com data de publicação", n["pct_sem_data_publicacao"] <= 20, f"{n['pct_sem_data_publicacao']}% sem data")]
    if o.get("n"):
        cs.append(("ODS: sem trechos duplicados", o["trechos_duplicados"] == 0, f"{o['trechos_duplicados']} duplicados"))
    if c.get("n"):
        cs += [("Corpus: doc_id único", c["doc_id_duplicados"] == 0, ""), ("Corpus: sem textos vazios", c["textos_vazios"] == 0, ""),
               ("Corpus: todos com fonte e URL", c["sem_fonte_ou_url"] == 0, f"{c['sem_fonte_ou_url']} sem fonte/URL")]
    return [(nome, bool(ok), det) for nome, ok, det in cs]


def renderizar_relatorio_md(rel: dict) -> str:
    """Markdown do Data Quality Report (artefato TDSP) a partir do relatório calculado."""
    cs = checks(rel)
    e, n, o, c, s = rel["emissoes"], rel["noticias"], rel["ods"], rel["corpus"], rel["sentimento"]
    L = ["# Data Quality Report", "", f"_Gerado automaticamente em {rel['gerado_em']} por `Scripts/gerar_relatorio_qualidade.py` sobre os arquivos presentes em `Data/`. "
         "Reexecute após cada coleta para atualizar._", "", "## 1. Resumo", "",
         f"**{sum(1 for _, ok, _ in cs if ok)} de {len(cs)} verificações aprovadas.**", "", "| Verificação | Resultado | Detalhe |", "|---|---|---|"]
    L += [f"| {nome} | {'✅' if ok else '❌'} | {det} |" for nome, ok, det in cs]
    L += ["", "## 2. Emissões (atividade e emissão)", ""]
    if e.get("n_registros"):
        L += [f"- Registros: **{e['n_registros']}** · período {e['periodo_inicio']} a {e['periodo_fim']} · origens: {e.get('por_origem')}",
              f"- Nulos por coluna: {sum(e['nulos_por_coluna'].values())} no total · duplicados: {e['duplicados']} · meses faltantes: {len(e['meses_faltantes'])} · emissões inconsistentes: {e['emissoes_inconsistentes']}",
              f"- Pares unidade×atividade com meses faltando: {len(e['cobertura_pares_incompletos'])} · outliers (z-score absoluto > 3, em log): {e['outliers']}",
              f"- Fatores de emissão estáveis por atividade: {'sim' if e['fatores_estaveis'] else 'NÃO'} · unidade de medida única por atividade: {'sim' if e['unidades_medida_por_atividade_ok'] else 'NÃO'}",
              f"- Emissão por registro (kgCO2e): {e.get('estatistica_emissao_kgco2e')}",
              "", "> ⚠️ A amostra é **sintética**: ausência de problemas aqui reflete o gerador, não a qualidade de dados reais de uma empresa."]
    else:
        L.append("_Sem dados de emissões._")
    L += ["", "## 3. Notícias coletadas (scraping)", ""]
    if n.get("n"):
        L += [f"- Manchetes: **{n['n']}** · fontes: {n['n_fontes']} · período de publicação: {n['periodo_publicacao']} · última coleta: {n['ultima_coleta']}",
              f"- Títulos duplicados: {n['titulos_duplicados']} · URLs duplicadas: {n['urls_duplicadas']} · URLs que apontam para a listagem: {n['urls_apontam_para_listagem']}",
              f"- Sem data de publicação: {n['pct_sem_data_publicacao']}% · sem linha fina: {n['pct_sem_resumo']}% · sem tags: {n['pct_sem_tags']}%",
              f"- Tamanho do título (caracteres): {n['titulo_caracteres']}"]
    else:
        L.append("_Sem notícias._")
    L += ["", "## 4. Conteúdo dos ODS (scraping)", ""]
    L += ([f"- Trechos: **{o['n']}** {o['por_ods']} · duplicados: {o['trechos_duplicados']} · sem seção: {o['pct_sem_secao']}% · tamanho (caracteres): {o['trecho_caracteres']}"] if o.get("n") else ["_Sem trechos._"])
    L += ["", "## 5. Corpus para IA", ""]
    L += ([f"- Documentos: **{c['n']}** {c['por_tipo']} · `doc_id` duplicados: {c['doc_id_duplicados']} · textos vazios: {c['textos_vazios']} · sem fonte/URL: {c['sem_fonte_ou_url']}",
           f"- Palavras: {c['total_palavras']} no total; por documento {c['palavras_por_documento']} · notícias sem data de publicação: {c['pct_noticias_sem_data_publicacao']}%"] if c.get("n") else ["_Corpus não gerado._"])
    L += ["", "## 6. Previsões de sentimento (modelo local)", ""]
    L += ([f"- Manchetes classificadas: {s['n']} · distribuição {s['distribuicao']} · confiança média {s['confianca_media']} · {s['pct_confianca_abaixo_60']}% com confiança < 0,60",
           "- ⚠️ Previsões de um modelo sem validação contra rótulos humanos."] if s else ["_Ainda não geradas (`python Code/llm/avaliar_sentimento.py prever`)._"])
    L += ["", "## 7. Achados e ações", ""]
    reprovadas = [(nome, det) for nome, ok, det in cs if not ok]
    L += ([f"- **{nome}** — {det}" for nome, det in reprovadas] if reprovadas else ["- Nenhuma verificação reprovada."])
    L += ["", "_Limitação do relatório: mede consistência interna e completude; não mede se os dados são *verdadeiros* (isso exige comparar com a fonte original)._"]
    return "\n".join(L)
