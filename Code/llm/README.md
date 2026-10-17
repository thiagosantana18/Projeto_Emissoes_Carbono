# Code/llm — reservado para a Etapa 4 (NÃO implementado)

Nesta etapa a pasta existe só para **fixar o contrato** com a camada de dados. Nenhum código de LLM foi escrito.

Entradas já prontas (geradas por `Code/data_preparation/build_corpus.py`):

| Tarefa planejada | Entrada | Avaliação |
|---|---|---|
| Classificação de sentimento | `Data/processed/corpus_llm.jsonl` (tipo `noticia`) | `Data/processed/avaliacao/sentimento_gold_template.csv` |
| Resumo automático | `corpus_llm.jsonl` (campo `texto`) | rubrica humana (ver `Docs/Project/LLM_Readiness.md`) |
| Perguntas e respostas | `corpus_llm.jsonl` (+ `doc_id`/`url` para citar a fonte) | `avaliacao/qa_gold_template.csv` |
| Geração de relatórios | `Data/processed/contexto_relatorio.json` | checagem de fidelidade numérica |

Módulos previstos: `client.py` (cliente do provedor, chave via `.env`), `sentimento.py`, `resumo.py`, `qa.py`,
`relatorio.py`, `prompts/`. Leitura dos dados: `esg_core.data_access.carregar_corpus()` /
`carregar_contexto_relatorio()` ou as rotas `GET /corpus` e `GET /corpus/contexto-relatorio` da API.
