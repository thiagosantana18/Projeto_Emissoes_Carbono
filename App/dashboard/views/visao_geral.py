import streamlit as st

from ui_helpers import corpus, emissoes_consolidadas, fmt_num, noticias, painel_diagnostico

st.title("🌱 Monitoramento e Previsão de Emissões de Carbono Corporativas")
st.caption("Pilar Ambiental (E) do ESG · ODS 12 e 13 · CRISP-DM / TDSP · Etapa 3 — multipágina, API e preparação para LLM")

df = emissoes_consolidadas()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Registros de emissão", fmt_num(len(df), 0))
c2.metric("Emissão total (tCO₂e)", fmt_num(df["emissao_kgco2e"].sum() / 1000) if not df.empty else "—")
c3.metric("Manchetes coletadas", fmt_num(len(noticias()), 0))
c4.metric("Documentos no corpus (LLM)", fmt_num(len(corpus()), 0))
st.caption("Use o menu lateral para navegar. Os dados de atividade são **sintéticos** (demonstração).")

st.divider()
col_p, col_o = st.columns(2)
with col_p:
    st.subheader("📌 O problema de negócio")
    st.markdown(
        """
Pequenas e médias empresas (PMEs) não têm **visibilidade contínua** da sua pegada de carbono
(Escopo 1, 2 e 3). O relatório é **anual, manual e isolado** em planilhas, o que:

- impede decisões tempestivas de redução de emissões;
- encarece a conformidade com **GRI** e **CDP**;
- dificulta integrar os dados com outros sistemas (ERP, BI) e com ferramentas de IA.
        """
    )
with col_o:
    st.subheader("🎯 Objetivos")
    st.markdown(
        """
1. Coletar dados de atividade/fatores por **API** e contexto por **web scraping** (BeautifulSoup);
2. Disponibilizar os dados por uma **API REST (FastAPI)** — consulta (GET) e envio (POST);
3. Explorar tudo em um **dashboard multipágina** com cache e estado de sessão;
4. **Preparar** os dados para tarefas com LLM (sentimento, resumo, Q&A, relatórios);
5. *(próximas etapas)* prever emissões e gerar relatórios com IA generativa.
        """
    )

st.subheader("🌍 Por que ODS 12 e ODS 13?")
a, b = st.columns(2)
a.markdown(
    "**ODS 12 — Consumo e produção responsáveis.** A pegada de carbono de uma PME nasce diretamente dos seus "
    "padrões de consumo de energia, combustível e insumos — medir e reduzir esse consumo é a aplicação prática "
    "da meta do ODS 12 de alcançar uso eficiente dos recursos naturais e de levar as empresas a integrar dados "
    "de sustentabilidade em seus relatórios."
)
b.markdown(
    "**ODS 13 — Ação contra a mudança global do clima.** Como a maior parte das emissões de uma PME vem da queima "
    "de combustíveis e do consumo de eletricidade, prever e comunicar essa trajetória de emissões é uma forma "
    "concreta de colocar em prática a meta do ODS 13 de integrar medidas de mudança do clima ao planejamento e à "
    "gestão das organizações."
)

st.subheader("🧩 Arquitetura")
st.code(
    """Fontes                    Pipeline (Code/)                 Dados (Data/)            Consumo
──────                    ────────────────                 ─────────────            ───────
Sites (BeautifulSoup) ──► data_acquisition/scrape_*.py ──► raw/*.csv, *.txt ──┐
Gerador sintético     ──► data_acquisition/generate_*  ──► processed/amostra  ├─► esg_core ─┬─► API FastAPI  (App/api)
Uploads / POST /emissoes ─────────────────────────────────► raw/emissoes_env. ┘             └─► Dashboard    (App/dashboard)
                          data_preparation/build_corpus ─► processed/corpus_llm.jsonl, contexto_relatorio.json
                                                           └─► (Etapa 4) tarefas com LLM""",
    language="text",
)

with st.expander("🔗 Links úteis e fontes de inspiração"):
    st.markdown(
        """
- [Climatiq API](https://www.climatiq.io/) · [SEEG](https://seeg.eco.br/) · [GHG Protocol](https://ghgprotocol.org/)
- [CDP](https://www.cdp.net/) · [GRI Standards](https://www.globalreporting.org/)
- [ODS 12](https://brasil.un.org/pt-br/sdgs/12) · [ODS 13](https://brasil.un.org/pt-br/sdgs/13)
- [Microsoft TDSP](https://learn.microsoft.com/en-us/azure/architecture/data-science-process/overview) ·
  [CRISP-DM](https://www.datascience-pm.com/crisp-dm-2/)
- [Streamlit](https://docs.streamlit.io/) · [FastAPI](https://fastapi.tiangolo.com/) ·
  [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
        """
    )
painel_diagnostico()
