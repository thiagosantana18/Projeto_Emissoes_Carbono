"""
Aplicação demo (v2) — Monitoramento e Previsão de Emissões de Carbono Corporativas
Pilar ESG: Ambiental | ODS 12 e 13 | Metodologia: CRISP-DM / TDSP

Novidades desta etapa:
    - Interface organizada em abas, com navegação intuitiva.
    - Cache (st.cache_data) para carregar dados coletados via scraping.
    - Estado de sessão (st.session_state) para manter filtros, o histórico
      de uploads e o dataset combinado entre interações do usuário.
    - Nuvem de palavras e estatísticas básicas a partir de conteúdo coletado
      via BeautifulSoup (ver Code/data_acquisition/).
    - Upload de CSV pelo usuário, com validação e mesclagem ao dataset
      já exibido, além de botão de download do resultado consolidado.

Como executar:
    pip install -r requirements.txt
    streamlit run app.py
"""

from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

try:
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt

    WORDCLOUD_DISPONIVEL = True
except ImportError:
    WORDCLOUD_DISPONIVEL = False

# ---------------------------------------------------------------------------
# Configuração geral da página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Emissões de Carbono Corporativas | ESG",
    page_icon="🌱",
    layout="wide",
)

PRIMARY_COLOR = "#1F6F50"
def localizar_raiz_projeto() -> Path:
    """
    Localiza a raiz do projeto (a pasta que contém Data/) subindo a partir
    da localização deste próprio arquivo.

    Por quê: este app.py pode viver em dois lugares diferentes dependendo
    de como o projeto foi organizado — na raiz do projeto (ao lado de
    Data/) ou dentro de App/dashboard/ (padrão TDSP, duas pastas acima de
    Data/). Em vez de fixar o número de níveis (o que já causou bugs de
    'arquivo não encontrado' ao mover o arquivo de um lugar para o outro),
    procuramos a pasta Data/ subindo a árvore de diretórios e usamos o
    primeiro ponto em que ela aparecer.
    """
    aqui = Path(__file__).resolve().parent
    candidatos = [aqui] + list(aqui.parents)
    for candidato in candidatos:
        if (candidato / "Data").is_dir():
            return candidato
    # Fallback: nenhuma pasta Data/ encontrada acima — assume que está
    # ao lado do próprio arquivo (comportamento anterior).
    return aqui


PROJECT_ROOT = localizar_raiz_projeto()
DATA_RAW_DIR = PROJECT_ROOT / "Data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "Data" / "processed"

STOPWORDS_PT = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "um", "uma",
    "para", "com", "por", "no", "na", "nos", "nas", "que", "se", "sua", "seu",
    "suas", "seus", "é", "ao", "aos", "à", "às", "entre", "sobre", "mais",
    "como", "já", "até", "diz", "ser", "foi", "são", "pelo", "pela", "esse",
    "essa", "este", "esta", "isso", "ou", "não", "também", "vai", "após",
}


