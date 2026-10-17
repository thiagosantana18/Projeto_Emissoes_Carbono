# Monitoramento e Previsão de Emissões de Carbono Corporativas (ESG · ODS 12 e 13)

Projeto de ciência de dados com IA aplicada ao pilar **Ambiental (E)** do ESG, organizado com **CRISP-DM** (ciclo analítico)
e **TDSP** (estrutura e documentação). Ajuda pequenas e médias empresas a enxergar, de forma contínua, a sua pegada de carbono.

**Etapa atual (3):** dashboard multipágina · API REST (FastAPI) · scraping aprimorado (BeautifulSoup) · dados preparados para LLM.
**Ainda não implementado:** previsão de emissões (Etapa de Modeling) e tarefas com LLM (Etapa 4).

## Arquitetura
```
Fontes ───────────────► Code/ (pipeline) ─────────► Data/ ──────────► Code/esg_core ─┬─► App/api        (FastAPI)
sites (BeautifulSoup)    data_acquisition/           raw/                (dados,       └─► App/dashboard  (Streamlit)
gerador sintético        data_preparation/           processed/           validação,
POST /emissoes, uploads                              (corpus_llm.jsonl)   corpus)
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
Os dados de exemplo já acompanham o projeto: o dashboard funciona logo após a instalação.

### Atualizar dados (opcional, precisa de internet)
```bash
python Scripts/atualizar_dados.py                 # scraping (ODS + notícias) → corpus para LLM
python Scripts/atualizar_dados.py --sem-scraping  # só reconstrói o corpus
python Scripts/atualizar_dados.py --regenerar-amostra
```
Os scrapers **verificam o robots.txt antes de coletar** e abortam se a fonte não permitir.
> Se você já tem seus próprios `Data/raw/noticias_esg.csv` e `ods_conteudo.csv` de uma coleta real, **mantenha-os** e rode apenas `--sem-scraping`.

## O que há no dashboard (menu lateral)
| Seção | Página | Conteúdo |
|---|---|---|
| Projeto | Visão geral | problema, objetivos, justificativa dos ODS, arquitetura, diagnóstico de caminhos |
| Dados e análises | Dados e gráficos | filtros persistentes, gráficos interativos (Plotly), tabela e download |
| | Notícias e nuvem de palavras | tabela de manchetes, busca, tags, nuvem de palavras e ranking |
| | Estatísticas e qualidade | estatísticas descritivas, Pareto, checklist de qualidade, estatísticas de texto |
| Serviços | Upload e download | upload de CSV com validação linha a linha, modelo de CSV, downloads |
| | API (FastAPI) | cliente de demonstração: GET, POST e rotas de texto |
| Próximos passos | Preparação para LLM | casos de uso × prontidão dos dados, artefatos, corpus |

Cache: `st.cache_data` com chave = data de modificação dos arquivos. Estado de sessão: filtros, uploads e histórico persistem entre páginas.

## API (resumo — detalhes em `Docs/API/API_Documentation.md`)
| Método | Rota | Função |
|---|---|---|
| GET | `/emissoes` | consulta com filtros e paginação |
| POST | `/emissoes` | envia um registro (validado; calcula a emissão se omitida) |
| GET | `/emissoes/resumo` · POST `/emissoes/lote` | agregações · envio em lote |
| GET | `/noticias` · `/ods` · `/corpus` · `/corpus/contexto-relatorio` | textos coletados e dados para LLM |
| GET | `/health` | status |

## Estrutura de pastas (TDSP)
```
App/api/            FastAPI (main, schemas, routers/)
App/dashboard/      Streamlit (app.py, ui_helpers.py, views/)
Code/esg_core/      camada de dados compartilhada (paths, data_access, validation, corpus, text_utils, amostra)
Code/data_acquisition/   scrapers + gerador de amostra       Code/data_preparation/  build_corpus.py
Code/llm/           reservado para a Etapa 4 (sem código)    Code/modeling/          (Etapa de Modeling)
Data/raw|processed|interim|external/        Docs/Project|Data_Report|API|Model_Report|Presentations/
Scripts/            atualizar_dados.py                       tests/                  testes automatizados
```

## Testes
```bash
python -m unittest discover -s tests -v      # ou: pytest
pip install -r requirements-dev.txt           # para incluir os testes da API (FastAPI + httpx)
```

## Documentação
- `Docs/Project/Project_Charter.docx` (v3) · `Docs/Data_Report/Data_Summary_Report.docx` (v3, com dicionário de dados)
- `Docs/Project/Decision_Log.md` — decisões (inclui por que **não** usamos Selenium) e lições aprendidas
- `Docs/Project/LLM_Readiness.md` — como os dados serão usados com LLMs · `Docs/API/API_Documentation.md`
- `Data/raw/NOTA_COLETA.md` — histórico de como os dados brutos foram obtidos

## Status
- [x] Business Understanding — Project Charter v3 (problema reavaliado)
- [x] Data Acquisition — API/scraping/amostra; Data Summary Report v3
- [x] Dashboard multipágina · API FastAPI · testes · preparação para LLM
- [ ] Data Quality Report completo / EDA aprofundada
- [ ] Modeling — previsão de emissões (Prophet/SARIMA) e explicabilidade
- [ ] Etapa 4 — tarefas com LLM (sentimento, resumo, Q&A, relatórios)
- [ ] Consulta real à Climatiq API (hoje os fatores são valores de referência rotulados por fonte)

## Avisos
- Dados de atividade **sintéticos** (demonstração). Fatores de emissão: valores de referência fixos.
- API **sem autenticação**: uso local. Não versionamos dados enviados via API (ver `.gitignore`).
- Conteúdo de terceiros coletado por scraping: só metadados/trechos curtos; respeite os termos de uso das fontes.
