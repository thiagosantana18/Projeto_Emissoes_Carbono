import streamlit as st

from ui_helpers import corpus, emissoes_consolidadas, fmt_num, noticias, painel_diagnostico

st.title("🌱 Monitoramento e Previsão de Emissões de Carbono Corporativas")
st.caption("Pilar Ambiental (E) do ESG · ODS 12 e 13 · CRISP-DM / TDSP · Versão final — da coleta de dados aos insights com IA")

df = emissoes_consolidadas()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Registros de emissão", fmt_num(len(df), 0))
c2.metric("Emissão total (tCO₂e)", fmt_num(df["emissao_kgco2e"].sum() / 1000) if not df.empty else "—")
c3.metric("Manchetes coletadas", fmt_num(len(noticias()), 0))
c4.metric("Documentos no corpus", fmt_num(len(corpus()), 0))
st.caption("Os dados de atividade são **sintéticos** (demonstração); os textos de notícias e ODS são **reais**, coletados por scraping. Veja a página *Ciclo de dados*.")

st.divider()
col_p, col_o = st.columns(2)
with col_p:
    st.subheader("📌 O problema de negócio")
    st.markdown(
        """
Pequenas e médias empresas (PMEs) não têm **visibilidade contínua** da sua pegada de carbono. O relatório é **anual, manual e isolado em planilhas**, o que:

- impede decisões tempestivas de redução de emissões;
- encarece a conformidade com **GRI** e **CDP**;
- deixa o gestor sem tempo para **ler e interpretar** o volume de informação ESG (relatórios, notícias, metas dos ODS).
        """
    )
with col_o:
    st.subheader("🎯 O que a solução entrega")
    st.markdown(
        """
1. **Coleta e integra** dados (scraping, API, uploads) com validação e rastreabilidade;
2. **Mostra** emissões, qualidade dos dados e notícias em um painel interativo;
3. **Prevê** as emissões dos próximos meses, com erro medido (backtest);
4. **Resume** relatórios e notícias, **responde perguntas** e **gera recomendações** com IA — com números conferidos contra as fontes;
5. **Expõe tudo por API REST**, para integrar a outros sistemas.
        """
    )

st.subheader("🧭 Por onde começar")
a, b, c = st.columns(3)
a.markdown("**1. Veja o ciclo**\n\nPágina *Ciclo de dados*: cada etapa, com números reais.")
b.markdown("**2. Explore**\n\n*Dados e gráficos* e *Notícias* para entender o cenário.")
c.markdown("**3. Peça à IA**\n\n*Resumos com IA*, *Pergunte aos dados* e *Insights e previsão*.")

st.subheader("🌍 Por que ODS 12 e ODS 13?")
x, y = st.columns(2)
x.markdown(
    "**ODS 12 — Consumo e produção responsáveis.** A pegada de carbono de uma PME nasce diretamente dos seus padrões de consumo de energia, combustível e insumos — "
    "medir e reduzir esse consumo é a aplicação prática da meta do ODS 12 de alcançar uso eficiente dos recursos naturais e de levar as empresas a integrar dados de sustentabilidade em seus relatórios."
)
y.markdown(
    "**ODS 13 — Ação contra a mudança global do clima.** Como a maior parte das emissões de uma PME vem da queima de combustíveis e do consumo de eletricidade, "
    "prever e comunicar essa trajetória de emissões é uma forma concreta de colocar em prática a meta do ODS 13 de integrar medidas de mudança do clima ao planejamento e à gestão das organizações."
)

st.subheader("🧩 Arquitetura")
st.code(
    """Fontes                         Pipeline (Code/)                    Dados (Data/)               Serviços                    Interface
──────                         ────────────────                    ─────────────               ────────                    ─────────
Sites (BeautifulSoup)   ─────► data_acquisition/ scrape_*   ─────► raw/*.csv ─────┐
Gerador sintético       ─────► data_acquisition/ generate_* ─────► processed/ ─────┤
POST /emissoes · uploads ───────────────────────────────────────► raw/emissoes_*   ├─► esg_core ─► API FastAPI ─┬─► Dashboard
                               data_preparation/ build_corpus ───► corpus_llm.jsonl ┘   (validação,  (/sumarizar, │   (Streamlit)
                                                                                         previsão,   /perguntar,  └─► clientes externos
                                                                                         qualidade)  /insights)
                                                                                           ├─► LLM local (sentimento, offline)
                                                                                           └─► LLM online (OpenAI/Anthropic) + prompts versionados + verificação + auditoria""",
    language="text",
)

with st.expander("🔗 Links úteis e fontes de inspiração"):
    st.markdown(
        """
- [Climatiq API](https://www.climatiq.io/) · [SEEG](https://seeg.eco.br/) · [GHG Protocol](https://ghgprotocol.org/) · [CDP](https://www.cdp.net/) · [GRI Standards](https://www.globalreporting.org/)
- [ODS 12](https://brasil.un.org/pt-br/sdgs/12) · [ODS 13](https://brasil.un.org/pt-br/sdgs/13)
- [Microsoft TDSP](https://learn.microsoft.com/en-us/azure/architecture/data-science-process/overview) · [CRISP-DM](https://www.datascience-pm.com/crisp-dm-2/)
- [Streamlit](https://docs.streamlit.io/) · [FastAPI](https://fastapi.tiangolo.com/) · [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
        """
    )
painel_diagnostico()
