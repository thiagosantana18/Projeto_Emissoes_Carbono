# Monitoramento e Previsão de Emissões de Carbono Corporativas (ESG · ODS 12 e 13)

Projeto de ciência de dados com IA aplicada ao pilar **Ambiental (E)** do ESG, organizado com **CRISP-DM** (ciclo analítico) e **TDSP** (estrutura e documentação).
Ajuda pequenas e médias empresas a enxergar a pegada de carbono **e a transformar o volume de informação ESG em decisões**.

**Versão final:** ciclo completo — coleta → qualidade → integração → modelagem → insights → apresentação — com **resumos, perguntas e recomendações geradas por IA online** (OpenAI/Anthropic),
**sentimento com modelo local** (Hugging Face), **previsão de emissões**, dashboard de 11 páginas e API REST de 21 operações.

## Arquitetura
```
Fontes ──────────► Code/ (pipeline) ──► Data/ ───► Code/esg_core ──► App/api (FastAPI) ◄── App/dashboard (Streamlit)
sites (BeautifulSoup)  data_acquisition/    raw/      dados, validação,   /emissoes  /noticias  /corpus  /previsao  /qualidade
gerador sintético      data_preparation/    processed/ corpus, previsão,    /processar_texto → LLM LOCAL (sentimento, offline)
POST /emissoes, uploads                     Models/    qualidade, IA ───►  /sumarizar  /perguntar  /insights → LLM ONLINE (OpenAI | Anthropic)
```
As chaves de IA ficam **só no servidor** (`.env`). Toda saída de IA traz fontes, versão do prompt, tokens e uma **verificação automática de fidelidade** (números e citações conferidos contra as fontes).

## Como executar
Requer Python 3.10+. A partir da **raiz do projeto**:
```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt

uvicorn App.api.main:app --reload           # API        → http://127.0.0.1:8000/docs   (um terminal)
streamlit run App/dashboard/app.py          # dashboard  → http://localhost:8501        (outro terminal)
```
Dados de exemplo acompanham o projeto: painel, gráficos, previsão e qualidade funcionam logo após a instalação. O dashboard usa a API quando ela está no ar e, se não estiver, cai para os arquivos locais (com aviso).

### IA online (resumos, perguntas, insights) — 3 passos
```bash
copy .env.example .env                        # Windows (Linux/macOS: cp)  → edite e defina OPENAI_API_KEY ou ANTHROPIC_API_KEY
python Code/llm/verificar_api_online.py       # 1 chamada mínima: confere chave, modelo e JSON
python Scripts/gerar_evidencias_ia.py --comparar-prompts    # saídas reais → Docs/Project/Evidencias_IA.md
```
Sem chave, tudo continua funcionando e as rotas de IA respondem **503** com a instrução do que fazer. Respostas idênticas vêm do cache (sem nova cobrança) e há um teto local de chamadas por hora.
⚠️ Textos enviados à IA saem para o provedor: não envie dados pessoais ou confidenciais.

### Sentimento com modelo local (opcional)
```bash
pip install -r requirements-llm.txt && python Code/llm/baixar_modelo.py    # uma vez, com internet (~0,5 GB)
python Code/llm/verificar_modelo.py                                         # carga, memória, latência
```

### Atualizar dados e documentos gerados
```bash
python Scripts/atualizar_dados.py                  # scraping (ODS + notícias, com robots.txt) → corpus
python Scripts/gerar_relatorio_qualidade.py        # Docs/Data_Report/Data_Quality_Report.md
python Scripts/remover_legados.py                  # lista resíduos de versões antigas (--executar remove)
```
Se você já tem seus `Data/raw/noticias_esg.csv` e `ods_conteudo.csv` reais, **mantenha-os**.

