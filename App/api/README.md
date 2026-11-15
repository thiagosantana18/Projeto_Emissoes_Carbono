# App/api — API REST (FastAPI)

```bash
uvicorn App.api.main:app --reload        # a partir da raiz do projeto
```
Swagger: http://127.0.0.1:8000/docs · ReDoc: http://127.0.0.1:8000/redoc

- `main.py` — app, lifespan (`ESG_LLM_PRELOAD`), rotas de sistema · `routers/` — emissoes, textos, **llm**
- `schemas.py` / `schemas_llm.py` — Request/Response Models · `erros.py` — handlers e envelope de erro padrão
- Lógica de dados e de LLM: `Code/esg_core/` · Documentação das rotas e dos erros: `Docs/API/API_Documentation.md`
