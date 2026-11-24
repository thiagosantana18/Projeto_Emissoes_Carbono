"""
API REST — Monitoramento e Previsão de Emissões de Carbono Corporativas (ESG).

Executar (a partir da raiz do projeto):
    uvicorn App.api.main:app --reload
Documentação interativa: http://127.0.0.1:8000/docs   (Swagger UI)
                         http://127.0.0.1:8000/redoc  (ReDoc)
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from esg_core import paths
from esg_core.env import carregar_dotenv
from esg_core.ia.servico import obter_servico_ia
from esg_core.llm.errors import ErroLLM
from esg_core.llm.sentimento import dependencias_instaladas, obter_servico

from .erros import registrar_handlers
from .routers import analises, emissoes, ia, llm, textos
from .schemas import HealthOut

VERSAO = "1.2.0"
carregar_dotenv()    # lê o .env da raiz (chaves de IA); não sobrescreve variáveis já definidas no ambiente
log = logging.getLogger("esg.api")

DESCRICAO = """
API do projeto de **monitoramento de emissões de carbono corporativas** (pilar Ambiental do ESG; ODS 12 e 13).

Permite **consultar** (GET) e **enviar** (POST) dados de atividade/emissão e **consultar** os dados textuais
coletados por web scraping, e **analisar textos com um modelo de linguagem do Hugging Face executado localmente**
(`POST /processar_texto`) e **usar IA online (OpenAI/Anthropic)** para sumarizar textos, responder perguntas e gerar insights
(`/sumarizar`, `/perguntar`, `/insights/emissoes`). As chaves ficam só no servidor. Serve como ponto de integração para outros sistemas (ERP, BI, planilhas).

Todos os erros usam o mesmo envelope JSON (`codigo`, `mensagem`, `detalhes`, `sugestao`, `request_id`).

> ⚠️ Protótipo acadêmico: **sem autenticação**. Não exponha publicamente.
"""

TAGS = [
    {"name": "Emissões", "description": "Consulta e envio de registros de atividade e emissão (kgCO2e)."},
    {"name": "Textos", "description": "Manchetes e trechos coletados via scraping (BeautifulSoup)."},
    {"name": "LLM local", "description": "Análise de texto com modelo Hugging Face local (sentimento) e estado do modelo."},
    {"name": "IA online", "description": "Sumarização, perguntas e respostas e insights com OpenAI/Anthropic (engenharia de prompts + verificação de fidelidade)."},
    {"name": "Análises", "description": "Previsão de emissões (backtest) e qualidade dos dados."},
    {"name": "Preparação para LLM", "description": "Corpus e contexto numérico preparados para as tarefas de LLM."},
    {"name": "Sistema", "description": "Saúde da API."},
]

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """ESG_LLM_PRELOAD=1 carrega o modelo na subida; se falhar, a API continua no ar (503 nas rotas de LLM)."""
    if os.environ.get("ESG_LLM_PRELOAD", "0").strip().lower() in {"1", "true", "sim", "yes", "on"}:
        try:
            obter_servico().carregar()
        except ErroLLM as exc:
            log.warning("Pré-carga do modelo falhou (a API segue no ar): %s", exc.mensagem)
    yield


app = FastAPI(title="API — Emissões de Carbono Corporativas (ESG)", version=VERSAO,
              description=DESCRICAO, openapi_tags=TAGS, lifespan=lifespan)
registrar_handlers(app)

app.include_router(emissoes.router)
app.include_router(textos.router)
app.include_router(llm.router)
app.include_router(ia.router)
app.include_router(analises.router)


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
    llm_estado = {"dependencias_instaladas": dependencias_instaladas(), "modelo_carregado": obter_servico().esta_carregado(),
                  "ia_online_configurada": obter_servico_ia().status()["algum_configurado"]}
    return {"status": "ok", "versao": VERSAO, "arquivos": arquivos, "llm": llm_estado}
