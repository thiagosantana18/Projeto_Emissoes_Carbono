# Data/processed

| Arquivo | Conteúdo | Gerado por |
|---|---|---|
| `amostra_emissoes.csv` | 216 linhas sintéticas: 24 meses × 9 pares unidade/atividade | `generate_sample_emissions.py` |
| `corpus_llm.jsonl` | documentos de texto em schema único (para LLM) | `build_corpus.py` |
| `contexto_relatorio.json` | agregados numéricos para geração de relatórios | `build_corpus.py` |
| `avaliacao/sentimento_gold_template.csv` | gabarito a rotular (positivo/negativo/neutro) | `build_corpus.py` |
| `avaliacao/qa_gold_template.csv` | gabarito de perguntas e respostas (vazio) | `build_corpus.py` |

Schemas e dicionário de dados: `Docs/Data_Report/Data_Summary_Report.docx`.
