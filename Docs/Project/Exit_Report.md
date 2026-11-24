# Exit Report (TDSP) — encerramento do projeto

**Projeto:** Monitoramento e Previsão de Emissões de Carbono Corporativas com IA · **Pilar ESG:** Ambiental · **ODS:** 12 e 13 · **Metodologia:** CRISP-DM + TDSP

## 1. O que foi entregue
Uma aplicação que percorre o ciclo de ciência de dados completo: **coleta** (scraping com robots.txt, API, uploads) → **limpeza e qualidade** (validação, relatório) → **integração** (camada única `esg_core`)
→ **modelagem** (previsão estatística, sentimento local, LLM online) → **insights** (resumos, perguntas, recomendações com fidelidade verificada) → **apresentação** (dashboard de 11 páginas, API REST de 21 operações, documentos).
Código: 71 arquivos Python; **139 testes automatizados** (111 executados e aprovados no ambiente de desenvolvimento; 28 de API pulados por falta do FastAPI nesse ambiente).

## 2. Objetivos do Project Charter × resultado
| Objetivo / critério | Resultado | Evidência e ressalva |
|---|---|---|
| Atualizar dados mensal/trimestralmente | ✅ Atingido | scraping agendável (`Scripts/atualizar_dados.py`), upload de CSV, `POST /emissoes` |
| Previsão com MAPE < 15% | ✅ Atingido **na amostra sintética** | MAPE 3,53% (backtest, 30 previsões) — `Model_Report.md`. Não prova desempenho em dados reais |
| Identificar as principais fontes de emissão | ✅ Atingido (análise descritiva) | Diesel (frota) 57,6%; Gás natural (caldeira) 25,2%; Eletricidade (rede) 11,6%. É análise de concentração (Pareto), não *feature importance* de um modelo de ML |
| Conformidade da coleta (robots.txt) | ✅ Implementado | verificação antes de cada coleta; lógica testada com robots.txt de exemplo. A coleta real depende da internet do usuário |
| API documentada, com validação de entrada | ✅ Atingido | 21 operações, OpenAPI, envelope de erro único; testes de API escritos (executar com FastAPI instalado) |
| Rastreabilidade dos dados para IA | ✅ Atingido | `doc_id`, fonte e URL em todo documento; data de coleta nunca vira data de publicação |
| Qualidade dos dados | 🟡 12 de 13 verificações | falha: notícias: urls de matéria (não da listagem) (18 apontam para listagem) — a **amostra** de notícias aponta para a listagem; uma coleta real resolve |
| Sumarização automática com LLM online | 🟡 Implementada e testada com LLM simulado | prompts versionados, map-reduce, PDF, fidelidade automática. **Não executada contra provedor real** — rodar `Scripts/gerar_evidencias_ia.py` |
| Qualidade do relatório por IA (sem números divergentes) | 🟡 Mecanismo pronto; medição pendente | verificação automática de números e citações em toda saída |
| Qualidade do sentimento em manchetes | ⏳ Pendente | exige rotular o gabarito (≥ 50 manchetes reais) |
| Reduzir ≥ 80% do tempo de elaboração do relatório ESG | ⏳ **Não medido** | não há cronometragem com usuários; a evidência é qualitativa (geração em segundos a poucos minutos, conforme o provedor) |
| Dashboard simples e profundo | ✅ Entregue | 11 páginas em 4 seções; fluxo de 3 passos; erros com ação sugerida. Não houve teste de usabilidade com usuários |

Legenda: ✅ atingido · 🟡 parcial · ⏳ pendente.

## 3. Entregáveis TDSP
| Artefato | Local | Versão |
|---|---|---|
| Project Charter | `Docs/Project/Project_Charter.docx` | v5 |
| Data Summary Report (com dicionário de dados e integração) | `Docs/Data_Report/Data_Summary_Report.docx` | v5 |
| Data Quality Report | `Docs/Data_Report/Data_Quality_Report.md` | gerado por script |
| Model Report | `Docs/Model_Report/Model_Report.md` | final |
| Engenharia de prompts | `Docs/Project/Prompt_Engineering.md` | final |
| Escolha do modelo local | `Docs/Project/LLM_Model_Selection.md` | final |
| Registro de decisões (ADR-001 a 025) e lições | `Docs/Project/Decision_Log.md` | final |
| Documentação da API | `Docs/API/API_Documentation.md` | final |
| Apresentação da solução | `Docs/Presentations/Apresentacao_Solucao_Final.docx` | final |
| Exit Report | este documento | final |

