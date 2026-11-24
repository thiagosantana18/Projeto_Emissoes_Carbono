"""Request/Response Models (Pydantic v2) das rotas de IA online, previsão e qualidade."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Provedor = Literal["openai", "anthropic"]
Nivel = Literal["executivo", "detalhado"]
VersaoSumario = Literal["sumario_v1", "sumario_v2"]


# ------------------------------------------------------------------ requisições
class SumarizarTextoRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "texto": "O relatório de sustentabilidade 2025 informa que a empresa reduziu 12% das emissões de escopo 1 ...",
        "objetivo": "apoiar a decisão sobre metas de redução", "nivel": "executivo"}})
    texto: str = Field(..., min_length=1, max_length=500000, description="Texto ou relatório completo. O limite efetivo é configurável (padrão: 60.000 caracteres); textos longos usam map-reduce.")
    objetivo: Optional[str] = Field(None, max_length=300, description="Para que o leitor usará o resumo (orienta o foco).")
    nivel: Nivel = Field("executivo", description="'executivo' (3–5 frases) ou 'detalhado' (6–8 frases).")
    titulo: Optional[str] = Field(None, max_length=120, description="Nome do documento (aparece nas fontes).")
    provedor: Optional[Provedor] = Field(None, description="Provedor de IA; padrão: o configurado no servidor.")
    versao_prompt: Optional[VersaoSumario] = Field(None, description="'sumario_v2' (padrão, estruturado) ou 'sumario_v1' (texto livre, para comparação).")
    usar_cache: bool = Field(True, description="Reaproveita resposta idêntica anterior (sem nova cobrança).")


class SumarizarCorpusRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"tipo": "noticia", "tag": "carbono", "limite": 10, "nivel": "executivo"}})
    tipo: Optional[Literal["noticia", "ods_trecho"]] = None
    tag: Optional[str] = Field(None, max_length=40, description="Tag temática (carbono, emissoes, esg, clima...).")
    doc_ids: Optional[list[str]] = Field(None, max_length=100)
    limite: int = Field(15, ge=1, le=100, description="Máximo de documentos (os mais recentes); também limitado por ESG_IA_MAX_DOCS.")
    objetivo: Optional[str] = Field(None, max_length=300)
    nivel: Nivel = "executivo"
    provedor: Optional[Provedor] = None
    versao_prompt: Optional[VersaoSumario] = None
    usar_cache: bool = True


class PerguntarRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"pergunta": "Qual atividade mais contribui para as emissões?", "k": 5}})
    pergunta: str = Field(..., min_length=1, max_length=600)
    k: int = Field(5, ge=1, le=10, description="Quantos trechos recuperar para fundamentar a resposta.")
    incluir_emissoes: bool = Field(True, description="Inclui os dados agregados de emissões como fonte.")
    provedor: Optional[Provedor] = None
    usar_cache: bool = True


class InsightsRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"foco": "reduzir emissões da frota", "incluir_previsao": True}})
    foco: Optional[str] = Field(None, max_length=300)
    incluir_previsao: bool = True
    incluir_noticias: bool = Field(False, description="Inclui um resumo (gerado por IA) das notícias ESG; faz uma chamada extra ao provedor.")
    provedor: Optional[Provedor] = None
    usar_cache: bool = True


# ------------------------------------------------------------------ respostas comuns
class Fidelidade(BaseModel):
    ok: bool = Field(..., description="True se todos os números e citações do texto gerado conferem com as fontes.")
    numeros_verificados: int
    numeros_nao_encontrados: list[str] = Field(default_factory=list, description="Números do texto gerado que NÃO aparecem nas fontes.")
    citacoes_invalidas: list[str] = Field(default_factory=list, description="Ids citados que não existem nas fontes.")
    observacao: str


class FonteDocumento(BaseModel):
    id: str = Field(..., description="Id usado no texto gerado (ex.: d1, p2).")
    doc_id: Optional[str] = None
    titulo: Optional[str] = None
    fonte: Optional[str] = None
    url: Optional[str] = None
    data: Optional[str] = None


class RiscoOportunidade(BaseModel):
    tipo: str
    descricao: str
    fontes: list[str] = Field(default_factory=list)


class Recomendacao(BaseModel):
    acao: str
    justificativa: str = ""
    ods: Optional[str] = Field(None, description="'12' ou '13' quando aplicável.")


class SumarioEstruturado(BaseModel):
    resumo_executivo: str
    pontos_chave: list[str]
    riscos_e_oportunidades: list[RiscoOportunidade]
    recomendacoes: list[Recomendacao]
    lacunas: list[str]
    fontes_citadas: list[str]


class SumarioResponse(BaseModel):
    resumo: SumarioEstruturado
    fontes: list[FonteDocumento]
    metodo: Literal["direto", "map_reduce"]
    n_documentos: int
    n_lotes: int
    n_chamadas: int
    versao_prompt: str
    provedor: str
    modelo: str
    tokens_entrada: Optional[int] = None
    tokens_saida: Optional[int] = None
    latencia_ms: float
    fidelidade: Fidelidade
    avisos: list[str] = Field(default_factory=list)
    baseline_extrativo: list[str] = Field(default_factory=list, description="Resumo extrativo SEM IA, para comparação.")
    cache: bool


class TrechoRecuperado(BaseModel):
    id: str
    doc_id: Optional[str] = None
    titulo: Optional[str] = None
    fonte: Optional[str] = None
    url: Optional[str] = None
    score: float
    trecho: str


class RespostaPergunta(BaseModel):
    resposta: str
    confianca: Literal["alta", "media", "baixa"]
    fontes_citadas: list[str]
    lacunas: list[str]
    trechos: list[TrechoRecuperado]
    fidelidade: Optional[Fidelidade] = None
    chamou_llm: bool = Field(..., description="False quando nenhum trecho relevante foi encontrado (o LLM não é chamado).")
    n_chamadas: int
    provedor: Optional[str] = None
    modelo: Optional[str] = None
    tokens_entrada: Optional[int] = None
    tokens_saida: Optional[int] = None
    versao_prompt: str
    cache: bool


class Destaque(BaseModel):
    titulo: str
    detalhe: str


class RiscoGravidade(BaseModel):
    descricao: str
    gravidade: Literal["alta", "media", "baixa"]


class RecomendacaoInsight(BaseModel):
    acao: str
    justificativa: str
    impacto_esperado: str
    prioridade: Literal["alta", "media", "baixa"]
    ods: Optional[str] = None


class InsightsEstruturados(BaseModel):
    destaques: list[Destaque]
    riscos: list[RiscoGravidade]
    recomendacoes: list[RecomendacaoInsight]
    alertas_de_dados: list[str]
    fontes_citadas: list[str]


class FonteInsight(BaseModel):
    id: str
    titulo: str


class InsightsResponse(BaseModel):
    insights: InsightsEstruturados
    fontes: list[FonteInsight]
    versao_prompt: str
    n_chamadas: int
    provedor: str
    modelo: str
    tokens_entrada: Optional[int] = None
    tokens_saida: Optional[int] = None
    fidelidade: Fidelidade
    texto_contexto: str = Field(..., description="Os dados de emissões, em texto, exatamente como o modelo os recebeu.")
    avisos: list[str] = Field(default_factory=list)
    cache: bool


# ------------------------------------------------------------------ status / histórico
class ProvedorStatus(BaseModel):
    nome: str
    configurado: bool
    modelo: str
    url_personalizada: bool


class StatusIA(BaseModel):
    provedor_padrao: str
    provedores: list[ProvedorStatus]
    algum_configurado: bool
    cache_ativo: bool
    chamadas_ultima_hora: int
    limites: dict[str, float]
    versoes_prompt: dict[str, str]


class HistoricoIA(BaseModel):
    total: int
    itens: list[dict[str, Any]]


# ------------------------------------------------------------------ previsão e qualidade
class PontoHistorico(BaseModel):
    mes: str
    kgco2e: float


class MetodoPrevisao(BaseModel):
    metodo: str
    mape: float
    rmse: float
    n_previsoes: int


class PontoPrevisao(BaseModel):
    mes: str
    previsto: float
    min: float
    max: float


class SerieInfo(BaseModel):
    inicio: str
    fim: str
    n_meses: int


class PrevisaoResponse(BaseModel):
    serie: SerieInfo
    historico: list[PontoHistorico]
    metodos: list[MetodoPrevisao]
    melhor: str
    mape_melhor: float
    meta_mape: float
    atinge_meta: bool
    previsoes: list[PontoPrevisao]
    intervalo: str
    avisos: list[str]
