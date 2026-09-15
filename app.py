"""
Aplicação demo — Monitoramento e Previsão de Emissões de Carbono Corporativas
Pilar ESG: Ambiental | ODS 12 e 13 | Metodologia: CRISP-DM / TDSP
"""

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Configuração geral da página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Emissões de Carbono Corporativas | ESG",
    page_icon="🌱",
    layout="wide",
)

PRIMARY_COLOR = "#1F6F50"

# ---------------------------------------------------------------------------
# Geração de dados de amostra (simulados)
# ---------------------------------------------------------------------------

@st.cache_data
def gerar_dados_amostra(n_linhas: int = 12, seed: int = 42) -> pd.DataFrame:
    """
    Gera uma amostra simulada dos dados que serão utilizados ao longo do
    projeto: dados de atividade (consumo) combinados com fatores de emissão,
    representando o formato final esperado após a integração das fontes
    descritas no Data Summary Report (Climatiq API, EPA/DEFRA, dados
    internos simulados).
    """
    rng = np.random.default_rng(seed)

    unidades = ["Matriz - SP", "Filial - RJ", "Filial - MG", "CD - PR"]
    setores = ["Administrativo", "Logística", "Produção"]
    tipos_atividade = [
        ("Eletricidade (rede)", "kWh", 0.0817, "Climatiq API"),
        ("Diesel (frota)", "litro", 2.6712, "EPA"),
        ("Gasolina (frota leve)", "litro", 2.2120, "EPA"),
        ("Gás natural (caldeira)", "m3", 1.9700, "DEFRA"),
    ]
    meses = pd.date_range("2025-01-01", periods=n_linhas, freq="MS")

    linhas = []
    for mes in meses:
        unidade = rng.choice(unidades)
        setor = rng.choice(setores)
        atividade, unidade_medida, fator, fonte = tipos_atividade[
            rng.integers(0, len(tipos_atividade))
        ]
        quantidade = round(float(rng.uniform(500, 8000)), 1)
        emissao = round(quantidade * fator, 2)

        linhas.append(
            {
                "mes_referencia": mes.strftime("%Y-%m"),
                "unidade": unidade,
                "setor": setor,
                "tipo_atividade": atividade,
                "quantidade": quantidade,
                "unidade_medida": unidade_medida,
                "fator_emissao_kgco2e": fator,
                "emissao_kgco2e": emissao,
                "fonte_fator": fonte,
            }
        )

    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Cabeçalho / Título do projeto
# ---------------------------------------------------------------------------

