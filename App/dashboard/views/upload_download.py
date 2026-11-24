from datetime import datetime

import pandas as pd
import streamlit as st

from esg_core import data_access as da
from esg_core import paths
from esg_core.validation import COLUNAS_EMISSOES, validar_emissoes_df
from ui_helpers import emissoes_consolidadas, fmt_num

st.title("📤 Upload e download de dados")
st.caption("Complemente a base com seus próprios registros (CSV) e exporte os dados do projeto.")

# ------------------------------------------------------------------ upload
st.subheader("1. Enviar registros de emissão (CSV)")
st.markdown("Colunas obrigatórias: `" + "`, `".join(COLUNAS_EMISSOES) + "`. "
            "Cada linha é validada (formato AAAA-MM, valores positivos, emissão ≈ quantidade × fator).")
st.download_button("⬇️ Baixar modelo de CSV", da.template_emissoes_csv().encode("utf-8"),
                   file_name="modelo_emissoes.csv", mime="text/csv")

arquivo = st.file_uploader("Selecione um arquivo CSV", type=["csv"], key=f"uploader_{st.session_state['uploader_n']}")
if arquivo is not None:
    try:
        bruto = pd.read_csv(arquivo)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Não foi possível ler o arquivo: {exc}")
        bruto = None

    if bruto is not None:
        validas, erros = validar_emissoes_df(bruto)
        if validas.empty and erros and erros[0].startswith("Colunas obrigatórias"):
            st.error(erros[0] + ". O arquivo foi rejeitado.")
        else:
            c1, c2 = st.columns(2)
            c1.metric("Linhas válidas", len(validas))
            c2.metric("Linhas rejeitadas", len(erros))
            if erros:
                with st.expander(f"Ver {len(erros)} erro(s)"):
                    st.write("\n".join(f"- {e}" for e in erros[:200]))
            if not validas.empty:
                st.dataframe(validas.head(10), hide_index=True)
                if st.button("➕ Adicionar linhas válidas ao dataset desta sessão"):
                    novas = validas.assign(origem="upload")
                    atual = st.session_state["df_uploads"]
                    st.session_state["df_uploads"] = novas if atual is None else pd.concat([atual, novas], ignore_index=True)
                    st.session_state["historico_uploads"].append(
                        {"arquivo": arquivo.name, "linhas": len(validas), "rejeitadas": len(erros),
                         "em": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
                    st.session_state["uploader_n"] += 1          # reinicia o uploader
                    st.rerun()

st.subheader("2. Dados enviados nesta sessão")
hist = st.session_state["historico_uploads"]
if hist:
    st.dataframe(pd.DataFrame(hist), hide_index=True)
    st.caption("Os uploads valem apenas para esta sessão do navegador. Para gravar no servidor, use `POST /emissoes` (página API).")
    if st.button("🗑️ Limpar uploads da sessão"):
        st.session_state["df_uploads"] = None
        st.session_state["historico_uploads"] = []
        st.rerun()
else:
    st.info("Nenhum upload nesta sessão.")

# ------------------------------------------------------------------ download
st.subheader("3. Baixar dados")
consolidado = emissoes_consolidadas()
st.caption(f"Dataset consolidado: {fmt_num(len(consolidado), 0)} linhas "
           f"(origens: {', '.join(sorted(consolidado['origem'].unique())) or '—'}).")
carimbo = datetime.now().strftime("%Y%m%d")

colunas = st.columns(3)
colunas[0].download_button("⬇️ Emissões consolidadas (CSV)", consolidado.to_csv(index=False).encode("utf-8"),
                           file_name=f"emissoes_consolidado_{carimbo}.csv", mime="text/csv")
noticias_df = da.carregar_noticias()
colunas[1].download_button("⬇️ Notícias coletadas (CSV)", noticias_df.to_csv(index=False).encode("utf-8"),
                           file_name="noticias_esg.csv", mime="text/csv", disabled=noticias_df.empty)
for destino, caminho, rotulo, mime in [
    (colunas[2], paths.caminho_corpus(), "⬇️ Corpus para LLM (JSONL)", "application/jsonl"),
    (colunas[0], paths.caminho_contexto_relatorio(), "⬇️ Contexto de relatório (JSON)", "application/json"),
]:
    destino.download_button(rotulo, caminho.read_bytes() if caminho.is_file() else b"",
                            file_name=caminho.name, mime=mime, disabled=not caminho.is_file(), key=f"dl_{caminho.name}")
