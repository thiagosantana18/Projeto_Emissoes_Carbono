"""Rotas de processamento de texto com o modelo de linguagem LOCAL (Hugging Face)."""
from fastapi import APIRouter, Depends, Query

from esg_core.llm.sentimento import TIPO_ANALISE, ServicoSentimento, obter_servico

from ..schemas_llm import (ErroResposta, ProcessarLoteRequest, ProcessarLoteResponse, ProcessarTextoRequest,
                           ProcessarTextoResponse, StatusModelo)

router = APIRouter(tags=["LLM local"])


def get_servico() -> ServicoSentimento:
    """Dependência: devolve o serviço compartilhado (substituível nos testes via dependency_overrides)."""
    return obter_servico()


ERROS_PROCESSAMENTO = {
    422: {"model": ErroResposta, "description": "Texto inválido (vazio, sem letras, longo demais) ou corpo malformado."},
    429: {"model": ErroResposta, "description": "Modelo ocupado: fila cheia. Veja o header Retry-After."},
    500: {"model": ErroResposta, "description": "Falha na inferência ou saída do modelo fora do contrato."},
    503: {"model": ErroResposta, "description": "Modelo indisponível (dependências ausentes, não baixado ou falha ao carregar)."},
    504: {"model": ErroResposta, "description": "A análise excedeu o tempo limite."},
}


@router.post(
    "/processar_texto",
    response_model=ProcessarTextoResponse,
    responses=ERROS_PROCESSAMENTO,
    summary="Analisar o sentimento de um texto (modelo local)",
    description="Recebe um texto e o classifica como **positivo**, **neutro** ou **negativo** usando um modelo do "
                "Hugging Face executado **localmente** (sem nuvem). Devolve o texto processado, o tipo de análise, "
                "o rótulo com a probabilidade de cada classe, o modelo usado e metadados (tempo, tokens, truncamento). "
                "Na primeira chamada o modelo é carregado na memória (alguns segundos); use `POST /modelo/carregar` "
                "para aquecê-lo antes.",
)
def processar_texto(requisicao: ProcessarTextoRequest, servico: ServicoSentimento = Depends(get_servico)):
    return servico.analisar(requisicao.texto)


@router.post(
    "/processar_texto/lote",
    response_model=ProcessarLoteResponse,
    responses=ERROS_PROCESSAMENTO,
    summary="Analisar o sentimento de vários textos de uma vez",
    description="Mesma análise de `POST /processar_texto`, para uma lista de textos (padrão: até 32). "
                "Se qualquer texto for inválido, a requisição inteira é rejeitada com 422 e o campo `detalhes` "
                "indica qual (`textos[i]`). A ordem do resultado é a mesma da entrada.",
)
def processar_lote(requisicao: ProcessarLoteRequest, servico: ServicoSentimento = Depends(get_servico)):
    itens = servico.analisar_lote(requisicao.textos)
    return {
        "tipo_analise": TIPO_ANALISE,
        "total": len(itens),
        "resultados": [{"indice": i, "texto_processado": r["texto_processado"], "resultado": r["resultado"],
                        "truncado": r["metadados"]["truncado"]} for i, r in enumerate(itens)],
        "modelo": itens[0]["modelo"],
        "tempo_total_ms": round(sum(r["metadados"]["tempo_inferencia_ms"] for r in itens), 2),
        "processado_em": itens[0]["metadados"]["processado_em"],
    }


@router.get(
    "/modelo/status",
    response_model=StatusModelo,
    summary="Estado do modelo local",
    description="Informa se o modelo está carregado, se as dependências e o cache existem, o último erro, "
                "contadores e limites. Use para diagnosticar um 503.",
)
def status_modelo(servico: ServicoSentimento = Depends(get_servico)):
    return servico.status()


@router.post(
    "/modelo/carregar",
    response_model=StatusModelo,
    responses={503: ERROS_PROCESSAMENTO[503]},
    summary="Carregar (aquecer) o modelo na memória",
    description="Carrega o modelo antes da primeira análise, para que ela não pague o tempo de carga. "
                "`forcar=true` ignora a espera após uma falha anterior e recarrega.",
)
def carregar_modelo(forcar: bool = Query(False, description="Recarrega mesmo se já estiver carregado ou em espera após falha."),
                    servico: ServicoSentimento = Depends(get_servico)):
    servico.carregar(forcar=forcar)
    return servico.status()
