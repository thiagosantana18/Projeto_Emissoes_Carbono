"""
Funções compartilhadas pelas páginas do dashboard: cache de dados, estado de sessão,
widgets com persistência entre páginas e componentes visuais.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

import api_client

from esg_core import data_access as da
from esg_core import paths
from esg_core.text_utils import STOPWORDS_PT

try:
    from wordcloud import WordCloud
    WORDCLOUD_OK = True
except ImportError:  # pacote opcional
    WORDCLOUD_OK = False

COR = "#1F6F50"

# Chaves de widgets cujo valor deve sobreviver à troca de página (ver manter_estado).
CHAVES_PERSISTENTES = [
    "f_unidades", "f_atividades", "f_origens", "f_periodo",
    "noticias_busca", "noticias_tag", "nuvem_fonte", "nuvem_topn", "api_url", "fonte_dados", "texto_llm",
]


# ------------------------------------------------------------------ estado
def inicializar_estado() -> None:
    padroes = {"df_uploads": None, "historico_uploads": [], "uploader_n": 0, "api_url": "http://127.0.0.1:8000",
               "api_nonce": 0, "sentimentos_resultados": None}
    for k, v in padroes.items():
        st.session_state.setdefault(k, v)


def manter_estado() -> None:
    """
    Streamlit apaga o estado de um widget quando a página que o contém deixa de ser
    renderizada. Reatribuir o valor a cada execução (em TODAS as páginas) o preserva.
    """
    for k in CHAVES_PERSISTENTES:
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]


def valor_padrao(chave: str, padrao) -> None:
    """Define o valor inicial pelo session_state (evita o aviso 'default + session_state')."""
    st.session_state.setdefault(chave, padrao)


def multiselect_persistente(rotulo: str, opcoes, chave: str):
    opcoes = list(opcoes)
    atual = st.session_state.get(chave)
    st.session_state[chave] = opcoes if atual is None else [x for x in atual if x in opcoes]
    return st.multiselect(rotulo, opcoes, key=chave)


def periodo_persistente(rotulo: str, meses, chave: str):
    meses = list(meses)
    if len(meses) < 2:
        st.caption(f"{rotulo}: {meses[0] if meses else '—'}")
        return (meses[0], meses[0]) if meses else (None, None)
    atual = st.session_state.get(chave)
    if not atual or atual[0] not in meses or atual[1] not in meses:
        st.session_state[chave] = (meses[0], meses[-1])
    return st.select_slider(rotulo, options=meses, key=chave)


# ------------------------------------------------------------------ dados com cache
# A chave de cache é a assinatura (caminho + data de modificação) dos arquivos: quando um
# CSV muda (scraper rodou, POST na API), o cache é invalidado sozinho. NÃO prefixar o
# parâmetro com "_" — Streamlit ignora parâmetros com underscore no hash.
@st.cache_data(show_spinner=False)
def _emissoes(assinatura: tuple) -> pd.DataFrame:
    return da.carregar_emissoes()


@st.cache_data(show_spinner=False)
def _noticias(assinatura: tuple) -> pd.DataFrame:
    return da.carregar_noticias()


@st.cache_data(show_spinner=False)
def _ods(assinatura: tuple) -> pd.DataFrame:
    return da.carregar_ods()


@st.cache_data(show_spinner=False)
def _corpus(assinatura: tuple) -> list:
    return da.carregar_corpus()


def emissoes_base_api() -> pd.DataFrame:
    return _emissoes(da.assinatura_emissoes())


def noticias() -> pd.DataFrame:
    return _noticias(da.assinatura_arquivos(paths.caminho_noticias()))


def ods() -> pd.DataFrame:
    return _ods(da.assinatura_arquivos(paths.caminho_ods()))


def corpus() -> list:
    return _corpus(da.assinatura_arquivos(paths.caminho_corpus()))


def emissoes_consolidadas() -> pd.DataFrame:
    """Base + registros enviados via API (em disco) + uploads feitos nesta sessão."""
    base = emissoes_base_api()
    up = st.session_state.get("df_uploads")
    if up is not None and not up.empty:
        return pd.concat([base, up], ignore_index=True)
    return base


@st.cache_data(ttl=20, show_spinner=False)
def _emissoes_api(base_url: str, nonce: int) -> pd.DataFrame:
    """Dados vindos da API. Cache curto (20 s); `nonce` permite forçar atualização. Exceções não são cacheadas."""
    return api_client.obter_emissoes(base_url)


def emissoes_para_graficos():
    """
    Fonte principal dos gráficos. Devolve (DataFrame, fonte, aviso):
      fonte = "API" (consumindo GET /emissoes) ou "LOCAL" (arquivos); aviso = motivo do fallback, se houve.
    Uploads feitos nesta sessão são sempre somados.
    """
    aviso = None
    fonte = "LOCAL"
    df = None
    if st.session_state.get("fonte_dados", "API") == "API":
        try:
            df = _emissoes_api(st.session_state["api_url"], st.session_state["api_nonce"])
            fonte = "API"
        except api_client.ApiIndisponivel as exc:
            aviso = f"{exc} Exibindo os arquivos locais."
        except api_client.ApiErro as exc:
            aviso = f"A API devolveu um erro ({exc.codigo}: {exc.mensagem}). Exibindo os arquivos locais."
        if df is not None and df.empty:
            df = None
            aviso = "A API não retornou registros. Exibindo os arquivos locais."
            fonte = "LOCAL"
    if df is None:
        df = emissoes_base_api()
    up = st.session_state.get("df_uploads")
    if up is not None and not up.empty:
        df = pd.concat([df, up], ignore_index=True)
    return df, fonte, aviso


@st.cache_data(show_spinner=False)
def gerar_nuvem(texto: str) -> Optional[np.ndarray]:
    if not WORDCLOUD_OK or not texto.strip():
        return None
    wc = WordCloud(width=900, height=420, background_color="white", colormap="Greens",
                   stopwords=STOPWORDS_PT, collocations=False, max_words=80).generate(texto)
    return wc.to_array()


# ------------------------------------------------------------------ apresentação
def fmt_num(valor: float, casas: int = 1) -> str:
    """Formato brasileiro: 1.234,5"""
    s = f"{valor:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def painel_diagnostico() -> None:
    with st.expander("🔍 Diagnóstico de caminhos (debug)"):
        st.caption("Se algum dado não aparecer, confira se os caminhos abaixo apontam para o lugar certo.")
        itens = [
            ("Raiz do projeto", paths.raiz_projeto()),
            ("Pasta Data", paths.data_dir()),
            ("Emissões (base)", paths.caminho_emissoes_base()),
            ("Emissões (enviadas via API)", paths.caminho_emissoes_enviadas()),
            ("Notícias", paths.caminho_noticias()),
            ("ODS", paths.caminho_ods()),
            ("Corpus LLM", paths.caminho_corpus()),
            ("Contexto de relatório", paths.caminho_contexto_relatorio()),
        ]
        st.dataframe(pd.DataFrame([{"item": n, "caminho": str(p), "existe": p.exists()} for n, p in itens]),
                     hide_index=True)
