import pandas as pd
import requests
import streamlit as st

from ui_helpers import valor_padrao

st.title("🔌 API (FastAPI)")
st.caption("Cliente de demonstração da API REST do projeto. A API roda como processo separado.")

valor_padrao("api_url", "http://127.0.0.1:8000")
st.text_input("URL base da API", key="api_url")
BASE = st.session_state["api_url"].rstrip("/")

with st.expander("▶️ Como subir a API", expanded=False):
    st.code("uvicorn App.api.main:app --reload      # a partir da raiz do projeto", language="bash")
    st.markdown(f"Documentação interativa (Swagger): [{BASE}/docs]({BASE}/docs) · ReDoc: [{BASE}/redoc]({BASE}/redoc)")


def chamar(metodo: str, caminho: str, **kwargs):
    try:
        return requests.request(metodo, BASE + caminho, timeout=8, **kwargs)
    except requests.exceptions.RequestException as exc:
        st.error(f"Não consegui falar com a API em {BASE}. Ela está no ar? ({type(exc).__name__})")
        return None


if st.button("🩺 Testar conexão (GET /health)"):
    r = chamar("GET", "/health")
    if r is not None:
        st.success(f"HTTP {r.status_code}") if r.ok else st.error(f"HTTP {r.status_code}")
        st.json(r.json())

aba_get, aba_post, aba_txt, aba_llm = st.tabs(["GET /emissoes", "POST /emissoes", "GET /noticias · /ods · /corpus", "POST /processar_texto"])

with aba_get:
    c1, c2, c3 = st.columns(3)
    unidade = c1.text_input("unidade", "")
    atividade = c2.text_input("tipo_atividade", "")
    origem = c3.selectbox("origem", ["", "base", "api"])
    c4, c5, c6 = st.columns(3)
    mes_ini = c4.text_input("mes_inicio (AAAA-MM)", "")
    mes_fim = c5.text_input("mes_fim (AAAA-MM)", "")
    limite = c6.number_input("limit", 1, 1000, 20)
    if st.button("Executar GET /emissoes"):
        params = {k: v for k, v in {"unidade": unidade, "tipo_atividade": atividade, "origem": origem,
                                    "mes_inicio": mes_ini, "mes_fim": mes_fim, "limit": int(limite)}.items() if v != ""}
        r = chamar("GET", "/emissoes", params=params)
        if r is not None:
            st.caption(f"{r.request.url} → HTTP {r.status_code}")
            if r.ok:
                j = r.json()
                st.metric("Total que atende aos filtros", j["total"])
                st.dataframe(pd.DataFrame(j["itens"]), hide_index=True)
            else:
                st.error(r.text)

with aba_post:
    st.markdown("Envia um registro. Se **emissão** ficar vazia, a API calcula quantidade × fator.")
    with st.form("form_post"):
        a, b = st.columns(2)
        mes = a.text_input("mes_referencia (AAAA-MM)", "2026-10")
        un = b.text_input("unidade", "Matriz - SP")
        setor = a.text_input("setor", "Administrativo")
        tipo = b.text_input("tipo_atividade", "Eletricidade (rede)")
        qtd = a.number_input("quantidade", min_value=0.0, value=8500.0)
        un_med = b.text_input("unidade_medida", "kWh")
        fator = a.number_input("fator_emissao_kgco2e", min_value=0.0, value=0.0817, format="%.4f")
        fonte = b.text_input("fonte_fator", "Climatiq API")
        emissao = st.number_input("emissao_kgco2e (0 = calcular automaticamente)", min_value=0.0, value=0.0)
        enviar = st.form_submit_button("Enviar POST /emissoes")
    if enviar:
        payload = {"mes_referencia": mes, "unidade": un, "setor": setor, "tipo_atividade": tipo, "quantidade": qtd,
                   "unidade_medida": un_med, "fator_emissao_kgco2e": fator, "fonte_fator": fonte}
        if emissao > 0:
            payload["emissao_kgco2e"] = emissao
        r = chamar("POST", "/emissoes", json=payload)
        if r is not None:
            if r.status_code == 201:
                st.success("Registro criado (HTTP 201). Ele já aparece em 'Dados e gráficos' (origem = api).")
                st.json(r.json())
            elif r.status_code == 422:
                st.error("Dados rejeitados pela validação (HTTP 422):")
                st.json(r.json().get("detalhes") or r.json())
            else:
                st.error(f"HTTP {r.status_code}: {r.text}")

with aba_txt:
    rota = st.selectbox("Rota", ["/noticias", "/ods", "/corpus", "/corpus/contexto-relatorio"])
    q = st.text_input("q (busca, opcional)", "")
    if st.button("Executar GET"):
        params = {"limit": 20}
        if q and rota in ("/noticias", "/ods"):
            params["q"] = q
        r = chamar("GET", rota, params=params)
        if r is not None:
            st.caption(f"{r.request.url} → HTTP {r.status_code}")
            if r.ok:
                j = r.json()
                if isinstance(j, dict) and "itens" in j:
                    st.metric("Total", j["total"])
                    st.dataframe(pd.DataFrame(j["itens"]), hide_index=True)
                else:
                    st.json(j)
            else:
                st.warning(r.json().get("mensagem", r.text))

with aba_llm:
    st.markdown("Veja a resposta **bruta** da API, inclusive o envelope de erro (tente texto vazio, ou rode sem o modelo baixado).")
    texto_teste = st.text_area("texto", "Resultado ótimo para a empresa", key="explorer_texto")
    if st.button("Executar POST /processar_texto"):
        r = chamar("POST", "/processar_texto", json={"texto": texto_teste})
        if r is not None:
            st.caption(f"HTTP {r.status_code} · X-Request-ID: {r.headers.get('X-Request-ID', '-')}"
                       + (f" · Retry-After: {r.headers['Retry-After']}" if "Retry-After" in r.headers else ""))
            st.json(r.json())
