"""Rotas de emissões: consulta (GET), resumo (GET) e envio de novos registros (POST)."""
from typing import Literal, Optional

from fastapi import APIRouter, Body, Query, status

from esg_core import data_access as da

from ..schemas import REGEX_MES, EmissaoIn, EmissaoOut, InseridosOut, ListaEmissoes, ResumoEmissoes

router = APIRouter(prefix="/emissoes", tags=["Emissões"])


def _filtrar(unidade, setor, tipo_atividade, mes_inicio, mes_fim, origem):
    return da.filtrar_emissoes(da.carregar_emissoes(), unidade, setor, tipo_atividade, mes_inicio, mes_fim, origem)


@router.get(
    "",
    response_model=ListaEmissoes,
    summary="Consultar registros de atividade/emissão",
    description="Lista os registros da base (amostra do projeto + registros enviados via POST), "
                "com filtros opcionais e paginação. Os filtros textuais ignoram maiúsculas/minúsculas.",
)
def listar_emissoes(
    unidade: Optional[str] = Query(None, description="Unidade de negócio. Ex.: 'Filial - RJ'."),
    setor: Optional[str] = Query(None, description="Setor. Ex.: 'Logística'."),
    tipo_atividade: Optional[str] = Query(None, description="Atividade. Ex.: 'Diesel (frota)'."),
    mes_inicio: Optional[str] = Query(None, pattern=REGEX_MES, description="Mês inicial (AAAA-MM), inclusivo."),
    mes_fim: Optional[str] = Query(None, pattern=REGEX_MES, description="Mês final (AAAA-MM), inclusivo."),
    origem: Optional[Literal["base", "api"]] = Query(None, description="'base' ou 'api'."),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de itens retornados."),
    offset: int = Query(0, ge=0, description="Quantidade de itens a pular (paginação)."),
):
    df = _filtrar(unidade, setor, tipo_atividade, mes_inicio, mes_fim, origem)
    return {"total": len(df), "limit": limit, "offset": offset,
            "itens": da.df_para_registros(da.paginar(df, limit, offset))}


@router.get(
    "/resumo",
    response_model=ResumoEmissoes,
    summary="Resumo agregado das emissões",
    description="Retorna total de kgCO2e e agregações por unidade, por tipo de atividade e por mês, "
                "para o mesmo conjunto de filtros de `GET /emissoes`.",
)
def resumo(
    unidade: Optional[str] = Query(None),
    setor: Optional[str] = Query(None),
    tipo_atividade: Optional[str] = Query(None),
    mes_inicio: Optional[str] = Query(None, pattern=REGEX_MES),
    mes_fim: Optional[str] = Query(None, pattern=REGEX_MES),
    origem: Optional[Literal["base", "api"]] = Query(None),
):
    return da.resumo_emissoes(_filtrar(unidade, setor, tipo_atividade, mes_inicio, mes_fim, origem))


@router.post(
    "",
    response_model=EmissaoOut,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar um novo registro de atividade/emissão",
    description="Valida e grava um registro em `Data/raw/emissoes_enviadas_api.csv`. "
                "Se `emissao_kgco2e` for omitida, é calculada como `quantidade × fator_emissao_kgco2e`. "
                "Dados inválidos (mês fora do formato AAAA-MM, quantidade ≤ 0, emissão inconsistente...) "
                "retornam **422** com o detalhe do erro. O registro passa a aparecer em `GET /emissoes` "
                "(origem = 'api') e no dashboard.",
)
def criar_emissao(registro: EmissaoIn):
    dados = registro.model_dump()
    da.anexar_emissoes_enviadas([dados])
    return {**dados, "origem": "api"}


@router.post(
    "/lote",
    response_model=InseridosOut,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar vários registros de uma vez (até 500)",
    description="Mesma validação de `POST /emissoes`, aplicada a uma lista. "
                "A operação é atômica na validação: se qualquer item for inválido, nada é gravado.",
)
def criar_emissoes_em_lote(registros: list[EmissaoIn] = Body(..., min_length=1, max_length=500)):
    n = da.anexar_emissoes_enviadas([r.model_dump() for r in registros])
    return {"inseridos": n}
