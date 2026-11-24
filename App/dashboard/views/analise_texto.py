import pandas as pd
import plotly.express as px
import streamlit as st

import api_client
from ui_helpers import fmt_num, noticias, valor_padrao
from ui_ia import mostrar_erro

st.title("🤖 Análise de texto com LLM local")
st.caption("Classificação de sentimento com um modelo do Hugging Face que roda na sua máquina. "
           "Esta página consome a API: `POST /processar_texto` e `POST /processar_texto/lote`.")

BASE = st.session_state["api_url"]
EMOJI = {"positivo": "😊", "neutro": "😐", "negativo": "😟"}


# ------------------------------------------------------------------ 1. estado do modelo
st.subheader("1. Estado do modelo")
status = None
try:
    status = api_client.status_modelo(BASE)
except Exception as exc:  # noqa: BLE001
    mostrar_erro(exc)

if status:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Modelo carregado", "sim" if status["carregado"] else "não")
    c2.metric("torch + transformers", "instalados" if status["dependencias_instaladas"] else "ausentes")
    c3.metric("Arquivos no cache local", "sim" if status["cache_presente"] else "não")
    c4.metric("Dispositivo", status["dispositivo"])
    st.caption(f"`{status['modelo_id']}` · requisições: {status['total_requisicoes']} · erros: {status['total_erros']}")
    if status["ultimo_erro"]:
        st.warning(f"Último erro de carga: {status['ultimo_erro']}")
    if not status["dependencias_instaladas"]:
        st.info("Instale as dependências: `pip install -r requirements-llm.txt` e reinicie a API.")
    elif not status["cache_presente"] and status["offline"]:
        st.info("Baixe o modelo uma vez (precisa de internet): `python Code/llm/baixar_modelo.py`")
    if not status["carregado"] and st.button("⚡ Carregar modelo na memória"):
        with st.spinner("Carregando o modelo..."):
            try:
                api_client.carregar_modelo(BASE)
                st.success("Modelo carregado.")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                mostrar_erro(exc)

# ------------------------------------------------------------------ 2. um texto
st.divider()
st.subheader("2. Analisar um texto")
valor_padrao("texto_llm", "Vivo reduz emissões em 91% e antecipa neutralidade climática para 2035")
st.text_area("Texto (português)", key="texto_llm", height=110)
if st.button("Analisar sentimento", type="primary"):
    with st.spinner("Analisando..."):
        try:
            st.session_state["ultimo_resultado_llm"] = api_client.processar_texto(BASE, st.session_state["texto_llm"])
        except Exception as exc:  # noqa: BLE001
            st.session_state["ultimo_resultado_llm"] = None
            mostrar_erro(exc)

r = st.session_state.get("ultimo_resultado_llm")
if r:
    res = r["resultado"]
    st.subheader(f"{EMOJI[res['rotulo']]} {res['rotulo'].capitalize()} — confiança {res['confianca']:.0%}")
    st.progress(float(res["confianca"]))
    prob = pd.DataFrame({"sentimento": list(res["probabilidades"]), "probabilidade": list(res["probabilidades"].values())})
    st.plotly_chart(px.bar(prob, x="sentimento", y="probabilidade", range_y=[0, 1], title="Probabilidade por classe"))
    m = r["metadados"]
    st.caption(f"Modelo: `{r['modelo']['id']}` ({r['modelo']['dispositivo']}) · {m['tempo_inferencia_ms']:.0f} ms · "
               f"{m['n_caracteres']} caracteres" + (f" · {m['n_tokens']} tokens" if m.get("n_tokens") else "")
               + (" · ⚠️ texto truncado pelo modelo" if m["truncado"] else ""))
    with st.expander("Resposta completa da API (JSON)"):
        st.json(r)

# ------------------------------------------------------------------ 3. manchetes
st.divider()
st.subheader("3. Classificar as manchetes coletadas")
valor_padrao("n_manchetes", 10)
st.slider("Quantas manchetes classificar", 3, 50, key="n_manchetes")
if st.button("Classificar manchetes"):
    with st.spinner("Buscando manchetes e classificando..."):
        try:
            try:
                df_n = api_client.obter_noticias(BASE, st.session_state["n_manchetes"])
            except api_client.ApiErro:
                df_n = noticias().head(st.session_state["n_manchetes"])
            if df_n.empty:
                st.info("Nenhuma manchete disponível. Rode o scraper de notícias.")
            else:
                resultados = api_client.processar_lote(BASE, df_n["titulo"].astype(str).tolist())
                st.session_state["sentimentos_resultados"] = pd.DataFrame([{
                    "titulo": t, "sentimento": x["resultado"]["rotulo"], "confianca": x["resultado"]["confianca"],
                    "p_positivo": x["resultado"]["probabilidades"]["positivo"],
                    "p_neutro": x["resultado"]["probabilidades"]["neutro"],
                    "p_negativo": x["resultado"]["probabilidades"]["negativo"]}
                    for t, x in zip(df_n["titulo"], resultados)])
        except Exception as exc:  # noqa: BLE001
            mostrar_erro(exc)

df_s = st.session_state.get("sentimentos_resultados")
if df_s is not None and not df_s.empty:
    contagem = df_s["sentimento"].value_counts().reindex(["positivo", "neutro", "negativo"], fill_value=0)
    a, b, c = st.columns(3)
    a.metric("😊 Positivas", int(contagem["positivo"]))
    b.metric("😐 Neutras", int(contagem["neutro"]))
    c.metric("😟 Negativas", int(contagem["negativo"]))
    st.plotly_chart(px.bar(contagem.rename_axis("sentimento").reset_index(name="manchetes"), x="sentimento", y="manchetes",
                           title="Distribuição de sentimento nas manchetes"))
    st.dataframe(df_s, hide_index=True,
                 column_config={"confianca": st.column_config.ProgressColumn("Confiança", min_value=0, max_value=1, format="%.2f")})
    st.download_button("⬇️ Baixar resultados (CSV)", df_s.to_csv(index=False).encode("utf-8"),
                       file_name="sentimento_manchetes.csv", mime="text/csv")
    st.caption("Estas são previsões do modelo, **não** rótulos verdadeiros. Para medir a qualidade, rotule o gabarito "
               "(`Data/processed/avaliacao/sentimento_gold_template.csv`) e rode `python Code/llm/avaliar_sentimento.py avaliar`.")
