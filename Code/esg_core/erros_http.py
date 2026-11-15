"""
Ajudantes (sem FastAPI) para montar o envelope de erro padrão da API e traduzir erros de validação.

Envelope: {"codigo": "...", "mensagem": "...", "detalhes": [{"campo","problema"}], "sugestao": "...", "request_id": "..."}
"""
from __future__ import annotations

from typing import Optional

CODIGOS_HTTP = {
    400: "REQUISICAO_INVALIDA", 401: "NAO_AUTENTICADO", 403: "ACESSO_NEGADO", 404: "NAO_ENCONTRADO",
    405: "METODO_NAO_PERMITIDO", 409: "CONFLITO", 413: "PAYLOAD_GRANDE_DEMAIS", 422: "DADOS_INVALIDOS",
    429: "MUITAS_REQUISICOES", 500: "ERRO_INTERNO", 503: "SERVICO_INDISPONIVEL", 504: "TEMPO_LIMITE_EXCEDIDO",
}
SUGESTOES_HTTP = {
    404: "Confira o caminho da rota na documentação interativa (/docs).",
    405: "Confira o método HTTP permitido para esta rota em /docs.",
    422: "Corrija os campos indicados em 'detalhes' e envie novamente.",
    500: "Erro inesperado no servidor. Informe o request_id ao responsável pela API.",
}


def codigo_para_status(status: int) -> str:
    return CODIGOS_HTTP.get(status, "ERRO_HTTP")


def montar_erro(codigo: str, mensagem: str, detalhes: Optional[list] = None, sugestao: Optional[str] = None,
                request_id: Optional[str] = None) -> dict:
    return {"codigo": codigo, "mensagem": mensagem, "detalhes": detalhes or [], "sugestao": sugestao,
            "request_id": request_id}


def traduzir_erro_validacao(erro: dict) -> str:
    """Traduz as mensagens do Pydantic v2 (em inglês) para português, sem expor o valor enviado."""
    tipo = str(erro.get("type", ""))
    ctx = erro.get("ctx") or {}
    if tipo == "missing":
        return "campo obrigatório ausente"
    if tipo == "json_invalid":
        return "JSON malformado"
    if tipo in ("string_too_short", "too_short"):
        return f"tamanho mínimo: {ctx.get('min_length', 1)}"
    if tipo in ("string_too_long", "too_long"):
        return f"tamanho máximo: {ctx.get('max_length', '?')}"
    if tipo == "string_pattern_mismatch":
        return f"formato inválido (esperado: {ctx.get('pattern', 'padrão definido na API')})"
    if tipo in ("greater_than", "greater_than_equal", "less_than", "less_than_equal"):
        rotulo = {"greater_than": "maior que", "greater_than_equal": "maior ou igual a",
                  "less_than": "menor que", "less_than_equal": "menor ou igual a"}[tipo]
        chave = {"greater_than": "gt", "greater_than_equal": "ge", "less_than": "lt", "less_than_equal": "le"}[tipo]
        return f"deve ser {rotulo} {ctx.get(chave, '?')}"
    if tipo in ("int_parsing", "float_parsing", "int_from_float", "float_type", "int_type"):
        return "deve ser um número"
    if tipo in ("string_type", "str_type"):
        return "deve ser texto"
    if tipo == "literal_error":
        return f"valor não permitido (opções: {ctx.get('expected', '?')})"
    if tipo == "value_error":
        return str(erro.get("msg", "valor inválido")).replace("Value error, ", "", 1)
    return str(erro.get("msg", "valor inválido"))


def detalhes_de_validacao(erros: list) -> list:
    detalhes = []
    for e in erros:
        loc = [str(p) for p in e.get("loc", []) if p not in ("body", "query", "path")]
        detalhes.append({"campo": ".".join(loc) or None, "problema": traduzir_erro_validacao(e)})
    return detalhes
