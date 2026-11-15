# Changelog

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
