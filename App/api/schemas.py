"""Modelos Pydantic (v2) — contratos de entrada e saída da API."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from esg_core.validation import calcular_emissao, emissao_consistente

REGEX_MES = r"^\d{4}-(0[1-9]|1[0-2])$"

EXEMPLO_EMISSAO = {
    "mes_referencia": "2026-10",
    "unidade": "Matriz - SP",
    "setor": "Administrativo",
    "tipo_atividade": "Eletricidade (rede)",
    "quantidade": 8500.0,
    "unidade_medida": "kWh",
    "fator_emissao_kgco2e": 0.0817,
    "emissao_kgco2e": 694.45,
    "fonte_fator": "Climatiq API",
}


class EmissaoIn(BaseModel):
    """Registro de atividade/emissão enviado pelo cliente (POST)."""

    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra={"example": EXEMPLO_EMISSAO})

    mes_referencia: str = Field(..., pattern=REGEX_MES, description="Mês de referência no formato AAAA-MM.")
    unidade: str = Field(..., min_length=1, max_length=80, description="Unidade de negócio (ex.: 'Filial - RJ').")
    setor: str = Field(..., min_length=1, max_length=80, description="Setor (ex.: 'Logística').")
    tipo_atividade: str = Field(..., min_length=1, max_length=80, description="Atividade emissora (ex.: 'Diesel (frota)').")
    quantidade: float = Field(..., gt=0, description="Quantidade consumida, na unidade de medida informada.")
    unidade_medida: str = Field(..., min_length=1, max_length=20, description="kWh, litro, m3, km...")
    fator_emissao_kgco2e: float = Field(..., ge=0, description="Fator de emissão em kgCO2e por unidade de medida.")
    emissao_kgco2e: Optional[float] = Field(
        None, ge=0,
        description="Emissão em kgCO2e. Se omitida, é calculada (quantidade × fator). "
                    "Se informada, deve ser consistente com quantidade × fator (tolerância de 1 %).",
    )
    fonte_fator: str = Field(..., min_length=1, max_length=80, description="Origem do fator (ex.: 'EPA', 'DEFRA', 'Climatiq API').")

    @model_validator(mode="after")
    def _validar_emissao(self):
        if self.emissao_kgco2e is None:
            self.emissao_kgco2e = calcular_emissao(self.quantidade, self.fator_emissao_kgco2e)
        elif not emissao_consistente(self.quantidade, self.fator_emissao_kgco2e, self.emissao_kgco2e):
            raise ValueError("emissao_kgco2e diverge de quantidade × fator_emissao_kgco2e (tolerância de 1 %).")
        return self


class EmissaoOut(BaseModel):
    mes_referencia: str
    unidade: str
    setor: str
    tipo_atividade: str
    quantidade: float
    unidade_medida: str
    fator_emissao_kgco2e: float
    emissao_kgco2e: float
    fonte_fator: str
    origem: str = Field(..., description="'base' (amostra do projeto) ou 'api' (enviado via POST).")


class ListaEmissoes(BaseModel):
    total: int = Field(..., description="Total de registros que atendem aos filtros (antes da paginação).")
    limit: int
    offset: int
    itens: list[EmissaoOut]


class ResumoEmissoes(BaseModel):
    n_registros: int
    total_kgco2e: float
    periodo_inicio: Optional[str] = None
    periodo_fim: Optional[str] = None
    por_unidade: dict[str, float]
    por_tipo_atividade: dict[str, float]
    por_mes: dict[str, float]


class InseridosOut(BaseModel):
    inseridos: int


class Noticia(BaseModel):
    titulo: str
    data_publicacao: Optional[str] = None
    url_materia: Optional[str] = None
    data_coleta: Optional[str] = None
    fonte: Optional[str] = None
    resumo: Optional[str] = None
    tags: Optional[str] = Field(None, description="Tags temáticas separadas por ';'.")


class ListaNoticias(BaseModel):
    total: int
    limit: int
    offset: int
    itens: list[Noticia]


class TrechoODS(BaseModel):
    ods: str
    titulo_pagina: Optional[str] = None
    secao: Optional[str] = None
    trecho: str
    url_fonte: Optional[str] = None
    data_coleta: Optional[str] = None


class ListaODS(BaseModel):
    total: int
    limit: int
    offset: int
    itens: list[TrechoODS]


class DocumentoCorpus(BaseModel):
    doc_id: str
    tipo: str
    fonte: Optional[str] = None
    url: Optional[str] = None
    titulo: Optional[str] = None
    texto: str
    data_publicacao: Optional[str] = None
    data_coleta: Optional[str] = None
    idioma: str
    n_palavras: int
    secao: Optional[str] = None
    tags: list[str]
    usos_previstos: list[str]


class ListaCorpus(BaseModel):
    total: int
    limit: int
    offset: int
    itens: list[DocumentoCorpus]


class HealthOut(BaseModel):
    status: str
    versao: str
    arquivos: dict[str, bool]
    llm: Optional[dict[str, bool]] = None
