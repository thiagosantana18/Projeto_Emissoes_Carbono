# Monitoramento e Previsão de Emissões de Carbono Corporativas (ESG · ODS 12 e 13)

Projeto de ciência de dados com IA aplicada ao pilar **Ambiental (E)** do ESG, organizado com **CRISP-DM** (ciclo analítico)
e **TDSP** (estrutura e documentação). Ajuda pequenas e médias empresas a enxergar, de forma contínua, a sua pegada de carbono.

**Etapa atual (4):** LLM local (Hugging Face) integrado à API FastAPI · respostas estruturadas e erros padronizados · dashboard consumindo a API.
**Ainda não implementado:** previsão de emissões (Modeling) e as demais tarefas de LLM (resumo, Q&A, relatórios).

## Arquitetura
```
Fontes ───────────► Code/ (pipeline) ──► Data/ ───► Code/esg_core ──┬─► App/api  (FastAPI) ◄── Dashboard (Streamlit)
sites (BeautifulSoup)  data_acquisition/    raw/        (dados,       │     /emissoes  /noticias  /corpus
gerador sintético      data_preparation/    processed/   validação,   │     /processar_texto  /modelo/status
POST /emissoes, uploads                     Models/      corpus,      └──► esg_core.llm ──► modelo Hugging Face LOCAL
                                           (cache HF)    LLM)                              (Models/hf_cache, offline)
```

## Como executar
Requer Python 3.10+. A partir da **raiz do projeto**:
```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt

streamlit run App/dashboard/app.py          # dashboard  → http://localhost:8501
uvicorn App.api.main:app --reload           # API        → http://127.0.0.1:8000/docs   (outro terminal)
```
Os dados de exemplo acompanham o projeto: dashboard e API (rotas de dados) funcionam logo após a instalação.
O dashboard usa a API quando ela está no ar e, se não estiver, **cai automaticamente para os arquivos locais** (com aviso).

### LLM local (sentimento) — passo único de preparação
```bash
pip install -r requirements-llm.txt          # torch + transformers (CPU)
python Code/llm/baixar_modelo.py             # UMA vez, com internet (~0,5 GB) → Models/hf_cache
python Code/llm/verificar_modelo.py          # confere carga, memória, latência e 3 frases de teste
```
Depois disso tudo roda **offline**. Sem esses passos a API segue funcionando e `/processar_texto` responde **503** com a instrução do que falta.
Modelo escolhido e justificativa: `Docs/Project/LLM_Model_Selection.md`. Variáveis de configuração: `.env.example`.

### Atualizar dados (opcional, precisa de internet)
```bash
python Scripts/atualizar_dados.py                 # scraping (ODS + notícias) → corpus para LLM
python Scripts/atualizar_dados.py --sem-scraping  # só reconstrói o corpus
python Code/llm/avaliar_sentimento.py prever      # sentimento de todas as notícias → Data/processed/sentimento_noticias.csv
```
Os scrapers **verificam o robots.txt antes de coletar**. Se você já tem seus `Data/raw/noticias_esg.csv` e `ods_conteudo.csv` reais, **mantenha-os**.

### Atualizando de uma versão anterior
Extrair um zip por cima de uma pasta antiga **não apaga** arquivos removidos. Rode `python Scripts/remover_legados.py` (lista) e
`python Scripts/remover_legados.py --executar` (remove `App/dashboard/README_app.md` e `Code/genai_reporting/`).

## O que há no dashboard (menu lateral)
| Seção | Página | Conteúdo |
|---|---|---|
| Projeto | Visão geral | problema, objetivos, justificativa dos ODS, arquitetura, diagnóstico de caminhos |
| Dados e análises | **Dados e gráficos** | **consome `GET /emissoes` da API** (fallback local), filtros persistentes, gráficos Plotly |
| | Notícias e nuvem de palavras | manchetes, busca, tags, nuvem de palavras e ranking |
| | Estatísticas e qualidade | estatísticas descritivas, Pareto, checklist de qualidade |
| Serviços | Upload e download | upload de CSV com validação linha a linha, modelo de CSV, downloads |
| | API (FastAPI) | cliente de demonstração (GET, POST, respostas brutas e erros) |
| IA e LLM | **Análise de texto (LLM local)** | estado do modelo, sentimento de um texto, classificação das manchetes (via API) |
| | Preparação dos dados | casos de uso × prontidão dos dados, artefatos |