# ---------------------------------------------------------------------------
# Estado de sessão — inicialização
# ---------------------------------------------------------------------------
def inicializar_estado():
    """Garante que as chaves usadas em st.session_state existam desde o início."""
    defaults = {
        "dataset_combinado": None,       # dataset de emissões + uploads do usuário
        "historico_uploads": [],         # nomes/registro dos arquivos enviados
        "unidades_filtro": None,         # última seleção de filtro (persistida)
        "atividades_filtro": None,
        "contador_geracoes_nuvem": 0,    # quantas vezes a nuvem foi gerada
        "ultima_atualizacao": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


inicializar_estado()


# ---------------------------------------------------------------------------
# Funções de carregamento de dados (com cache)
# ---------------------------------------------------------------------------
@st.cache_data
def carregar_dados_emissoes() -> pd.DataFrame:
    """
    Carrega a amostra processada de dados de atividade/emissão
    (gerada em Code/data_acquisition e salva em Data/processed).
    Cai em geração sintética on-the-fly caso o arquivo não exista.
    """
    caminho = DATA_PROCESSED_DIR / "amostra_emissoes.csv"
    if caminho.exists():
        return pd.read_csv(caminho)

    # fallback: gera na hora (mesma lógica do script de amostra)
    rng = np.random.default_rng(42)
    unidades = ["Matriz - SP", "Filial - RJ", "Filial - MG", "CD - PR"]
    setores = ["Administrativo", "Logística", "Produção"]
    tipos_atividade = [
        ("Eletricidade (rede)", "kWh", 0.0817, "Climatiq API"),
        ("Diesel (frota)", "litro", 2.6712, "EPA"),
        ("Gasolina (frota leve)", "litro", 2.2120, "EPA"),
        ("Gás natural (caldeira)", "m3", 1.9700, "DEFRA"),
    ]
    meses = pd.date_range("2025-01-01", periods=12, freq="MS")
    linhas = []
    for mes in meses:
        unidade = rng.choice(unidades)
        setor = rng.choice(setores)
        atividade, unidade_medida, fator, fonte = tipos_atividade[
            rng.integers(0, len(tipos_atividade))
        ]
        quantidade = round(float(rng.uniform(500, 8000)), 1)
        linhas.append(
            {
                "mes_referencia": mes.strftime("%Y-%m"),
                "unidade": unidade,
                "setor": setor,
                "tipo_atividade": atividade,
                "quantidade": quantidade,
                "unidade_medida": unidade_medida,
                "fator_emissao_kgco2e": fator,
                "emissao_kgco2e": round(quantidade * fator, 2),
                "fonte_fator": fonte,
            }
        )
    return pd.DataFrame(linhas)


@st.cache_data
def carregar_noticias() -> pd.DataFrame:
    """
    Carrega as manchetes coletadas via scraping (Data/raw/noticias_esg.csv).

    Defensivo quanto ao schema: o site de origem nem sempre expõe a data de
    publicação na página de listagem (ver extrair_data_publicacao() no
    script de coleta), então a coluna 'data_publicacao' pode não existir ou
    vir vazia em algumas linhas. Aqui garantimos que a coluna sempre exista,
    preenchendo com 'data_coleta' quando faltar — assim o restante do app
    nunca precisa lidar com KeyError.
    """
    colunas_esperadas = ["titulo", "data_publicacao", "url_materia", "data_coleta"]
    caminho = DATA_RAW_DIR / "noticias_esg.csv"

    if not caminho.exists():
        return pd.DataFrame(columns=colunas_esperadas)

    df = pd.read_csv(caminho)

    if "data_publicacao" not in df.columns:
        df["data_publicacao"] = pd.NA

    if "data_coleta" in df.columns:
        df["data_publicacao"] = df["data_publicacao"].fillna(df["data_coleta"])

    for coluna in colunas_esperadas:
        if coluna not in df.columns:
            df[coluna] = pd.NA

    return df[colunas_esperadas]


@st.cache_data
def carregar_conteudo_ods() -> pd.DataFrame:
    """Carrega os trechos sobre ODS 12/13 coletados via scraping."""
    caminho = DATA_RAW_DIR / "ods_conteudo.csv"
    if caminho.exists():
        return pd.read_csv(caminho)
    return pd.DataFrame(columns=["ods", "titulo_pagina", "trecho", "url_fonte", "data_coleta"])


@st.cache_data
def calcular_frequencia_palavras(textos: tuple, top_n: int = 20) -> pd.DataFrame:
    """
    Calcula a frequência de palavras em uma coleção de textos, ignorando
    stopwords em português e pontuação. Cacheado porque é reprocessado
    toda vez que os filtros de notícia mudam.
    """
    import re
    from collections import Counter

    contador = Counter()
    for texto in textos:
        palavras = re.findall(r"[a-zà-ú]+", texto.lower())
        palavras = [p for p in palavras if p not in STOPWORDS_PT and len(p) > 2]
        contador.update(palavras)

    mais_comuns = contador.most_common(top_n)
    return pd.DataFrame(mais_comuns, columns=["palavra", "frequencia"])


def gerar_nuvem_palavras(texto_completo: str):
    """Gera a figura matplotlib da nuvem de palavras (ou None se indisponível)."""
    if not WORDCLOUD_DISPONIVEL or not texto_completo.strip():
        return None

    wc = WordCloud(
        width=900,
        height=450,
        background_color="white",
        colormap="Greens",
        stopwords=STOPWORDS_PT,
        collocations=False,
    ).generate(texto_completo)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout(pad=0)
    return fig


# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div style="padding: 1.2rem 1.5rem; border-radius: 10px;
                background-color: {PRIMARY_COLOR}; margin-bottom: 1rem;">
        <h1 style="color: white; margin-bottom: 0.2rem;">
            🌱 Monitoramento e Previsão de Emissões de Carbono Corporativas
        </h1>
    </div>
    """,
    unsafe_allow_html=True,
)

aba_visao_geral, aba_noticias, aba_dados, aba_upload = st.tabs(
    ["🏠 Visão Geral", "📰 Notícias & Nuvem de Palavras", "📊 Dados do Projeto", "📤 Upload & Download"]
)

# ---------------------------------------------------------------------------
# ABA 1 — Visão Geral
# ---------------------------------------------------------------------------
with aba_visao_geral:
    col_prob, col_obj = st.columns(2)

    with col_prob:
        st.subheader("📌 O problema de negócio")
        st.markdown(
            """
            Grande parte das empresas — especialmente pequenas e médias — não possui
            **visibilidade contínua** sobre sua pegada de carbono (Escopo 1, 2 e 3).
            Os relatórios costumam ser produzidos **anualmente e de forma manual**, o que:

            - dificulta decisões tempestivas de redução de emissões;
            - eleva o custo de conformidade com frameworks como **GRI** e **CDP**;
            - reduz a credibilidade dos indicadores ESG reportados.
            """
        )

    with col_obj:
        st.subheader("🎯 Objetivos do projeto")
        st.markdown(
            """
            1. Coletar dados de atividade e fatores de emissão via **APIs** e **web scraping**;
            2. Calcular e **prever** a trajetória de emissões de carbono;
            3. Identificar as **principais fontes de emissão**;
            4. Apresentar tudo em um **dashboard interativo**, com cache e estado de sessão;
            5. Permitir que o usuário **complemente os dados** via upload de CSV.
            """
        )

    st.info(
        "🎯 **Meta de sucesso:** prever as emissões mensais com MAPE < 15%, "
        "reduzindo em pelo menos 80% o tempo de elaboração do relatório ESG.",
        icon="🎯",
    )

    st.subheader("🌍 Por que ODS 12 e ODS 13?")
    col_ods12, col_ods13 = st.columns(2)
    with col_ods12:
        st.markdown(
            """
            **ODS 12 — Consumo e produção responsáveis**
            A pegada de carbono de uma PME nasce diretamente dos seus padrões de
            consumo de energia, combustível e insumos — medir e reduzir esse
            consumo é a aplicação prática da meta do ODS 12 de alcançar uso
            eficiente dos recursos naturais e de levar as empresas a integrar
            dados de sustentabilidade em seus relatórios.
            """
        )
    with col_ods13:
        st.markdown(
            """
            **ODS 13 — Ação contra a mudança global do clima**
            Como a maior parte das emissões de uma PME vem da queima de
            combustíveis e do consumo de eletricidade, prever e comunicar essa
            trajetória de emissões é uma forma concreta de colocar em prática
            a meta do ODS 13 de integrar medidas de mudança do clima ao
            planejamento e à gestão das organizações.
            """
        )

    st.divider()
    st.subheader("🔗 Links úteis e fontes de inspiração")

    links = [
        {"titulo": "Climatiq API", "url": "https://www.climatiq.io/", "descricao": "Fatores de emissão de CO2e usados na coleta de dados."},
        {"titulo": "SEEG", "url": "https://seeg.eco.br/", "descricao": "Séries históricas de emissões setoriais no Brasil."},
        {"titulo": "GHG Protocol", "url": "https://ghgprotocol.org/", "descricao": "Padrão internacional de contabilização de emissões."},
        {"titulo": "CDP", "url": "https://www.cdp.net/", "descricao": "Plataforma global de divulgação de dados ambientais."},
        {"titulo": "GRI Standards", "url": "https://www.globalreporting.org/", "descricao": "Normas de relato de sustentabilidade."},
        {"titulo": "ODS 13 (ONU Brasil)", "url": "https://brasil.un.org/pt-br/sdgs/13", "descricao": "Página oficial do ODS 13 na Agenda 2030."},
        {"titulo": "ODS 12 (ONU Brasil)", "url": "https://brasil.un.org/pt-br/sdgs/12", "descricao": "Página oficial do ODS 12 na Agenda 2030."},
        {"titulo": "Microsoft TDSP", "url": "https://learn.microsoft.com/en-us/azure/architecture/data-science-process/overview", "descricao": "Metodologia usada para organizar o projeto."},
    ]
    link_cols = st.columns(2)
    for i, link in enumerate(links):
        with link_cols[i % 2]:
            st.markdown(
                f"""
                <div style="border: 1px solid #DDDDDD; border-radius: 8px;
                            padding: 0.7rem 1rem; margin-bottom: 0.7rem;">
                    <a href="{link['url']}" target="_blank"
                       style="font-weight: 600; color: {PRIMARY_COLOR}; text-decoration: none;">
                        {link['titulo']} ↗
                    </a>
                    <p style="margin: 0.2rem 0 0 0; font-size: 0.88rem; color: #555555;">
                        {link['descricao']}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# ABA 2 — Notícias & Nuvem de Palavras
# ---------------------------------------------------------------------------
with aba_noticias:
    st.subheader("📰 Notícias sobre ESG e pegada de carbono")
    st.caption(
        "Manchetes coletadas via *web scraping* (BeautifulSoup) de portais de notícias "
        "sobre ESG, respeitando o `robots.txt` de cada fonte. "
        "Ver `Code/data_acquisition/scrape_noticias_esg.py`."
    )

    df_noticias = carregar_noticias()
    df_ods = carregar_conteudo_ods()

    if df_noticias.empty:
        st.warning(
            f"Nenhuma notícia encontrada em `{DATA_RAW_DIR / 'noticias_esg.csv'}`. "
            "Rode o script de coleta primeiro (verifique se este é o caminho correto "
            "— veja o diagnóstico de caminhos no rodapé da página)."
        )
    else:
        # Conversão defensiva: o site de origem pode não expor data de
        # publicação, e o que sobra (data_coleta) pode vir em formatos
        # mistos — por isso usamos errors="coerce" em vez de deixar
        # pd.to_datetime lançar exceção e derrubar o app.
        datas_validas = pd.to_datetime(
            df_noticias["data_publicacao"], errors="coerce", format="mixed", dayfirst=True
        )

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Notícias coletadas", len(df_noticias))
        col_b.metric(
            "Período mais recente",
            datas_validas.max().strftime("%d/%m/%Y") if datas_validas.notna().any() else "N/D",
        )
        col_c.metric("Fonte", df_noticias["url_materia"].iloc[0].split("/")[2] if len(df_noticias) else "-")

        df_noticias_ordenado = df_noticias.assign(_data_ord=datas_validas).sort_values(
            "_data_ord", ascending=False, na_position="last"
        ).drop(columns="_data_ord")

        st.dataframe(
            df_noticias_ordenado,
            width='stretch',
            hide_index=True,
            column_config={
                "titulo": "Manchete",
                "data_publicacao": "Data",
                "url_materia": st.column_config.LinkColumn("Link"),
                "data_coleta": "Coletado em",
            },
        )

        st.divider()
        st.subheader("☁️ Nuvem de palavras")

        fonte_nuvem = st.radio(
            "Gerar nuvem de palavras a partir de:",
            options=["Manchetes de notícias", "Conteúdo sobre ODS 12/13"],
            horizontal=True,
            key="fonte_nuvem_radio",
        )

        if fonte_nuvem == "Manchetes de notícias":
            texto_completo = " ".join(df_noticias["titulo"].astype(str))
            textos_tupla = tuple(df_noticias["titulo"].astype(str))
        else:
            texto_completo = " ".join(df_ods["trecho"].astype(str)) if not df_ods.empty else ""
            textos_tupla = tuple(df_ods["trecho"].astype(str)) if not df_ods.empty else tuple()

        if st.button("🔄 Gerar / atualizar nuvem de palavras"):
            st.session_state["contador_geracoes_nuvem"] += 1

        st.caption(
            f"Nuvem gerada {st.session_state['contador_geracoes_nuvem']}x nesta sessão "
            "(contador mantido via `st.session_state`)."
        )

        if texto_completo:
            fig = gerar_nuvem_palavras(texto_completo)
            if fig is not None:
                st.pyplot(fig)
            else:
                st.info(
                    "📦 Pacote `wordcloud` não está instalado neste ambiente. "
                    "Rode `pip install wordcloud` (já incluso no requirements.txt) para "
                    "ver a nuvem de palavras. Exibindo estatística de frequência como alternativa:"
                )

            st.markdown("**Estatísticas básicas — top 15 palavras mais frequentes**")
            df_freq = calcular_frequencia_palavras(textos_tupla, top_n=15)
            col_tabela, col_grafico = st.columns([1, 1.4])
            with col_tabela:
                st.dataframe(df_freq, width='stretch', hide_index=True)
            with col_grafico:
                st.bar_chart(df_freq.set_index("palavra"))
        else:
            st.info("Sem texto disponível para gerar a nuvem de palavras.")

# ---------------------------------------------------------------------------
# ABA 3 — Dados do Projeto
# ---------------------------------------------------------------------------
with aba_dados:
    st.subheader("📊 Amostra dos dados de atividade e emissão")
    st.caption(
        "Dados combinando consumo simulado por unidade/setor com fatores de "
        "emissão (Climatiq/EPA/DEFRA), conforme descrito no Data Summary Report."
    )

    df_base = carregar_dados_emissoes()

    # Se já existe um dataset combinado (com uploads) na sessão, usa ele;
    # caso contrário, inicializa com os dados base.
    if st.session_state["dataset_combinado"] is None:
        st.session_state["dataset_combinado"] = df_base.copy()

    df_atual = st.session_state["dataset_combinado"]

    unidades_disponiveis = sorted(df_atual["unidade"].dropna().unique())
    atividades_disponiveis = sorted(df_atual["tipo_atividade"].dropna().unique())

    # Filtros com persistência via session_state
    default_unidades = st.session_state["unidades_filtro"] or unidades_disponiveis
    default_atividades = st.session_state["atividades_filtro"] or atividades_disponiveis

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        unidades_selecionadas = st.multiselect(
            "Filtrar por unidade", options=unidades_disponiveis, default=default_unidades
        )
    with col_f2:
        atividades_selecionadas = st.multiselect(
            "Filtrar por tipo de atividade", options=atividades_disponiveis, default=default_atividades
        )

    # Persiste a seleção atual no estado de sessão
    st.session_state["unidades_filtro"] = unidades_selecionadas
    st.session_state["atividades_filtro"] = atividades_selecionadas

    df_filtrado = df_atual[
        df_atual["unidade"].isin(unidades_selecionadas)
        & df_atual["tipo_atividade"].isin(atividades_selecionadas)
    ]

    st.dataframe(
        df_filtrado,
        width='stretch',
        hide_index=True,
        column_config={
            "mes_referencia": "Mês",
            "unidade": "Unidade",
            "setor": "Setor",
            "tipo_atividade": "Tipo de atividade",
            "quantidade": st.column_config.NumberColumn("Quantidade", format="%.1f"),
            "unidade_medida": "Un. de medida",
            "fator_emissao_kgco2e": st.column_config.NumberColumn("Fator (kgCO2e/un.)", format="%.4f"),
            "emissao_kgco2e": st.column_config.NumberColumn("Emissão (kgCO2e)", format="%.2f"),
            "fonte_fator": "Fonte do fator",
        },
    )

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Registros na amostra", len(df_filtrado))
    col_m2.metric("Emissão total (kgCO2e)", f"{df_filtrado['emissao_kgco2e'].sum():,.0f}")
    col_m3.metric("Unidades representadas", df_filtrado["unidade"].nunique())

    if st.session_state["historico_uploads"]:
        st.success(
            f"✅ Dataset atual inclui {len(st.session_state['historico_uploads'])} "
            f"arquivo(s) enviado(s) pelo usuário: {', '.join(st.session_state['historico_uploads'])}"
        )

# ---------------------------------------------------------------------------
# ABA 4 — Upload & Download
# ---------------------------------------------------------------------------
with aba_upload:
    st.subheader("📤 Enviar dados complementares (CSV)")
    st.markdown(
        """
        Envie um arquivo CSV com o **mesmo formato** da amostra de dados
        (colunas: `mes_referencia`, `unidade`, `setor`, `tipo_atividade`,
        `quantidade`, `unidade_medida`, `fator_emissao_kgco2e`,
        `emissao_kgco2e`, `fonte_fator`) para complementar a base exibida na
        aba **Dados do Projeto**.
        """
    )

    arquivo_enviado = st.file_uploader("Selecione um arquivo CSV", type=["csv"])

    colunas_esperadas = {
        "mes_referencia", "unidade", "setor", "tipo_atividade", "quantidade",
        "unidade_medida", "fator_emissao_kgco2e", "emissao_kgco2e", "fonte_fator",
    }

    if arquivo_enviado is not None:
        try:
            df_novo = pd.read_csv(arquivo_enviado)
        except Exception as exc:
            st.error(f"Não foi possível ler o arquivo: {exc}")
            df_novo = None

        if df_novo is not None:
            colunas_arquivo = set(df_novo.columns)
            faltantes = colunas_esperadas - colunas_arquivo

            if faltantes:
                st.error(
                    "O arquivo enviado não tem o formato esperado. "
                    f"Colunas faltando: {', '.join(sorted(faltantes))}"
                )
            else:
                st.success(f"Arquivo lido com sucesso: {len(df_novo)} linha(s).")
                st.dataframe(df_novo.head(10), width='stretch', hide_index=True)

                if st.button("➕ Adicionar estes dados ao dataset do projeto"):
                    base_atual = st.session_state["dataset_combinado"]
                    st.session_state["dataset_combinado"] = pd.concat(
                        [base_atual, df_novo], ignore_index=True
                    )
                    st.session_state["historico_uploads"].append(arquivo_enviado.name)
                    st.session_state["ultima_atualizacao"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    st.success(
                        "Dados adicionados! Vá até a aba 'Dados do Projeto' para ver o "
                        "dataset combinado atualizado."
                    )

    st.divider()
    st.subheader("📥 Baixar dataset consolidado")

    df_para_download = st.session_state["dataset_combinado"]
    if df_para_download is None:
        df_para_download = carregar_dados_emissoes()

    st.caption(
        f"O dataset atual tem {len(df_para_download)} linha(s)"
        + (
            f" — última atualização em {st.session_state['ultima_atualizacao']}."
            if st.session_state["ultima_atualizacao"]
            else " (dados originais, sem uploads adicionados nesta sessão)."
        )
    )

    csv_buffer = StringIO()
    df_para_download.to_csv(csv_buffer, index=False)

    st.download_button(
        label="⬇️ Baixar CSV consolidado",
        data=csv_buffer.getvalue(),
        file_name=f"emissoes_consolidado_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    if st.session_state["historico_uploads"]:
        st.markdown("**Histórico de uploads nesta sessão:**")
        for nome_arquivo in st.session_state["historico_uploads"]:
            st.markdown(f"- {nome_arquivo}")

    if st.button("🗑️ Limpar dados enviados e reiniciar dataset"):
        st.session_state["dataset_combinado"] = carregar_dados_emissoes().copy()
        st.session_state["historico_uploads"] = []
        st.session_state["ultima_atualizacao"] = None
        st.rerun()

# ---------------------------------------------------------------------------
# Rodapé
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Projeto desenvolvido com Python e Streamlit · Metodologia CRISP-DM / TDSP · "
    "Alinhado aos ODS 12 e 13 da Agenda 2030 · Cache e estado de sessão habilitados"
)

with st.expander("🔍 Diagnóstico de caminhos (debug)"):
    st.markdown(
        "Se uma aba disser que não encontrou dados mesmo com os arquivos "
        "preenchidos, confira aqui se os caminhos abaixo apontam para o "
        "lugar certo do seu projeto."
    )
    diagnostico = pd.DataFrame(
        [
            {"item": "Localização deste app.py", "caminho": str(Path(__file__).resolve()), "existe": True},
            {"item": "Raiz do projeto detectada", "caminho": str(PROJECT_ROOT), "existe": PROJECT_ROOT.is_dir()},
            {"item": "Pasta Data/raw", "caminho": str(DATA_RAW_DIR), "existe": DATA_RAW_DIR.is_dir()},
            {"item": "noticias_esg.csv", "caminho": str(DATA_RAW_DIR / "noticias_esg.csv"), "existe": (DATA_RAW_DIR / "noticias_esg.csv").is_file()},
            {"item": "ods_conteudo.csv", "caminho": str(DATA_RAW_DIR / "ods_conteudo.csv"), "existe": (DATA_RAW_DIR / "ods_conteudo.csv").is_file()},
            {"item": "Pasta Data/processed", "caminho": str(DATA_PROCESSED_DIR), "existe": DATA_PROCESSED_DIR.is_dir()},
            {"item": "amostra_emissoes.csv", "caminho": str(DATA_PROCESSED_DIR / "amostra_emissoes.csv"), "existe": (DATA_PROCESSED_DIR / "amostra_emissoes.csv").is_file()},
        ]
    )
    st.dataframe(diagnostico, width='stretch', hide_index=True)
