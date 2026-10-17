"""
API REST — Monitoramento e Previsão de Emissões de Carbono Corporativas (ESG).

Executar (a partir da raiz do projeto):
    uvicorn App.api.main:app --reload
Documentação interativa: http://127.0.0.1:8000/docs   (Swagger UI)
                         http://127.0.0.1:8000/redoc  (ReDoc)
"""
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from esg_core import paths

from .routers import emissoes, textos
from .schemas import HealthOut

VERSAO = "1.0.0"

DESCRICAO = """
API do projeto de **monitoramento de emissões de carbono corporativas** (pilar Ambiental do ESG; ODS 12 e 13).

Permite **consultar** (GET) e **enviar** (POST) dados de atividade/emissão e **consultar** os dados textuais
coletados por web scraping. Serve como ponto de integração para outros sistemas (ERP, BI, planilhas)
e como fonte de dados para as tarefas de LLM planejadas para a próxima etapa.

> ⚠️ Protótipo acadêmico: **sem autenticação**. Não exponha publicamente.
"""

TAGS = [
    {"name": "Emissões", "description": "Consulta e envio de registros de atividade e emissão (kgCO2e)."},
    {"name": "Textos", "description": "Manchetes e trechos coletados via scraping (BeautifulSoup)."},
    {"name": "Preparação para LLM", "description": "Corpus e contexto numérico preparados para a etapa de LLM."},
    {"name": "Sistema", "description": "Saúde da API."},
]

app = FastAPI(title="API — Emissões de Carbono Corporativas (ESG)", version=VERSAO,
              description=DESCRICAO, openapi_tags=TAGS)

app.include_router(emissoes.router)
app.include_router(textos.router)


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthOut, tags=["Sistema"], summary="Verificar se a API está no ar")
def health():
    """Retorna `status: ok` e quais arquivos de dados existem no servidor."""
    arquivos = {
        "emissoes_base": paths.caminho_emissoes_base().is_file(),
        "noticias": paths.caminho_noticias().is_file(),
        "ods": paths.caminho_ods().is_file(),
        "corpus_llm": paths.caminho_corpus().is_file(),
    }
    return {"status": "ok", "versao": VERSAO, "arquivos": arquivos}
