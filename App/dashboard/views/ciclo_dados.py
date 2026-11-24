import pandas as pd
import streamlit as st

import api_client
from esg_core import paths
from esg_core.previsao import prever_emissoes
from esg_core.qualidade import checks, relatorio_qualidade
from ui_helpers import emissoes_para_graficos

st.title("🔄 O ciclo de ciência de dados, de ponta a ponta")
st.caption("Cada etapa abaixo mostra o que foi feito **com os dados atuais do projeto**: da coleta à geração de insights.")
BASE = st.session_state["api_url"]

# ---- dados das etapas (API quando disponível; senão, local)
try:
    rel = api_client.qualidade(BASE)
    lista_checks = [(c["verificacao"], c["ok"], c["detalhe"]) for c in rel["resumo_verificacoes"]]
    origem_q = "API"
except (api_client.ApiIndisponivel, api_client.ApiErro):
    rel = relatorio_qualidade()
    lista_checks = checks(rel)
    origem_q = "LOCAL"
try:
    hist_ia = api_client.historico_ia(BASE, 200)
except Exception:  # noqa: BLE001
    hist_ia = []
try:
    prev = prever_emissoes(emissoes_para_graficos()[0])
except ValueError:
    prev = None

e, n, o, c = rel["emissoes"], rel["noticias"], rel["ods"], rel["corpus"]
aprovadas = sum(1 for _, ok, _ in lista_checks if ok)
cols = st.columns(6)
cols[0].metric("1 · Coleta", f"{(n.get('n') or 0) + (o.get('n') or 0)} textos", help="Manchetes + trechos dos ODS coletados por scraping")
cols[1].metric("2 · Qualidade", f"{aprovadas}/{len(lista_checks)} ✔")
cols[2].metric("3 · Integração", f"{c.get('n') or 0} docs")
cols[3].metric("4 · Modelagem", "3 modelos")
cols[4].metric("5 · Insights", f"{len(hist_ia)} gerações")
cols[5].metric("6 · Apresentação", "dashboard + API")

aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs(["1 · Coleta", "2 · Limpeza e qualidade", "3 · Integração", "4 · Modelagem e IA", "5 · Insights", "6 · Apresentação"])

with aba1:
    st.markdown("Os dados chegam por **quatro caminhos**. Os textos vêm de scraping que **verifica o robots.txt** antes de coletar.")
    linhas = [
        {"fonte": "Notícias ESG (portal de notícias)", "como": "scraping (BeautifulSoup)", "arquivo": "Data/raw/noticias_esg.csv", "registros": n.get("n", 0), "última coleta": n.get("ultima_coleta")},
        {"fonte": "Páginas dos ODS 12 e 13", "como": "scraping (BeautifulSoup)", "arquivo": "Data/raw/ods_conteudo.csv", "registros": o.get("n", 0), "última coleta": o.get("ultima_coleta")},
        {"fonte": "Atividade e emissões da empresa", "como": "gerador sintético (seed fixa)", "arquivo": "Data/processed/amostra_emissoes.csv", "registros": (e.get("n_registros", 0) - e.get("por_origem", {}).get("api", 0)), "última coleta": "—"},
        {"fonte": "Registros enviados por sistemas externos", "como": "API: POST /emissoes", "arquivo": "Data/raw/emissoes_enviadas_api.csv", "registros": e.get("por_origem", {}).get("api", 0), "última coleta": "—"},
        {"fonte": "Planilhas do usuário", "como": "upload de CSV (sessão)", "arquivo": "(memória da sessão)", "registros": 0 if st.session_state.get("df_uploads") is None else len(st.session_state["df_uploads"]), "última coleta": "—"},
    ]
    st.dataframe(pd.DataFrame(linhas), hide_index=True)
    st.info("**Dados reais × sintéticos:** os textos (manchetes e ODS) são **reais**, coletados da web. Os dados de atividade/emissão são **sintéticos** (demonstração); "
            "os fatores de emissão são valores de referência. Empresas reais alimentam o sistema por `POST /emissoes` ou upload de CSV.")

with aba2:
    st.markdown(f"**{aprovadas} de {len(lista_checks)} verificações aprovadas** (fonte: {origem_q}).")
    st.progress(aprovadas / len(lista_checks) if lista_checks else 0.0)
    st.dataframe(pd.DataFrame([{"verificação": nome, "resultado": "✅" if ok else "❌", "detalhe": det} for nome, ok, det in lista_checks]), hide_index=True)
    if n.get("urls_apontam_para_listagem"):
        st.warning("As URLs das notícias da **amostra** apontam para a página de listagem, não para as matérias. Uma coleta real com `scrape_noticias_esg.py` resolve.")
    st.caption("Detalhes e gráficos na página *Estatísticas e qualidade*; relatório completo em `Docs/Data_Report/Data_Quality_Report.md`.")