## 4. Como o cliente pode aceitar a solução em ~15 minutos (checklist)
1. `pip install -r requirements.txt` · `streamlit run App/dashboard/app.py` → abre a **Visão geral** e o **Ciclo de dados** (todas as etapas com números).
2. Em *Dados e gráficos*, filtrar por unidade/atividade e observar a mudança nos gráficos; em *Estatísticas e qualidade*, ver o checklist.
3. `uvicorn App.api.main:app --reload` → `http://127.0.0.1:8000/docs`: testar `GET /emissoes` e `POST /emissoes` (registro novo aparece no dashboard).
4. Copiar `.env.example` para `.env`, colocar **uma** chave (OpenAI ou Anthropic), `python Code/llm/verificar_api_online.py` → deve terminar com "Tudo certo".
5. Em *Resumos com IA*: resumir as notícias coletadas e enviar um relatório em PDF; conferir o painel de **fidelidade** e as **fontes**.
6. Em *Pergunte aos dados*: fazer uma pergunta com resposta nos dados e uma sem (a IA deve dizer que não sabe).
7. `python Scripts/gerar_evidencias_ia.py --comparar-prompts` → `Docs/Project/Evidencias_IA.md` com as saídas reais.
8. (Opcional) `pip install -r requirements-llm.txt`, `python Code/llm/baixar_modelo.py` → página *Análise de texto (LLM local)*.

## 5. Limitações e riscos que permanecem
- **Dados de emissão sintéticos** e fatores de emissão de referência (sem consulta real à Climatiq API). Conclusões numéricas são ilustrativas.
- **Nenhuma chamada a provedor de IA real e nenhuma inferência do modelo local foram executadas** no ambiente de desenvolvimento (sem internet/chaves/bibliotecas). Tudo foi testado com componentes simulados; a primeira execução real pode revelar ajustes (nomes de modelo, limites).
- API sem autenticação (uso local). Textos enviados ao provedor de IA saem do ambiente da empresa.
- Corpus pequeno e de fonte única; sentimento e resumos refletem esse recorte.
- Previsão com 24 meses (2 ciclos sazonais) e dados sintéticos.

## 6. Recomendações de continuidade
1. Rodar com **dados reais** da empresa (POST /emissoes / upload) e repetir backtest e qualidade.
2. Executar `gerar_evidencias_ia.py --comparar-prompts` e preencher a avaliação humana; ajustar prompts com base nos números.
3. Rotular o gabarito de sentimento (≥ 50) e medir; só então usar os resultados em decisões.
4. Integrar a Climatiq API (fatores com versão/ano) e ampliar fontes de notícias.
5. Autenticação na API, banco de dados no lugar de CSV, *embeddings* para a busca quando o corpus crescer, monitoramento de custo.

## 7. Lições aprendidas
1. **Schema drift entre scraper e app** derrubou o dashboard → loaders defensivos + teste de regressão.
2. **Duas versões do mesmo arquivo** geraram "dados não encontrados" → um só arquivo e raiz detectada automaticamente.
3. **Datas honestas:** preencher publicação com data de coleta enganaria citações → nulo no corpus.
4. **Extrair zip sobre projeto antigo não apaga o que foi removido** → `remover_legados.py`.
5. **Não afirmar o que não foi medido:** estimativas e medições são distinguidas em todos os documentos.
6. **LLM sem verificação é risco de conformidade:** a checagem automática de números/citações é tão importante quanto o prompt.
7. **Isolar dependências pesadas e opcionais** (torch, PDF, provedores) mantém o projeto utilizável por quem só quer o dashboard.
8. **Testar com dublês** (HTTP, LLM, pipeline) torna possível validar erros, timeouts e limites sem rede nem custo.
