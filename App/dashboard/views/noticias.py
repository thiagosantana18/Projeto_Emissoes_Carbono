import pandas as pd
import plotly.express as px
import streamlit as st

from esg_core import data_access as da
from esg_core.text_utils import frequencia_palavras
from ui_helpers import WORDCLOUD_OK, fmt_num, gerar_nuvem, noticias, ods, valor_padrao
from esg_core import paths

st.title("📰 Notícias ESG e nuvem de palavras")
st.caption("Manchetes coletadas por web scraping (BeautifulSoup), com verificação prévia do robots.txt. "
           "Veja `Code/data_acquisition/scrape_noticias_esg.py`.")

df = noticias()
if df.empty:
    st.warning(f"Nenhuma notícia em `{paths.caminho_noticias()}`. Rode: `python Code/data_acquisition/scrape_noticias_esg.py`.")
    st.stop()

todas_tags = sorted({t for linha in df["tags"].dropna().astype(str) for t in linha.split(";") if t})
valor_padrao("noticias_busca", "")
valor_padrao("noticias_tag", "(todas)")
if st.session_state["noticias_tag"] not in ["(todas)"] + todas_tags:
    st.session_state["noticias_tag"] = "(todas)"

c1, c2 = st.columns([2, 1])
c1.text_input("🔎 Buscar no título", key="noticias_busca")
c2.selectbox("Tag temática", ["(todas)"] + todas_tags, key="noticias_tag")
tag = None if st.session_state["noticias_tag"] == "(todas)" else st.session_state["noticias_tag"]
f = da.filtrar_noticias(df, st.session_state["noticias_busca"] or None, tag)

datas = pd.to_datetime(df["data_publicacao"], errors="coerce", format="mixed", dayfirst=True)
m1, m2, m3 = st.columns(3)
m1.metric("Manchetes (após filtros)", f"{len(f)} de {len(df)}")
m2.metric("Fontes", df["fonte"].nunique() if df["fonte"].notna().any() else 1)
m3.metric("Mais recente", datas.max().strftime("%d/%m/%Y") if datas.notna().any() else "N/D")

st.dataframe(
    f[["titulo", "data_publicacao", "fonte", "tags", "url_materia"]], hide_index=True,
    column_config={"titulo": "Manchete", "data_publicacao": "Data", "fonte": "Fonte", "tags": "Tags",
                   "url_materia": st.column_config.LinkColumn("Link")},
)

st.divider()
st.subheader("☁️ Nuvem de palavras e estatísticas")
OPCOES = ["Manchetes (com os filtros acima)", "Conteúdo dos ODS 12/13"]
valor_padrao("nuvem_fonte", OPCOES[0])
valor_padrao("nuvem_topn", 15)
if st.session_state["nuvem_fonte"] not in OPCOES:
    st.session_state["nuvem_fonte"] = OPCOES[0]
st.radio("Gerar a partir de", OPCOES, horizontal=True, key="nuvem_fonte")
st.slider("Palavras no ranking", 5, 30, key="nuvem_topn")

if st.session_state["nuvem_fonte"] == OPCOES[0]:
    textos = (f["titulo"].astype(str) + " " + f["resumo"].fillna("").astype(str)).tolist()
else:
    textos = ods()["trecho"].dropna().astype(str).tolist()

if not textos:
    st.info("Sem texto para analisar com os filtros atuais.")
    st.stop()

imagem = gerar_nuvem(" ".join(textos))
if imagem is not None:
    st.image(imagem)
elif not WORDCLOUD_OK:
    st.info("Pacote `wordcloud` não instalado (`pip install wordcloud`). Exibindo apenas o ranking de frequência.")

ranking = pd.DataFrame(frequencia_palavras(textos, st.session_state["nuvem_topn"]), columns=["palavra", "frequência"])
ca, cb = st.columns([1, 2])
ca.dataframe(ranking, hide_index=True)
cb.plotly_chart(px.bar(ranking.sort_values("frequência"), x="frequência", y="palavra", orientation="h"))

if todas_tags:
    contagem = (df["tags"].dropna().astype(str).str.split(";").explode().loc[lambda s: s != ""]
                .value_counts().rename_axis("tag").reset_index(name="manchetes"))
    st.markdown("**Temas mais frequentes nas manchetes (tags)**")
    st.plotly_chart(px.bar(contagem, x="tag", y="manchetes"))
