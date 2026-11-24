import pandas as pd
import streamlit as st

from esg_core import data_access as da
from esg_core import paths
from ui_helpers import corpus, fmt_num

st.title("🧪 Preparação dos dados para LLM")
st.info("Mostra **o quanto os dados estão prontos** para cada tarefa com LLM. A **classificação de sentimento já roda** "
        "com um modelo local (página *Análise de texto*); resumo, Q&A e geração de relatórios seguem como próximas etapas.")

docs = corpus()
dfc = pd.DataFrame(docs)
n_not = int((dfc["tipo"] == "noticia").sum()) if docs else 0
n_ods = int((dfc["tipo"] == "ods_trecho").sum()) if docs else 0

st.subheader("Casos de uso × dados disponíveis")
casos = pd.DataFrame([
    {"Caso de uso": "Classificação de sentimento", "Dados": f"{n_not} manchetes (título + linha fina quando houver)",
     "Prontidão": "🟢 Implementado (modelo local)", "Lacuna / decisão": "Só títulos curtos; falta gabarito humano para medir acurácia (rotular o template e rodar avaliar_sentimento.py)",
     "Artefato preparado": "POST /processar_texto · avaliacao/sentimento_gold_template.csv"},
    {"Caso de uso": "Resumo automático", "Dados": f"{n_ods} trechos de ODS (≤ 600 caracteres)",
     "Prontidão": "🔴 Lacuna", "Lacuna / decisão": "Não há textos longos. Decidir: coletar corpo de artigos (respeitando robots.txt e direitos autorais) ou resumir conjuntos de documentos",
     "Artefato preparado": "corpus_llm.jsonl (campo texto)"},
    {"Caso de uso": "Perguntas e respostas (Q&A / RAG)", "Dados": f"{len(docs)} documentos com fonte, URL e seção",
     "Prontidão": "🟡 Parcial", "Lacuna / decisão": "Base pequena; ampliar fontes. Metadados já permitem citar a origem da resposta",
     "Artefato preparado": "corpus_llm.jsonl + avaliacao/qa_gold_template.csv"},
    {"Caso de uso": "Geração de relatórios (texto)", "Dados": "Agregados numéricos por unidade/atividade/mês",
     "Prontidão": "🟢 Pronto", "Lacuna / decisão": "Fatores de emissão ainda são valores de referência; checar fidelidade numérica do texto gerado",
     "Artefato preparado": "contexto_relatorio.json"},
])
st.dataframe(casos, hide_index=True)

st.subheader("Artefatos")
artefatos = [
    ("Corpus unificado", paths.caminho_corpus(), "python Code/data_preparation/build_corpus.py"),
    ("Contexto de relatório", paths.caminho_contexto_relatorio(), "python Code/data_preparation/build_corpus.py"),
    ("Gabarito de sentimento", paths.processed_dir() / "avaliacao" / "sentimento_gold_template.csv", "python Code/data_preparation/build_corpus.py"),
    ("Gabarito de Q&A", paths.processed_dir() / "avaliacao" / "qa_gold_template.csv", "python Code/data_preparation/build_corpus.py"),
]
for nome, caminho, comando in artefatos:
    st.write(("✅ " if caminho.is_file() else "❌ ") + f"{nome} — `{caminho.name}`" + ("" if caminho.is_file() else f" → gere com `{comando}`"))

if docs:
    st.subheader("Corpus")
    c1, c2, c3 = st.columns(3)
    c1.metric("Documentos", len(dfc))
    c2.metric("Com data de publicação", int(dfc["data_publicacao"].notna().sum()))
    c3.metric("Palavras (média/doc)", fmt_num(dfc["n_palavras"].mean()))
    st.dataframe(dfc[["doc_id", "tipo", "fonte", "titulo", "data_publicacao", "n_palavras", "tags"]], hide_index=True)
    with st.expander("Exemplo de documento (schema)"):
        st.json(docs[0])

ctx = da.carregar_contexto_relatorio()
if ctx:
    with st.expander("Contexto numérico para geração de relatórios (prévia)"):
        st.json({k: ctx[k] for k in ("periodo", "n_registros", "total_kgco2e", "maiores_fontes", "variacao_ultimo_mes_pct")})

st.subheader("Fluxo (sentimento já implementado)")
st.code("""Data/processed/corpus_llm.jsonl ──► [sentimento ✅ | resumo | Q&A com recuperação] ──► resultados + métricas
Data/processed/contexto_relatorio.json ─► [geração de relatório] ──► texto + checagem de fidelidade numérica
Data/processed/avaliacao/*.csv ─────────► avaliação (acurácia, fidelidade, taxa de alucinação)""", language="text")
st.caption("Detalhes em Docs/Project/LLM_Readiness.md.")