## O que há no dashboard (menu lateral)
| Seção | Página | O que responde |
|---|---|---|
| Projeto | Visão geral · **Ciclo de dados** | o problema e a solução · cada etapa do ciclo com números reais |
| Dados e análises | Dados e gráficos · Notícias e nuvem de palavras · Estatísticas e qualidade | quanto emitimos, o que se fala, os dados são confiáveis? |
| **IA e insights** | **Resumos com IA** | resume notícias/ODS coletados ou **um relatório em PDF**; compara prompts v1 × v2 |
| | **Pergunte aos dados** | perguntas em linguagem natural, com fontes (e "não sei" quando não há base) |
| | **Insights e previsão** | previsão com backtest + destaques, riscos e recomendações ligadas aos ODS |
| | Análise de texto (LLM local) | sentimento de um texto ou das manchetes |
| Serviços | Upload e download · API (FastAPI) | enviar dados · testar a API |

## API (21 operações — detalhes e envelope de erros em `Docs/API/API_Documentation.md`)
| Grupo | Rotas |
|---|---|
| Emissões | `GET/POST /emissoes` · `POST /emissoes/lote` · `GET /emissoes/resumo` |
| Textos coletados | `GET /noticias` · `/ods` · `/corpus` · `/corpus/contexto-relatorio` |
| LLM local | `POST /processar_texto` (+ `/lote`) · `GET /modelo/status` · `POST /modelo/carregar` |
| **IA online** | **`POST /sumarizar`** · `/sumarizar/corpus` · `/perguntar` · `/insights/emissoes` · `GET /ia/status` · `/ia/historico` |
| Análises | `GET /previsao/emissoes` · `/qualidade` · `/health` |

Erros: sempre `{codigo, mensagem, detalhes, sugestao, request_id}` (422, 404, 429, 502, 503, 504…).

## Estrutura de pastas (TDSP)
```
App/api/ · App/dashboard/       API FastAPI · dashboard Streamlit (views/, ui_ia.py, api_client.py)
Code/esg_core/                  dados, validação, corpus, previsão, qualidade, llm/ (sentimento local), ia/ (IA online: provedores, prompts, sumarização, QA, insights, fidelidade)
Code/data_acquisition/ · data_preparation/ · llm/        scrapers e gerador · corpus · scripts do LLM local e da IA online
Data/raw|processed|interim|external/      Models/ (cache do modelo local, não versionado)
Docs/Project|Data_Report|Model_Report|API|Presentations/     Scripts/     tests/
```

## Testes
```bash
python -m unittest discover -s tests -v      # ou: pytest
pip install -r requirements-dev.txt           # inclui FastAPI + httpx: habilita os testes de API (28 pulados sem isso)
```
**139 testes** (111 executam sem FastAPI). Clientes de IA, LLM local e rotas usam **dublês** (HTTP/LLM/pipeline simulados): nenhuma chamada real a provedores ou ao modelo foi feita no desenvolvimento.
A validação real é feita por `verificar_api_online.py`, `gerar_evidencias_ia.py` e `verificar_modelo.py`.

## Documentação (TDSP)
`Docs/Project/Project_Charter.docx` (v5) · `Docs/Data_Report/Data_Summary_Report.docx` (v5) · `Data_Quality_Report.md` · `Docs/Model_Report/Model_Report.md` · `Docs/Project/Exit_Report.md` ·
`Prompt_Engineering.md` · `LLM_Model_Selection.md` · `Decision_Log.md` (ADR-001 a 025) · `Docs/API/API_Documentation.md` · `Docs/Presentations/Apresentacao_Solucao_Final.docx` · `CHANGELOG.md`

## Status
- [x] Ciclo completo implementado e documentado · IA online (resumo, perguntas, insights) · LLM local (sentimento) · previsão com backtest · dashboard final
- [ ] **Validar com provedor real** (`verificar_api_online.py`, `gerar_evidencias_ia.py`) e preencher a avaliação humana
- [ ] **Medir o sentimento**: rotular o gabarito (≥ 50 manchetes reais) · rodar com **dados reais** da empresa · integrar a Climatiq API

## Avisos
- Dados de atividade/emissão **sintéticos** (demonstração); textos de notícias e ODS são **reais** (scraping). Fatores de emissão: valores de referência fixos.
- API **sem autenticação**: uso local. Resumos e respostas de IA devem ser **revisados por uma pessoa** antes de apoiar decisões.
