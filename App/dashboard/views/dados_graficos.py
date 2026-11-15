import plotly.express as px
import streamlit as st

from ui_helpers import (emissoes_para_graficos, fmt_num, multiselect_persistente, periodo_persistente,
                        valor_padrao)

st.title("📊 Dados e gráficos interativos")
st.caption("Filtre por unidade, atividade, origem e período. Os filtros são mantidos ao trocar de página.")

valor_padrao("fonte_dados", "API")
topo1, topo2 = st.columns([3, 1])
topo1.radio("Fonte dos dados", ["API", "LOCAL"], horizontal=True, key="fonte_dados",
            help="API: esta página consome GET /emissoes da API FastAPI. LOCAL: lê os arquivos diretamente.")
if topo2.button("🔄 Atualizar da API"):
    st.session_state["api_nonce"] += 1

df, fonte, aviso = emissoes_para_graficos()
if fonte == "API":
    st.success(f"📡 Dados obtidos pela API em {st.session_state['api_url']} (GET /emissoes) — {len(df)} registros.")
elif aviso:
    st.warning(f"⚠️ {aviso}\n\nPara usar a API: `uvicorn App.api.main:app --reload`.")
else:
    st.info("💾 Dados lidos dos arquivos locais.")
if df.empty:
    st.warning("Sem dados de emissões. Gere a amostra: `python Code/data_acquisition/generate_sample_emissions.py`.")
    st.stop()

c1, c2, c3 = st.columns(3)
with c1:
    unidades = multiselect_persistente("Unidade", sorted(df["unidade"].unique()), "f_unidades")
with c2:
    atividades = multiselect_persistente("Tipo de atividade", sorted(df["tipo_atividade"].unique()), "f_atividades")
with c3:
    origens = multiselect_persistente("Origem do dado", sorted(df["origem"].unique()), "f_origens")
ini, fim = periodo_persistente("Período", sorted(df["mes_referencia"].unique()), "f_periodo")

f = df[df["unidade"].isin(unidades) & df["tipo_atividade"].isin(atividades) & df["origem"].isin(origens)
       & (df["mes_referencia"] >= ini) & (df["mes_referencia"] <= fim)]
if f.empty:
    st.info("Nenhum registro para os filtros selecionados.")
    st.stop()

mensal = f.groupby("mes_referencia")["emissao_kgco2e"].sum()
por_ativ = f.groupby("tipo_atividade")["emissao_kgco2e"].sum().sort_values(ascending=False)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Registros", fmt_num(len(f), 0))
m2.metric("Emissão total (tCO₂e)", fmt_num(f["emissao_kgco2e"].sum() / 1000))
m3.metric("Média mensal (tCO₂e)", fmt_num(mensal.mean() / 1000))
m4.metric("Maior fonte", f"{por_ativ.index[0]} ({100 * por_ativ.iloc[0] / por_ativ.sum():.0f}%)")

aba1, aba2, aba3 = st.tabs(["📅 Evolução mensal", "🏭 Unidades e atividades", "🗂️ Tabela"])

with aba1:
    serie = f.groupby(["mes_referencia", "tipo_atividade"], as_index=False)["emissao_kgco2e"].sum()
    fig = px.bar(serie, x="mes_referencia", y="emissao_kgco2e", color="tipo_atividade",
                 labels={"mes_referencia": "Mês", "emissao_kgco2e": "kgCO₂e", "tipo_atividade": "Atividade"},
                 title="Emissões mensais por tipo de atividade")
    st.plotly_chart(fig)

with aba2:
    ca, cb = st.columns(2)
    por_un = f.groupby("unidade", as_index=False)["emissao_kgco2e"].sum().sort_values("emissao_kgco2e")
    ca.plotly_chart(px.bar(por_un, x="emissao_kgco2e", y="unidade", orientation="h",
                           labels={"emissao_kgco2e": "kgCO₂e", "unidade": ""}, title="Total por unidade"))
    cb.plotly_chart(px.sunburst(f, path=["unidade", "tipo_atividade"], values="emissao_kgco2e",
                                title="Composição: unidade → atividade"))

with aba3:
    st.dataframe(
        f.sort_values(["mes_referencia", "unidade"], ascending=[False, True]),
        hide_index=True,
        column_config={
            "mes_referencia": "Mês", "unidade": "Unidade", "setor": "Setor", "tipo_atividade": "Atividade",
            "quantidade": st.column_config.NumberColumn("Quantidade", format="%.1f"),
            "unidade_medida": "Un.",
            "fator_emissao_kgco2e": st.column_config.NumberColumn("Fator (kgCO₂e/un.)", format="%.4f"),
            "emissao_kgco2e": st.column_config.NumberColumn("Emissão (kgCO₂e)", format="%.2f"),
            "fonte_fator": "Fonte do fator", "origem": "Origem",
        },
    )
    st.download_button("⬇️ Baixar dados filtrados (CSV)", f.to_csv(index=False).encode("utf-8"),
                       file_name="emissoes_filtradas.csv", mime="text/csv")
