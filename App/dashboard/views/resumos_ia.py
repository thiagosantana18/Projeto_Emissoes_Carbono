import pandas as pd
import streamlit as st

import api_client
from esg_core.arquivos import extrair_texto
from ui_helpers import noticias, valor_padrao
from ui_ia import mostrar_erro, render_sumario, status_e_provedor

OBJETIVO = "apoiar decisões de gestores de pequenas e médias empresas sobre sustentabilidade e emissões de carbono"

st.title("📝 Resumos com IA")
st.caption("Sumarização de notícias ESG, trechos dos ODS e relatórios longos com um LLM online (OpenAI/Anthropic). "
           "A chave fica no servidor da API. ⚠️ Os textos são enviados ao provedor escolhido.")
BASE = st.session_state["api_url"]
status, provedor = status_e_provedor(BASE)
if status is None:
    st.stop()

valor_padrao("ia_objetivo", OBJETIVO)
valor_padrao("ia_nivel", "executivo")
valor_padrao("ia_versao_prompt", "sumario_v2")
valor_padrao("ia_usar_cache", True)
c1, c2 = st.columns([2, 1])
c1.text_input("Objetivo do leitor (orienta o foco do resumo)", key="ia_objetivo")
c2.radio("Nível de detalhe", ["executivo", "detalhado"], key="ia_nivel", horizontal=True)
with st.expander("Opções avançadas (engenharia de prompt e custo)"):
    st.selectbox("Versão do prompt", ["sumario_v2", "sumario_v1"], key="ia_versao_prompt",
                 help="v2: estruturado, com regras, esquema JSON e citações. v1: instrução mínima em texto livre (linha de base para comparar).")
    st.checkbox("Reaproveitar resposta idêntica anterior (cache, sem nova cobrança)", key="ia_usar_cache")
args = dict(objetivo=st.session_state["ia_objetivo"], nivel=st.session_state["ia_nivel"], provedor=provedor,
            versao_prompt=st.session_state["ia_versao_prompt"], usar_cache=st.session_state["ia_usar_cache"])

aba_c, aba_t, aba_cmp = st.tabs(["📰 Documentos coletados", "📄 Texto ou relatório", "🔬 Comparar prompts"])

with aba_c:
    st.markdown("Resume o que foi **coletado por scraping** (manchetes e trechos dos ODS), citando cada fonte.")
    df_n = noticias()
    tags = sorted({t for linha in df_n["tags"].dropna().astype(str) for t in linha.split(";") if t}) if not df_n.empty else []
    valor_padrao("ia_tipo", "Todos")
    valor_padrao("ia_tag", "(todas)")
    valor_padrao("ia_limite", 10)
    if st.session_state["ia_tag"] not in ["(todas)"] + tags:
        st.session_state["ia_tag"] = "(todas)"
    a, b, c = st.columns(3)
    a.selectbox("Tipo de documento", ["Todos", "noticia", "ods_trecho"], key="ia_tipo")
    b.selectbox("Tag temática", ["(todas)"] + tags, key="ia_tag")
    c.slider("Máximo de documentos (mais recentes)", 3, 40, key="ia_limite")
    filtros = dict(tipo=None if st.session_state["ia_tipo"] == "Todos" else st.session_state["ia_tipo"],
                   tag=None if st.session_state["ia_tag"] == "(todas)" else st.session_state["ia_tag"], limite=st.session_state["ia_limite"])
    if st.button("Resumir documentos coletados", type="primary"):
        with st.spinner("Gerando o resumo com a IA..."):
            try:
                st.session_state["resumo_ia"] = api_client.sumarizar_corpus(BASE, **filtros, **args)
            except Exception as exc:  # noqa: BLE001
                st.session_state["resumo_ia"] = None
                mostrar_erro(exc)

with aba_t:
    st.markdown("Cole um texto ou envie um **relatório de sustentabilidade** (PDF com texto, TXT ou MD). Textos longos são divididos em trechos e resumidos por *map-reduce*.")
    arquivo = st.file_uploader("Arquivo", type=["pdf", "txt", "md"], key="ia_arquivo")
    texto, titulo = "", None
    if arquivo is not None:
        try:
            texto, avisos = extrair_texto(arquivo.name, arquivo.getvalue())
            titulo = arquivo.name
            for av in avisos:
                st.warning(av)
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
    else:
        valor_padrao("ia_texto", "")
        st.text_area("…ou cole o texto aqui", key="ia_texto", height=200)
        texto = st.session_state["ia_texto"]
    limite_chars = int(status["limites"]["max_chars_entrada"])
    if texto:
        st.caption(f"{len(texto):,} caracteres · limite configurado: {limite_chars:,}".replace(",", "."))
        if len(texto) > limite_chars:
            st.warning("O texto excede o limite do servidor; a API vai recusar. Envie uma parte menor ou aumente ESG_IA_MAX_CHARS.")
    if st.button("Resumir texto", type="primary", disabled=not texto.strip()):
        with st.spinner("Gerando o resumo com a IA..."):
            try:
                st.session_state["resumo_ia"] = api_client.sumarizar_texto(BASE, texto, titulo=titulo, **args)
            except Exception as exc:  # noqa: BLE001
                st.session_state["resumo_ia"] = None
                mostrar_erro(exc)

with aba_cmp:
    st.markdown("**Engenharia de prompts na prática:** roda os mesmos documentos com o prompt **v1** (instrução mínima) e **v2** (estruturado, ancorado, com citações) "
                "e compara. Usa os filtros da aba *Documentos coletados* e faz **2 chamadas** ao provedor.")
    if st.button("Comparar v1 × v2"):
        resultados = {}
        with st.spinner("Rodando os dois prompts..."):
            for v in ("sumario_v1", "sumario_v2"):
                try:
                    resultados[v] = api_client.sumarizar_corpus(BASE, **{**filtros, **args, "versao_prompt": v})
                except Exception as exc:  # noqa: BLE001
                    mostrar_erro(exc)
                    break
        if len(resultados) == 2:
            st.session_state["comparacao_prompts"] = resultados
    cmp = st.session_state.get("comparacao_prompts")
    if cmp:
        linhas = []
        for v, r in cmp.items():
            s = r["resumo"]
            linhas.append({"prompt": v, "saída estruturada": "sim" if s["pontos_chave"] or s["recomendacoes"] else "não (texto livre)",
                           "pontos-chave": len(s["pontos_chave"]), "recomendações": len(s["recomendacoes"]), "fontes citadas": len(s["fontes_citadas"]),
                           "lacunas declaradas": len(s["lacunas"]), "números verificados": r["fidelidade"]["numeros_verificados"],
                           "números não encontrados": len(r["fidelidade"]["numeros_nao_encontrados"]), "tokens (ent/saída)": f"{r['tokens_entrada']}/{r['tokens_saida']}"})
        st.dataframe(pd.DataFrame(linhas), hide_index=True)
        ca, cb = st.columns(2)
        ca.markdown("**v1 — texto livre**")
        ca.info(cmp["sumario_v1"]["resumo"]["resumo_executivo"])
        cb.markdown("**v2 — estruturado e ancorado**")
        cb.info(cmp["sumario_v2"]["resumo"]["resumo_executivo"])
        st.caption("A v1 não permite verificar citações (não há) nem declara lacunas; a v2 sim. Qual é melhor depende de você ler os dois e das métricas acima.")

r = st.session_state.get("resumo_ia")
if r:
    st.divider()
    render_sumario(r)
