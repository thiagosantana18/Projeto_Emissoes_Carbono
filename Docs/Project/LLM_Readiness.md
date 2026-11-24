# Preparação para LLM (Etapas 3 e 4)

> **Estado final (Etapa 5):** sentimento (modelo local), **sumarização, perguntas e respostas e insights** (LLM online) estão implementados — ver `Prompt_Engineering.md`, `Model_Report.md` e `Exit_Report.md`.
> As saídas com provedor real devem ser geradas com `Scripts/gerar_evidencias_ia.py`; a qualidade do sentimento depende de rotular o gabarito.

## 1. Dados disponíveis (amostra do projeto)
| Dado | Volume | Natureza | Observação |
|---|---|---|---|
| Manchetes ESG | 18 | título (+ linha fina, quando o scraper capturar) | amostra; o scraper real gera mais |
| Trechos ODS 12/13 | 10 | parágrafos curtos (≤ 600 caracteres) | com `secao` para contexto |
| Emissões | 216 linhas | tabela numérica | vira texto via `contexto_relatorio.json` |
| **Corpus unificado** | **28 documentos / 409 palavras** | JSONL com `doc_id`, `fonte`, `url`, `data_publicacao`, `tags`, `usos_previstos` | |

Schema do documento: `doc_id, tipo, fonte, url, titulo, texto, data_publicacao, data_coleta, idioma, n_palavras, secao, tags, usos_previstos`.

## 2. Casos de uso × prontidão
| Caso de uso | Entrada | Prontidão | Lacuna | Avaliação prevista |
|---|---|---|---|---|
| **Classificação de sentimento** (positivo/negativo/neutro) | manchetes (`tipo = noticia`) | 🟢 implementado (modelo local); qualidade **ainda não medida** | só títulos curtos; **falta gabarito humano para medir a acurácia**; "neutro" tende a ser frequente em títulos | rotular `sentimento_gold_template.csv` (≥ 50 itens); acurácia e F1 por classe |
| **Resumo automático** | `texto` dos documentos, relatórios enviados (TXT/MD/PDF) | 🟡 implementado (LLM online); **ainda sem execução com provedor real** | manchetes são curtas; relatórios longos usam map-reduce e foram testados com textos simulados | `Scripts/gerar_evidencias_ia.py`; fidelidade automática; leitura humana 1–5; comparação com resumo extrativo |
| **Perguntas e respostas (RAG)** | corpus + dados de emissões; recuperação BM25 | 🟡 implementado (`POST /perguntar`); sem execução com provedor real | base pequena (28 docs); sem conjunto de perguntas de referência | `qa_gold_template.csv`: acerto da resposta + **acerto da citação**; pergunta de controle sem resposta nos dados |
| **Geração de relatórios / insights** | contexto numérico + previsão + sentimento | 🟢 implementado (`POST /insights/emissoes`); sem execução com provedor real | fatores de referência fixos; dados sintéticos | **fidelidade numérica**: 100 % dos números do texto devem existir no contexto (checagem automática) |

## 3. Decisões tomadas para facilitar as tarefas com LLM
- **Rastreabilidade:** todo documento tem `doc_id`, `fonte`, `url` → respostas podem citar a origem.
- **Honestidade temporal:** `data_publicacao` é `null` quando desconhecida (nunca substituída pela data de coleta).
- **Grounding numérico:** relatórios devem ser gerados *a partir do JSON de contexto*, nunca de memória do modelo.
- **Acesso uniforme:** `esg_core.data_access.carregar_corpus()` e as rotas `GET /corpus` e `GET /corpus/contexto-relatorio`.
- **Segredos:** chave do provedor via `.env` (`ANTHROPIC_API_KEY` reservada em `.env.example`), nunca no código.

## 4. Arquitetura (sentimento implementado; demais tarefas previstas)
Implementado: `Code/esg_core/llm/` (serviço de sentimento, erros, métricas) → rotas `POST /processar_texto` e `/lote` → página *Análise de texto*; scripts em `Code/llm/`. Previsto: resumo, Q&A (recuperação) e relatório. Cada tarefa grava resultados em `Data/processed/` com metadados (modelo, versão do prompt, data) para auditoria.

## 5. Riscos e mitigação
| Risco | Mitigação |
|---|---|
| Alucinação em relatórios | geração ancorada no JSON de contexto + checagem automática de números |
| Viés/ruído de fonte única | ampliar fontes de notícias antes de avaliar |
| Direitos autorais | só metadados/trechos curtos; avaliar antes de coletar corpo de artigos |
| Custo/latência | processar em lote, cachear resultados por `doc_id` |
| Dados sintéticos dão falsa sensação de precisão | `observacoes` do contexto declaram a natureza dos dados |

## 6. Pendências
1. **Rotular o gabarito de sentimento** (≥ 50 manchetes reais após rodar o scraper) e rodar `python Code/llm/avaliar_sentimento.py avaliar` — sem isso a qualidade do modelo é desconhecida.
2. Executar `python Scripts/gerar_evidencias_ia.py --comparar-prompts` com uma chave real e registrar a avaliação humana (resumo, Q&A, insights).
3. Elaborar 20–30 perguntas de Q&A com resposta esperada e `doc_id_fonte`.
