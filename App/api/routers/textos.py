"""Rotas de dados textuais: notícias, conteúdo dos ODS e corpus preparado para LLM."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from esg_core import data_access as da

from ..schemas import ListaCorpus, ListaNoticias, ListaODS

router = APIRouter()


@router.get(
    "/noticias",
    response_model=ListaNoticias,
    tags=["Textos"],
    summary="Consultar manchetes de notícias ESG coletadas",
    description="Manchetes coletadas por web scraping (Data/raw/noticias_esg.csv), da mais recente para a mais antiga. "
                "`q` busca no título; `tag` filtra por tag temática (ex.: carbono, emissoes, esg, clima).",
)
def listar_noticias(
    q: Optional[str] = Query(None, description="Texto a buscar no título."),
    tag: Optional[str] = Query(None, description="Tag temática."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    df = da.filtrar_noticias(da.carregar_noticias(), q, tag)
    return {"total": len(df), "limit": limit, "offset": offset,
            "itens": da.df_para_registros(da.paginar(df, limit, offset))}


@router.get(
    "/ods",
    response_model=ListaODS,
    tags=["Textos"],
    summary="Consultar trechos sobre os ODS 12 e 13",
    description="Trechos coletados por web scraping (Data/raw/ods_conteudo.csv). `ods` aceita '12' ou '13'.",
)
def listar_ods(
    ods: Optional[str] = Query(None, description="Número do ODS: 12 ou 13."),
    q: Optional[str] = Query(None, description="Texto a buscar no trecho."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    df = da.filtrar_ods(da.carregar_ods(), ods, q)
    return {"total": len(df), "limit": limit, "offset": offset,
            "itens": da.df_para_registros(da.paginar(df, limit, offset))}


_MSG_CORPUS = ("Corpus ainda não gerado. Execute: python Code/data_preparation/build_corpus.py")


@router.get(
    "/corpus",
    response_model=ListaCorpus,
    tags=["Preparação para LLM"],
    summary="Consultar o corpus unificado (preparado para tarefas com LLM)",
    description="Documentos de texto em schema único e rastreável (doc_id, fonte, url, data, tags, usos previstos). "
                "É a porta de entrada de dados para as tarefas de LLM da próxima etapa "
                "(sentimento, resumo, Q&A). Nenhum LLM é executado por esta rota.",
)
def listar_corpus(
    tipo: Optional[str] = Query(None, description="'noticia' ou 'ods_trecho'."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    docs = da.carregar_corpus()
    if not docs:
        raise HTTPException(status_code=404, detail=_MSG_CORPUS)
    if tipo:
        docs = [d for d in docs if d["tipo"] == tipo]
    return {"total": len(docs), "limit": limit, "offset": offset, "itens": docs[offset: offset + limit]}


@router.get(
    "/corpus/contexto-relatorio",
    tags=["Preparação para LLM"],
    summary="Agregados numéricos para geração de relatórios (grounding)",
    description="Totais por unidade/atividade/mês, maiores fontes e fatores utilizados. "
                "Base factual para a futura geração de relatórios com LLM e para a checagem de fidelidade numérica.",
)
def contexto_relatorio():
    contexto = da.carregar_contexto_relatorio()
    if contexto is None:
        raise HTTPException(status_code=404, detail=_MSG_CORPUS)
    return contexto