st.markdown(
    f"""
    <div style="padding: 1.2rem 1.5rem; border-radius: 10px;
                background-color: {PRIMARY_COLOR}; margin-bottom: 1.5rem;">
        <h1 style="color: white; margin-bottom: 0.2rem;">
            🌱 Monitoramento e Previsão de Emissões de Carbono Corporativas
        </h1>
        <p style="color: #E8F3EE; font-size: 1.05rem; margin-bottom: 0;">
            Um protótipo de IA aplicada ao pilar Ambiental do ESG — CRISP-DM · TDSP · ODS 12 e 13
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    "Demo do projeto — os dados exibidos abaixo são simulados e servem apenas "
    "para ilustrar a estrutura final da solução."
)

# ---------------------------------------------------------------------------
# Descrição do problema de negócio e objetivos
# ---------------------------------------------------------------------------

st.header("📌 O problema de negócio")

col_prob, col_obj = st.columns(2)

with col_prob:
    st.subheader("Contexto")
    st.markdown(
        """
        Grande parte das empresas — especialmente pequenas e médias — não possui
        **visibilidade contínua** sobre sua pegada de carbono (Escopo 1, 2 e 3).
        Os relatórios de emissões costumam ser produzidos **anualmente e de forma
        manual**, o que:

        - dificulta decisões tempestivas de redução de emissões;
        - eleva o custo e o esforço de conformidade com frameworks como **GRI** e **CDP**;
        - reduz a credibilidade e a comparabilidade dos indicadores ESG reportados.
        """
    )

with col_obj:
    st.subheader("Objetivo do projeto")
    st.markdown(
        """
        Desenvolver uma aplicação em **Python** que:

        1. colete dados de atividade e fatores de emissão via **APIs**;
        2. calcule e **preveja** a trajetória de emissões de carbono da organização;
        3. identifique as **principais fontes de emissão** (explicabilidade);
        4. apresente tudo em um **dashboard interativo (Streamlit)**, com
           simulação de cenários *what-if*;
        5. gere automaticamente um **relatório narrativo** (estilo GRI/CDP)
           com apoio de **IA generativa**.
        """
    )

st.info(
    "🎯 **Meta de sucesso:** prever as emissões mensais com erro percentual "
    "médio (MAPE) inferior a 15%, reduzindo em pelo menos 80% o tempo de "
    "elaboração do relatório ESG.",
    icon="🎯",
)

st.divider()

# ---------------------------------------------------------------------------
# Links úteis / fontes de inspiração
# ---------------------------------------------------------------------------

st.header("🔗 Links úteis e fontes de inspiração")

links = [
    {
        "titulo": "Climatiq API",
        "descricao": "API de fatores de emissão de CO2e usada na coleta de dados do projeto.",
        "url": "https://www.climatiq.io/",
    },
    {
        "titulo": "SEEG — Sistema de Estimativas de Emissões de GEE",
        "descricao": "Séries históricas de emissões setoriais no Brasil, usadas como benchmark.",
        "url": "https://seeg.eco.br/",
    },
    {
        "titulo": "GHG Protocol",
        "descricao": "Padrão internacional de contabilização de emissões (Escopo 1, 2 e 3).",
        "url": "https://ghgprotocol.org/",
    },
    {
        "titulo": "CDP — Disclosure Insight Action",
        "descricao": "Plataforma global de divulgação de dados ambientais corporativos.",
        "url": "https://www.cdp.net/",
    },
    {
        "titulo": "GRI Standards",
        "descricao": "Normas de relato de sustentabilidade usadas como referência para o relatório gerado por IA.",
        "url": "https://www.globalreporting.org/",
    },
    {
        "titulo": "ODS 13 — Ação contra a mudança global do clima",
        "descricao": "Objetivo de Desenvolvimento Sustentável (Agenda 2030) ao qual o projeto está alinhado.",
        "url": "https://brasil.un.org/pt-br/sdgs/13",
    },
    {
        "titulo": "ODS 12 — Consumo e produção responsáveis",
        "descricao": "Segundo ODS de referência do projeto (Agenda 2030).",
        "url": "https://brasil.un.org/pt-br/sdgs/12",
    },
    {
        "titulo": "Microsoft TDSP",
        "descricao": "Team Data Science Process — metodologia usada para organizar o ciclo de vida do projeto.",
        "url": "https://learn.microsoft.com/en-us/azure/architecture/data-science-process/overview",
    },
    {
        "titulo": "CRISP-DM",
        "descricao": "Cross Industry Standard Process for Data Mining — metodologia analítica do projeto.",
        "url": "https://www.datascience-pm.com/crisp-dm-2/",
    },
    {
        "titulo": "Streamlit Docs",
        "descricao": "Documentação oficial do framework usado para construir o dashboard interativo.",
        "url": "https://docs.streamlit.io/",
    },
]

link_cols = st.columns(2)
for i, link in enumerate(links):
    with link_cols[i % 2]:
        st.markdown(
            f"""
            <div style="border: 1px solid #DDDDDD; border-radius: 8px;
                        padding: 0.8rem 1rem; margin-bottom: 0.8rem;">
                <a href="{link['url']}" target="_blank"
                   style="font-weight: 600; font-size: 1.02rem; color: {PRIMARY_COLOR};
                          text-decoration: none;">
                    {link['titulo']} ↗
                </a>
                <p style="margin: 0.3rem 0 0 0; font-size: 0.9rem; color: #555555;">
                    {link['descricao']}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# Amostra dos dados
# ---------------------------------------------------------------------------

st.header("📊 Amostra dos dados do projeto")

st.markdown(
    """
    Abaixo, uma amostra do formato de dados que será utilizado ao longo do
    projeto — combinando **dados de atividade** (consumo simulado por
    unidade/setor) com os **fatores de emissão** obtidos via API, conforme
    descrito no *Data Summary Report*.
    """
)

df_amostra = gerar_dados_amostra()

col_filtro1, col_filtro2 = st.columns([1, 1])
with col_filtro1:
    unidades_selecionadas = st.multiselect(
        "Filtrar por unidade",
        options=sorted(df_amostra["unidade"].unique()),
        default=sorted(df_amostra["unidade"].unique()),
    )
with col_filtro2:
    atividades_selecionadas = st.multiselect(
        "Filtrar por tipo de atividade",
        options=sorted(df_amostra["tipo_atividade"].unique()),
        default=sorted(df_amostra["tipo_atividade"].unique()),
    )

df_filtrado = df_amostra[
    df_amostra["unidade"].isin(unidades_selecionadas)
    & df_amostra["tipo_atividade"].isin(atividades_selecionadas)
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
        "fator_emissao_kgco2e": st.column_config.NumberColumn(
            "Fator (kgCO2e/un.)", format="%.4f"
        ),
        "emissao_kgco2e": st.column_config.NumberColumn(
            "Emissão (kgCO2e)", format="%.2f"
        ),
        "fonte_fator": "Fonte do fator",
    },
)

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Registros na amostra", len(df_filtrado))
col_m2.metric(
    "Emissão total (kgCO2e)", f"{df_filtrado['emissao_kgco2e'].sum():,.0f}"
)
col_m3.metric("Unidades representadas", df_filtrado["unidade"].nunique())

st.caption(
    "⚠️ Dados meramente ilustrativos, gerados de forma sintética para fins "
    "de demonstração da estrutura da aplicação. Os fatores de emissão "
    "utilizados são valores de referência simplificados."
)

# ---------------------------------------------------------------------------
# Rodapé
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "Projeto desenvolvido com Python e Streamlit · Metodologia CRISP-DM / TDSP · "
    "Alinhado aos ODS 12 e 13 da Agenda 2030"
)
