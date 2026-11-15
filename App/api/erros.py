"""Tratamento centralizado de erros: todo erro da API sai no mesmo envelope (ver schemas_llm.ErroResposta)."""
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from esg_core.erros_http import SUGESTOES_HTTP, codigo_para_status, detalhes_de_validacao, montar_erro
from esg_core.llm.errors import ErroLLM

log = logging.getLogger("esg.api")


def _rid(request: Request):
    return getattr(request.state, "request_id", None)


def _resposta(status: int, corpo: dict, headers=None) -> JSONResponse:
    return JSONResponse(status_code=status, content=corpo, headers=headers)


def registrar_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        try:
            resposta = await call_next(request)
        except Exception:  # noqa: BLE001  (último recurso: nunca vazar traceback para o cliente)
            log.exception("Erro não tratado [request_id=%s] %s %s", rid, request.method, request.url.path)
            resposta = _resposta(500, montar_erro("ERRO_INTERNO", "Erro interno inesperado.",
                                                  sugestao=SUGESTOES_HTTP[500], request_id=rid))
        resposta.headers["X-Request-ID"] = rid
        return resposta

    @app.exception_handler(ErroLLM)
    async def tratar_erro_llm(request: Request, exc: ErroLLM):
        if exc.status_code >= 500:
            log.error("%s [request_id=%s]: %s", exc.codigo, _rid(request), exc.mensagem)
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        return _resposta(exc.status_code,
                         montar_erro(exc.codigo, exc.mensagem, exc.detalhes, exc.sugestao, _rid(request)), headers)

    @app.exception_handler(RequestValidationError)
    async def tratar_validacao(request: Request, exc: RequestValidationError):
        return _resposta(422, montar_erro("DADOS_INVALIDOS", "Os dados enviados são inválidos.",
                                          detalhes_de_validacao(exc.errors()), SUGESTOES_HTTP[422], _rid(request)))

    @app.exception_handler(StarletteHTTPException)
    async def tratar_http(request: Request, exc: StarletteHTTPException):
        mensagem = exc.detail if isinstance(exc.detail, str) else "Erro na requisição."
        return _resposta(exc.status_code,
                         montar_erro(codigo_para_status(exc.status_code), mensagem,
                                     sugestao=SUGESTOES_HTTP.get(exc.status_code), request_id=_rid(request)),
                         getattr(exc, "headers", None))

    @app.exception_handler(ResponseValidationError)
    async def tratar_resposta_invalida(request: Request, exc: ResponseValidationError):
        log.error("Resposta fora do contrato [request_id=%s]: %s", _rid(request), exc.errors())
        return _resposta(500, montar_erro("RESPOSTA_INVALIDA",
                                          "A resposta gerada não passou na validação do contrato da API.",
                                          sugestao=SUGESTOES_HTTP[500], request_id=_rid(request)))

    @app.exception_handler(Exception)
    async def tratar_excecao(request: Request, exc: Exception):
        log.exception("Erro não tratado [request_id=%s]", _rid(request))
        return _resposta(500, montar_erro("ERRO_INTERNO", "Erro interno inesperado.",
                                          sugestao=SUGESTOES_HTTP[500], request_id=_rid(request)))
