"""Rotas de IA online (OpenAI/Anthropic): sumarização, perguntas e respostas e insights. A chave fica SÓ no servidor."""
from fastapi import APIRouter, Depends, Query

from esg_core.ia.servico import ServicoIA, obter_servico_ia

from ..schemas_ia import (HistoricoIA, InsightsRequest, InsightsResponse, PerguntarRequest, RespostaPergunta, StatusIA,
                          SumarioResponse, SumarizarCorpusRequest, SumarizarTextoRequest)
from ..schemas_llm import ErroResposta

router = APIRouter(tags=["IA online"])


def get_servico_ia() -> ServicoIA:
    """Dependência (substituível nos testes via dependency_overrides)."""
    return obter_servico_ia()


ERROS_IA = {
    404: {"model": ErroResposta, "description": "Dados necessários ainda não existem (corpus, emissões) ou filtros sem resultado."},
    422: {"model": ErroResposta, "description": "Entrada inválida (texto curto/longo demais, versão de prompt ou provedor desconhecidos)."},
    429: {"model": ErroResposta, "description": "Limite local de chamadas/hora ou limite de taxa do provedor. Veja Retry-After."},
    502: {"model": ErroResposta, "description": "Provedor de IA fora do ar, ou resposta do modelo inutilizável (JSON inválido/truncada/vazia)."},
    503: {"model": ErroResposta, "description": "IA não configurada (sem chave), credencial inválida ou sem crédito no provedor."},
    504: {"model": ErroResposta, "description": "O provedor não respondeu dentro do tempo limite."},
}


@router.get("/ia/status", response_model=StatusIA, summary="Estado da IA online",
            description="Provedores configurados (a chave nunca é exibida), modelos, limites, uso na última hora e versões dos prompts.")
def status_ia(servico: ServicoIA = Depends(get_servico_ia)):
    return servico.status()


@router.get("/ia/historico", response_model=HistoricoIA, summary="Histórico de auditoria das gerações com IA",
            description="Registro de cada geração: tipo, provedor, modelo, versão do prompt, tokens, fidelidade e um trecho da saída. "
                        "A entrada original NÃO é gravada (só tamanho).")
def historico_ia(limite: int = Query(50, ge=1, le=500), servico: ServicoIA = Depends(get_servico_ia)):
    itens = servico.historico(limite)
    return {"total": len(itens), "itens": itens}


@router.post("/sumarizar", response_model=SumarioResponse, responses=ERROS_IA, summary="Resumir um texto ou relatório com IA",
             description="Recebe um texto (relatório de sustentabilidade, artigo...) e devolve um resumo **estruturado**: resumo executivo, pontos-chave, "
                         "riscos e oportunidades, recomendações (com ODS), lacunas e fontes. Textos longos são divididos em trechos e resumidos por "
                         "map-reduce. Todo número e citação do resumo é **verificado automaticamente** contra o texto original (`fidelidade`). "
                         "Também devolve um resumo extrativo sem IA para comparação. ⚠️ O texto é enviado ao provedor de IA escolhido.")
def sumarizar_texto(req: SumarizarTextoRequest, servico: ServicoIA = Depends(get_servico_ia)):
    return servico.sumarizar_texto(req.texto, req.objetivo, req.nivel, req.titulo, req.provedor, req.versao_prompt, req.usar_cache)


@router.post("/sumarizar/corpus", response_model=SumarioResponse, responses=ERROS_IA, summary="Resumir documentos do corpus coletado",
             description="Resume os documentos (notícias ESG e trechos de ODS coletados por scraping) que atendem aos filtros, citando cada fonte pelo id "
                         "e devolvendo a tabela de fontes com título e URL. Volumes grandes usam map-reduce.")
def sumarizar_corpus(req: SumarizarCorpusRequest, servico: ServicoIA = Depends(get_servico_ia)):
    return servico.sumarizar_corpus(req.tipo, req.tag, req.doc_ids, req.limite, req.objetivo, req.nivel, req.provedor, req.versao_prompt, req.usar_cache)


@router.post("/perguntar", response_model=RespostaPergunta, responses=ERROS_IA, summary="Perguntar aos dados (RAG)",
             description="Recupera os trechos mais relevantes do corpus (e dos dados de emissões) e pede ao modelo que responda **apenas** com eles, citando as fontes. "
                         "Se nenhum trecho for relevante, a resposta é 'não permitem responder' e o provedor **não é chamado**.")
def perguntar(req: PerguntarRequest, servico: ServicoIA = Depends(get_servico_ia)):
    return servico.perguntar(req.pergunta, req.k, req.provedor, req.incluir_emissoes, req.usar_cache)


@router.post("/insights/emissoes", response_model=InsightsResponse, responses=ERROS_IA, summary="Gerar insights e recomendações sobre as emissões",
             description="Combina os dados agregados de emissões, a previsão (opcional), o sentimento das notícias (se já calculado) e, se pedido, um resumo das notícias, "
                         "e pede destaques, riscos e recomendações priorizadas ligadas aos ODS 12 e 13. Números do texto são verificados contra os dados.")
def insights_emissoes(req: InsightsRequest, servico: ServicoIA = Depends(get_servico_ia)):
    return servico.insights_emissoes(req.foco, req.incluir_previsao, req.incluir_noticias, req.provedor, req.usar_cache)