## API (resumo — detalhes e envelope de erros em `Docs/API/API_Documentation.md`)
| Método | Rota | Função |
|---|---|---|
| GET / POST | `/emissoes` · `/emissoes/lote` · GET `/emissoes/resumo` | consulta, envio e agregações |
| GET | `/noticias` · `/ods` · `/corpus` · `/corpus/contexto-relatorio` | textos coletados e dados para LLM |
| **POST** | **`/processar_texto`** · `/processar_texto/lote` | **sentimento com modelo Hugging Face local** |
| GET / POST | `/modelo/status` · `/modelo/carregar` | estado e aquecimento do modelo |
| GET | `/health` | status |

Erros: sempre `{codigo, mensagem, detalhes, sugestao, request_id}` — 422 (entrada), 429 (modelo ocupado), 500 (falha), 503 (modelo indisponível), 504 (tempo limite).

## Estrutura de pastas (TDSP)
```
App/api/            FastAPI (main, schemas, schemas_llm, erros, routers/)
App/dashboard/      Streamlit (app.py, ui_helpers.py, api_client.py, views/)
Code/esg_core/      dados, validação, corpus, textos e llm/ (serviço de sentimento, config, erros, métricas)
Code/llm/           scripts: baixar_modelo, verificar_modelo, avaliar_sentimento
Code/data_acquisition/  scrapers + gerador de amostra        Code/data_preparation/  build_corpus.py
Data/raw|processed|interim|external/        Models/ (cache do modelo, não versionado)
Docs/Project|Data_Report|API|Model_Report|Presentations/     Scripts/ (atualizar_dados, remover_legados)     tests/
```

## Testes
```bash
python -m unittest discover -s tests -v      # ou: pytest
pip install -r requirements-dev.txt           # inclui FastAPI + httpx: habilita os testes de API (20 pulados sem isso)
```
Os testes do LLM usam um **pipeline falso** (nada é baixado). A inferência real do modelo é verificada por `Code/llm/verificar_modelo.py`.

## Documentação
- `Docs/Project/Project_Charter.docx` (v4) · `Docs/Data_Report/Data_Summary_Report.docx` (v4, dicionário de dados)
- `Docs/Project/LLM_Model_Selection.md` — **escolha do modelo, requisitos de hardware e como a integração local funciona**
- `Docs/Project/Decision_Log.md` (ADR-001 a 015) · `Docs/Project/LLM_Readiness.md` · `Docs/API/API_Documentation.md` · `CHANGELOG.md`

## Status
- [x] Business Understanding · Data Acquisition · Dashboard multipágina · API FastAPI · preparação de dados para LLM
- [x] LLM local integrado à API (sentimento) · Response Models · tratamento de erros padronizado · dashboard consumindo a API
- [ ] **Medir a qualidade do sentimento**: rotular o gabarito (≥ 50 manchetes reais) e rodar `avaliar_sentimento.py avaliar`
- [ ] Data Quality Report completo · Modeling (previsão de emissões) · resumo, Q&A e relatórios com LLM
- [ ] Consulta real à Climatiq API (hoje os fatores são valores de referência rotulados por fonte)

## Avisos
- Dados de atividade **sintéticos** (demonstração). Fatores de emissão: valores de referência fixos.
- A inferência real do modelo e a execução das rotas FastAPI foram **verificadas por testes com componentes simulados**; rode `verificar_modelo.py` e a suíte completa na sua máquina.
- API **sem autenticação**: uso local. Conteúdo de terceiros coletado por scraping: só metadados/trechos curtos.
