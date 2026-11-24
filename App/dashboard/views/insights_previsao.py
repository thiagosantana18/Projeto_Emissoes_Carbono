import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import api_client
from esg_core.previsao import prever_emissoes
from ui_helpers import emissoes_para_graficos, fmt_num, valor_padrao
from ui_ia import ICONE_GRAV, mostrar_erro, render_fidelidade, render_uso, status_e_provedor

st.title("💡 Insights e previsão de emissões")
BASE = st.session_state["api_url"]

# ------------------------------------------------------------------ 1. previsão
st.subheader("1. Para onde caminham as emissões?")
horizonte = st.slider("Meses a prever", 1, 12, 6)
prev, fonte = None, "API"
try:
    prev = api_client.previsao_emissoes(BASE, horizonte)
except (api_client.ApiIndisponivel, api_client.ApiErro) as exc:
    fonte = "LOCAL"
    try:
        prev = prever_emissoes(emissoes_para_graficos()[0], horizonte)
        prev["avisos"] = [a for a in prev["avisos"] if a]
        st.warning(f"⚠️ API indisponível ({exc}). Previsão calculada localmente.")
    except ValueError as exc2:
        st.warning(str(exc2))
if prev:
    hist, fut = pd.DataFrame(prev["historico"]), pd.DataFrame(prev["previsoes"])
    fig = go.Figure()
    fig.add_scatter(x=hist["mes"], y=hist["kgco2e"], name="Histórico", mode="lines+markers")
    fig.add_scatter(x=fut["mes"], y=fut["previsto"], name="Previsão", mode="lines+markers", line=dict(dash="dash"))
    fig.add_scatter(x=list(fut["mes"]) + list(fut["mes"])[::-1], y=list(fut["max"]) + list(fut["min"])[::-1], fill="toself",
                    name="Faixa aproximada", line=dict(width=0), opacity=0.25)
    fig.update_layout(title="Emissões mensais totais (kgCO₂e)", xaxis_title="mês", yaxis_title="kgCO₂e")
    st.plotly_chart(fig)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Melhor método", prev["melhor"].replace("_", " "))
    m2.metric("Erro médio no backtest (MAPE)", f"{fmt_num(prev['mape_melhor'], 1)}%")
    m3.metric("Meta do projeto (< 15%)", "✅ atingida" if prev["atinge_meta"] else "❌ não atingida")
    m4.metric("Meses de histórico", prev["serie"]["n_meses"])
    with st.expander("Comparação dos métodos (backtest com origem móvel)"):
        st.dataframe(pd.DataFrame(prev["metodos"]), hide_index=True)
    st.caption(f"Fonte: {fonte} · {prev['intervalo']}. ⚠️ Com a amostra sintética do projeto, o resultado demonstra o método — não prova que prevê uma empresa real.")

# ------------------------------------------------------------------ 2. insights com IA
st.divider()
st.subheader("2. O que fazer a respeito? (insights com IA)")
st.caption("A IA recebe os dados agregados de emissões, a previsão e o sentimento das notícias, e propõe destaques, riscos e recomendações ligadas aos ODS 12 e 13. "
           "Todo número do texto é conferido contra os dados.")
status, provedor = status_e_provedor(BASE)
if status is not None:
    valor_padrao("ia_foco", "")
    st.text_input("Foco (opcional)", key="ia_foco", placeholder="ex.: reduzir emissões da frota")
    a, b = st.columns(2)
    inc_prev = a.checkbox("Incluir a previsão", value=True)
    inc_not = b.checkbox("Incluir resumo das notícias (1 chamada extra)", value=False)
    if st.button("Gerar insights", type="primary"):
        with st.spinner("Analisando os dados com a IA..."):
            try:
                st.session_state["insights_ia"] = api_client.insights_emissoes(BASE, foco=st.session_state["ia_foco"] or None, incluir_previsao=inc_prev,
                                                                               incluir_noticias=inc_not, provedor=provedor)
            except Exception as exc:  # noqa: BLE001
                st.session_state["insights_ia"] = None
                mostrar_erro(exc)

r = st.session_state.get("insights_ia")
if r:
    ins = r["insights"]
    for av in r.get("avisos", []):
        st.info(av)
    st.markdown("#### Destaques")
    for d in ins["destaques"]:
        st.markdown(f"- **{d['titulo']}** — {d['detalhe']}")
    if ins["riscos"]:
        st.markdown("#### Riscos")
        for x in ins["riscos"]:
            st.markdown(f"- {ICONE_GRAV[x['gravidade']]} {x['descricao']} *(gravidade {x['gravidade']})*")
    if ins["recomendacoes"]:
        st.markdown("#### Recomendações priorizadas")
        ordem = {"alta": 0, "media": 1, "baixa": 2}
        recs = sorted(ins["recomendacoes"], key=lambda x: ordem[x["prioridade"]])
        st.dataframe(pd.DataFrame([{"prioridade": f"{ICONE_GRAV[x['prioridade']]} {x['prioridade']}", "ação": x["acao"], "por quê": x["justificativa"],
                                    "impacto esperado": x["impacto_esperado"], "ODS": x["ods"] or ""} for x in recs]), hide_index=True)
    if ins["alertas_de_dados"]:
        st.markdown("#### ⚠️ Alertas sobre os dados")
        for x in ins["alertas_de_dados"]:
            st.markdown(f"- {x}")
    render_fidelidade(r["fidelidade"])
    with st.expander("Dados enviados ao modelo (exatamente como ele os recebeu)"):
        st.text(r["texto_contexto"])
    render_uso(r)

# ------------------------------------------------------------------ 3. sentimento
df_s = st.session_state.get("sentimentos_resultados")
if df_s is not None and not df_s.empty:
    st.divider()
    st.subheader("3. Clima das notícias (modelo local de sentimento)")
    contagem = df_s["sentimento"].value_counts().reindex(["positivo", "neutro", "negativo"], fill_value=0)
    st.plotly_chart(px.bar(contagem.rename_axis("sentimento").reset_index(name="manchetes"), x="sentimento", y="manchetes"))
    st.caption("Previsões de um modelo, sem validação contra rótulos humanos. Geradas na página *Análise de texto (LLM local)*.")
