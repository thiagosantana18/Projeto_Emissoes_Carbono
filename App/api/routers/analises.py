"""Rotas analíticas sem IA online: previsão de emissões (baseline estatístico) e qualidade dos dados."""
from typing import Any

from fastapi import APIRouter, Query

from esg_core import data_access as da
from esg_core.ia.errors import DadosIndisponiveisError
from esg_core.previsao import prever_emissoes
from esg_core.qualidade import checks, relatorio_qualidade

from ..schemas_ia import PrevisaoResponse
from ..schemas_llm import ErroResposta

router = APIRouter(tags=["Análises"])


@router.get("/previsao/emissoes", response_model=PrevisaoResponse, responses={404: {"model": ErroResposta}},
            summary="Previsão das emissões mensais (com backtest)",
            description="Compara três métodos (ingênuo, sazonal ingênuo, tendência + sazonalidade) por backtest e prevê os próximos meses com o melhor. "
                        "A meta do projeto é MAPE < 15%. Sobre a amostra sintética, o resultado demonstra o método, não a capacidade de prever uma empresa real.")
def previsao_emissoes(horizonte: int = Query(6, ge=1, le=12, description="Meses a prever.")):
    df = da.carregar_emissoes()
    if df.empty:
        raise DadosIndisponiveisError("Não há dados de emissões.", sugestao="Gere a amostra: python Code/data_acquisition/generate_sample_emissions.py")
    try:
        r = prever_emissoes(df, horizonte)
    except ValueError as exc:
        raise DadosIndisponiveisError(str(exc), sugestao="Envie mais meses de dados (POST /emissoes) ou gere a amostra completa.") from exc
    r["avisos"] = [a for a in r["avisos"] if a]
    return r


@router.get("/qualidade", response_model=dict[str, Any], summary="Relatório de qualidade dos dados",
            description="Verificações de qualidade de emissões, notícias, ODS, corpus e sentimento, calculadas sobre os arquivos atuais. "
                        "`resumo_verificacoes` lista cada verificação com o resultado.")
def qualidade():
    rel = relatorio_qualidade()
    rel["resumo_verificacoes"] = [{"verificacao": n, "ok": ok, "detalhe": d} for n, ok, d in checks(rel)]
    return rel
