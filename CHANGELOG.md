# Changelog

## Etapa 5 — IA online, sumarização e dashboard final
**Adicionado**
- `Code/esg_core/ia/`: clientes OpenAI e Anthropic (HTTP, retentativas, adaptação de parâmetros, redação de chaves), **prompts versionados**, sumarização com **map-reduce**, perguntas e respostas (BM25 + abstenção),
  insights de emissões, **verificação de fidelidade** (números e citações), cache, limite de custo e auditoria.
- API: `POST /sumarizar`, `/sumarizar/corpus`, `/perguntar`, `/insights/emissoes`, `GET /ia/status`, `/ia/historico`, `/previsao/emissoes`, `/qualidade` (21 operações no total; API 1.2.0).
- Previsão de emissões (3 métodos, backtest) e relatório de qualidade de dados (`esg_core/previsao.py`, `qualidade.py`).
- Dashboard: **Ciclo de dados**, **Resumos com IA** (corpus, texto, PDF, comparação de prompts), **Pergunte aos dados**, **Insights e previsão**; Visão geral reescrita.
- Scripts: `verificar_api_online.py`, `gerar_evidencias_ia.py`, `gerar_relatorio_qualidade.py`.
- Documentos: Prompt_Engineering, Model_Report, Data_Quality_Report, Exit_Report, ADR-016 a 025; Project Charter e Data Summary Report v5; Apresentação da solução final (Word).
- 68 testes novos (todos executáveis sem rede, chave ou FastAPI, exceto 8 de API).
**Alterado**
- Dashboard organizado pelo ciclo de dados (4 seções, 11 páginas); API 1.1.0 → 1.2.0; `/health` informa IA online; `.env` é lido pela API.
**Removido**
- Página "Preparação dos dados para LLM" (absorvida pelo Ciclo de dados).

## Etapa 4 — LLM local, API robusta, dashboard consumindo a API
**Adicionado**
- `Code/esg_core/llm/` — serviço de sentimento com modelo Hugging Face local (carga preguiçosa, offline por padrão, timeout, fila limitada, validação da saída).
- API: `POST /processar_texto`, `POST /processar_texto/lote`, `GET /modelo/status`, `POST /modelo/carregar`; Response Models em `App/api/schemas_llm.py`.
- Tratamento de erros padronizado (`App/api/erros.py`): envelope `{codigo, mensagem, detalhes, sugestao, request_id}`, `X-Request-ID`, `Retry-After`.
- Dashboard: página **Análise de texto (LLM local)**; **Dados e gráficos** agora consome `GET /emissoes` (com fallback local); `api_client.py`.
- Scripts `Code/llm/` (baixar, verificar, avaliar), `Scripts/remover_legados.py`, `requirements-llm.txt`, `Models/`.
- Documentos: `LLM_Model_Selection.md`, ADR-009 a 015; Project Charter e Data Summary Report v4.
- Testes: 41 novos (27 executáveis sem FastAPI; 14 de API pulados sem FastAPI).
**Alterado**
- ⚠️ Formato de erro de **todas** as rotas: `detail` → envelope padrão (`mensagem`, `detalhes`...).
- API 1.0.0 → 1.1.0; `/health` inclui estado do LLM; página *Preparação* reflete o sentimento implementado.
**Removido**
- `App/dashboard/README_app.md` e `Code/genai_reporting/` (resíduos de versões anteriores; `Code/llm` substitui). Use `Scripts/remover_legados.py` na sua pasta.

## Etapa 3 — Multipágina, API e preparação para LLM
Dashboard multipágina; FastAPI (consulta/envio); scraping aprimorado (BeautifulSoup); corpus JSONL e contexto de relatório; testes; documentos v3.

## Etapa 2 — Interatividade e scraping
Abas, cache, session_state, scraping com BeautifulSoup, nuvem de palavras, upload/download; documentos v2.

## Etapa 1 — Proposta e planejamento
Problemas ESG/ODS, Project Charter v1, Data Summary Report v1, estrutura TDSP, demo Streamlit.