with aba3:
    st.markdown("Tudo passa pela mesma camada (`Code/esg_core`): carregamento com schema defensivo, validação e transformação em formatos prontos para análise e IA.")
    st.dataframe(pd.DataFrame([
        {"origem": "noticias_esg.csv + ods_conteudo.csv", "transformação": "normalização, deduplicação, ids estáveis, datas honestas (nunca data de coleta como publicação)", "resultado": "corpus_llm.jsonl", "usado por": "resumos, perguntas, sentimento"},
        {"origem": "amostra_emissoes.csv + emissoes_enviadas_api.csv + uploads", "transformação": "validação linha a linha (formato, positivos, emissão = quantidade × fator)", "resultado": "tabela única com coluna 'origem'", "usado por": "gráficos, previsão, API"},
        {"origem": "emissões consolidadas", "transformação": "agregação por unidade, atividade e mês; texto com números em pt-BR", "resultado": "contexto_relatorio.json / texto de contexto", "usado por": "insights e perguntas (IA ancorada em números)"},
        {"origem": "saídas de IA", "transformação": "JSON validado + verificação de fidelidade + registro de auditoria", "resultado": "Data/processed/ia/historico.jsonl", "usado por": "painel de insights, governança"},
    ]), hide_index=True)
    st.markdown("**Artefatos presentes:**")
    for nome, caminho in [("Corpus (JSONL)", paths.caminho_corpus()), ("Contexto de relatório", paths.caminho_contexto_relatorio()),
                          ("Gabarito de sentimento", paths.processed_dir() / "avaliacao" / "sentimento_gold_template.csv"),
                          ("Previsões de sentimento", paths.processed_dir() / "sentimento_noticias.csv"),
                          ("Histórico de auditoria da IA", paths.caminho_ia_dir() / "historico.jsonl")]:
        st.write(("✅ " if caminho.is_file() else "⬜ ") + f"{nome} — `{caminho.name}`")

with aba4:
    modelo_local = {}
    try:
        modelo_local = api_client.status_modelo(BASE)
    except Exception:  # noqa: BLE001
        pass
    ia_status = {}
    try:
        ia_status = api_client.status_ia(BASE)
    except Exception:  # noqa: BLE001
        pass
    st.dataframe(pd.DataFrame([
        {"modelo": "Previsão de emissões (tendência + sazonalidade)", "tipo": "estatístico, transparente", "roda": "local (Python)", "tarefa": "prever os próximos meses",
         "situação": (f"MAPE {prev['mape_melhor']}% no backtest; meta < 15% {'atingida' if prev['atinge_meta'] else 'não atingida'}" if prev else "dados insuficientes")},
        {"modelo": "DistilBERT multilíngue de sentimento", "tipo": "encoder pequeno (Hugging Face)", "roda": "local (CPU, offline)", "tarefa": "sentimento das manchetes",
         "situação": ("carregado" if modelo_local.get("carregado") else "não carregado") + (" · cache presente" if modelo_local.get("cache_presente") else " · cache ausente") if modelo_local else "API offline"},
        {"modelo": "LLM online (OpenAI/Anthropic)", "tipo": "LLM generativo via API", "roda": "provedor (nuvem)", "tarefa": "resumos, perguntas, insights",
         "situação": ("configurado: " + ", ".join(p["nome"] for p in ia_status["provedores"] if p["configurado"])) if ia_status.get("algum_configurado") else ("sem chave configurada" if ia_status else "API offline")},
    ]), hide_index=True)
    st.markdown("**Por que três modelos?** Cada um resolve o que faz melhor, com o menor custo: um método estatístico explicável para números, um modelo pequeno local para classificar muitos textos curtos "
                "sem custo por chamada, e um LLM online para tarefas que exigem linguagem (resumir, responder, recomendar) — sempre com prompts versionados e verificação automática.")

with aba5:
    if not hist_ia:
        st.info("Nenhuma geração de IA registrada ainda. Use *Resumos com IA*, *Pergunte aos dados* ou *Insights e previsão*.")
    else:
        dfh = pd.DataFrame(hist_ia)
        a, b, c2, d = st.columns(4)
        a.metric("Gerações", len(dfh))
        b.metric("Reaproveitadas do cache", int(dfh["cache"].fillna(False).sum()))
        fid = dfh["fidelidade_ok"].dropna()
        c2.metric("Com fidelidade ✔", f"{int(fid.sum())}/{len(fid)}" if len(fid) else "—")
        d.metric("Tokens (entrada + saída)", int(dfh["tokens_entrada"].fillna(0).sum() + dfh["tokens_saida"].fillna(0).sum()))
        st.dataframe(dfh[[col for col in ("em", "tipo", "provedor", "modelo", "versao_prompt", "cache", "fidelidade_ok", "saida") if col in dfh]], hide_index=True)
    st.caption("O histórico guarda tipo, modelo, versão do prompt, tokens, fidelidade e um trecho da saída — **nunca o texto de entrada** (governança sem expor conteúdo).")

with aba6:
    st.dataframe(pd.DataFrame([
        {"página": "Dados e gráficos", "pergunta que responde": "Quanto emitimos, onde e quando?", "ação do usuário": "filtrar unidade/atividade/período"},
        {"página": "Notícias e nuvem de palavras", "pergunta que responde": "O que se fala sobre ESG?", "ação do usuário": "buscar, filtrar por tema"},
        {"página": "Resumos com IA", "pergunta que responde": "Qual a essência destes documentos?", "ação do usuário": "escolher documentos ou enviar um relatório e clicar em resumir"},
        {"página": "Pergunte aos dados", "pergunta que responde": "Pergunta livre sobre os dados", "ação do usuário": "digitar a pergunta"},
        {"página": "Insights e previsão", "pergunta que responde": "Para onde vamos e o que fazer?", "ação do usuário": "clicar em gerar insights"},
        {"página": "Análise de texto (LLM local)", "pergunta que responde": "Qual o tom desta notícia?", "ação do usuário": "colar texto ou classificar manchetes"},
    ]), hide_index=True)
    st.markdown("Tudo é acessível também por **API REST** (`/docs`), para integrar com outros sistemas.")
