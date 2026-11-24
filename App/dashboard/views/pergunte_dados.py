import streamlit as st

import api_client
from ui_ia import mostrar_erro, render_fidelidade, render_uso, status_e_provedor
from ui_helpers import valor_padrao

st.title("💬 Pergunte aos dados")
st.caption("Perguntas em linguagem natural sobre as **emissões**, as **notícias ESG** e os **ODS 12 e 13**. A IA responde só com o que os trechos recuperados sustentam "
           "e cita as fontes; sem base relevante, ela diz que não sabe (e o provedor nem é chamado).")
BASE = st.session_state["api_url"]
status, provedor = status_e_provedor(BASE)
if status is None:
    st.stop()
valor_padrao("chat_k", 5)
st.slider("Trechos recuperados por pergunta", 1, 10, key="chat_k")
historico = st.session_state.setdefault("chat_ia", [])

SUGESTOES = ["Qual atividade mais contribui para as emissões da empresa?", "O que as notícias dizem sobre neutralidade climática?",
             "O que a meta 13.2 do ODS 13 propõe?"]
pergunta = None
cols = st.columns(len(SUGESTOES))
for col, q in zip(cols, SUGESTOES):
    if col.button(q):
        pergunta = q
entrada = st.chat_input("Pergunte sobre emissões, notícias ESG ou os ODS 12 e 13")
if isinstance(entrada, str) and entrada.strip():
    pergunta = entrada.strip()

if pergunta:
    with st.spinner("Buscando nos dados e consultando a IA..."):
        try:
            resp = api_client.perguntar(BASE, pergunta, k=st.session_state["chat_k"], provedor=provedor)
            historico.append({"pergunta": pergunta, "resposta": resp})
        except Exception as exc:  # noqa: BLE001
            historico.append({"pergunta": pergunta, "erro": exc})

for item in historico:
    with st.chat_message("user"):
        st.write(item["pergunta"])
    with st.chat_message("assistant"):
        if "erro" in item:
            mostrar_erro(item["erro"])
            continue
        r = item["resposta"]
        icone = {"alta": "🟢", "media": "🟡", "baixa": "🔴"}[r["confianca"]]
        st.write(r["resposta"])
        st.caption(f"{icone} confiança {r['confianca']} · " + ("fontes: " + ", ".join(r["fontes_citadas"]) if r["fontes_citadas"] else "sem fontes citadas")
                   + ("" if r["chamou_llm"] else " · nenhum trecho relevante: a IA não foi chamada"))
        for lac in r["lacunas"]:
            st.caption(f"↳ lacuna: {lac}")
        if r["trechos"]:
            with st.expander(f"Trechos usados ({len(r['trechos'])})"):
                for t in r["trechos"]:
                    st.markdown(f"**{t['id']}** · {t.get('titulo') or t.get('doc_id')} · relevância {t['score']}")
                    st.caption(t["trecho"])
                    if t.get("url"):
                        st.markdown(f"[abrir fonte]({t['url']})")
        render_fidelidade(r.get("fidelidade"))
        if r["chamou_llm"]:
            render_uso(r)

if historico and st.button("🗑️ Limpar conversa"):
    st.session_state["chat_ia"] = []
    st.rerun()
