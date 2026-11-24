import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from esg_core.validation import diagnostico_qualidade_emissoes
from ui_helpers import corpus, emissoes_consolidadas, fmt_num

st.title("📈 Estatísticas e qualidade dos dados")
df = emissoes_consolidadas()
if df.empty:
    st.warning("Sem dados de emissões.")
    st.stop()

aba_em, aba_q, aba_tx = st.tabs(["🔥 Emissões", "✅ Qualidade", "📝 Textos"])

with aba_em:
    desc = (df.groupby("tipo_atividade")["emissao_kgco2e"].agg(["count", "sum", "mean", "median", "std", "min", "max"])
            .round(2).reset_index())
    desc.columns = ["Atividade", "Registros", "Soma (kgCO₂e)", "Média", "Mediana", "Desvio-padrão", "Mín.", "Máx."]
    st.markdown("**Estatísticas descritivas por atividade**")
    st.dataframe(desc, hide_index=True)

    ca, cb = st.columns(2)
    p = df.groupby("tipo_atividade")["emissao_kgco2e"].sum().sort_values(ascending=False)
    acumulado = 100 * p.cumsum() / p.sum()
    fig = go.Figure()
    fig.add_bar(x=p.index, y=p.values, name="kgCO₂e")
    fig.add_scatter(x=p.index, y=acumulado.values, name="% acumulado", yaxis="y2", mode="lines+markers")
    fig.update_layout(title="Pareto: concentração das emissões", yaxis2=dict(overlaying="y", side="right", range=[0, 105]))
    ca.plotly_chart(fig)
    cb.plotly_chart(px.box(df, x="tipo_atividade", y="emissao_kgco2e", points=False,
                           labels={"tipo_atividade": "", "emissao_kgco2e": "kgCO₂e por registro"},
                           title="Distribuição das emissões por registro"))

    total_mes = df.groupby("mes_referencia")["emissao_kgco2e"].sum()
    var = (total_mes.pct_change() * 100).dropna().round(1).reset_index(name="variação %")
    st.plotly_chart(px.bar(var, x="mes_referencia", y="variação %", title="Variação mensal do total (%)"))

with aba_q:
    d = diagnostico_qualidade_emissoes(df)
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Registros", fmt_num(d["n_registros"], 0))
    q2.metric("Duplicados (mês+unidade+atividade)", d["duplicados"])
    q3.metric("Meses faltantes", len(d["meses_faltantes"]))
    q4.metric("Emissões inconsistentes", d["emissoes_inconsistentes"])
    st.markdown("**Checklist (critérios do Data Summary Report)**")
    checks = [
        ("Sem valores nulos", all(v == 0 for v in d["nulos_por_coluna"].values())),
        ("Sem lacunas de mês na série (> 1 mês consecutivo)", not d["meses_faltantes"]),
        ("Sem registros duplicados", d["duplicados"] == 0),
        ("Emissão = quantidade × fator (tolerância de 1%)", d["emissoes_inconsistentes"] == 0),
    ]
    for rotulo, ok in checks:
        st.write(("✅ " if ok else "❌ ") + rotulo)
    if d["meses_faltantes"]:
        st.warning("Meses faltantes: " + ", ".join(d["meses_faltantes"]))
    st.caption(f"Período coberto: {d['periodo_inicio']} a {d['periodo_fim']}")
    st.dataframe(pd.DataFrame({"coluna": list(d["nulos_por_coluna"]), "nulos": list(d["nulos_por_coluna"].values())}),
                 hide_index=True)

with aba_tx:
    docs = corpus()
    if not docs:
        st.info("Corpus ainda não gerado. Rode: `python Code/data_preparation/build_corpus.py`.")
    else:
        dfc = pd.DataFrame(docs)
        t1, t2, t3 = st.columns(3)
        t1.metric("Documentos", len(dfc))
        t2.metric("Palavras (total)", fmt_num(dfc["n_palavras"].sum(), 0))
        t3.metric("Palavras por documento (média)", fmt_num(dfc["n_palavras"].mean()))
        st.plotly_chart(px.histogram(dfc, x="n_palavras", color="tipo", nbins=20,
                                     labels={"n_palavras": "palavras por documento"},
                                     title="Tamanho dos documentos"))
        st.dataframe(dfc.groupby(["tipo", "fonte"], dropna=False).agg(documentos=("doc_id", "count"),
                     palavras=("n_palavras", "sum")).reset_index(), hide_index=True)
