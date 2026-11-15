"""Response/Request Models (Pydantic v2) das rotas de LLM local e do envelope de erro padrão."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Rotulo = Literal["positivo", "neutro", "negativo"]

EXEMPLO_REQUISICAO = {"texto": "Vivo reduz emissões em 91% e antecipa neutralidade climática para 2035", "tarefa": "sentimento"}


class ProcessarTextoRequest(BaseModel):
    """Texto a ser analisado pelo modelo local."""

    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra={"example": EXEMPLO_REQUISICAO})

    texto: str = Field(..., min_length=1, max_length=20000,
                       description="Texto em português (ou outro idioma suportado) a analisar. "
                                   "O limite efetivo por texto é configurável (padrão: 2000 caracteres).")
    tarefa: Literal["sentimento"] = Field(
        "sentimento", description="Tipo de análise. Nesta versão: classificação de sentimento. "
                                  "Resumo e Q&A estão planejados (ver Docs/Project/LLM_Readiness.md).")


class ProcessarLoteRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, json_schema_extra={
        "example": {"textos": ["Gerdau reduz pela metade pegada de carbono do aço",
                               "Aquecimento global empurra vegetação para o colapso, diz pesquisa"],
                    "tarefa": "sentimento"}})

    textos: list[str] = Field(..., min_length=1, max_length=1000,
                              description="Lista de textos (o máximo por requisição é configurável; padrão: 32).")
    tarefa: Literal["sentimento"] = "sentimento"


class Probabilidades(BaseModel):
    positivo: float = Field(..., ge=0, le=1)
    neutro: float = Field(..., ge=0, le=1)
    negativo: float = Field(..., ge=0, le=1)


class ResultadoSentimento(BaseModel):
    rotulo: Rotulo = Field(..., description="Classe com maior probabilidade.")
    confianca: float = Field(..., ge=0, le=1, description="Probabilidade da classe prevista.")
    probabilidades: Probabilidades


class InfoModelo(BaseModel):
    id: str = Field(..., description="Identificador do modelo no Hugging Face Hub.")
    dispositivo: str = Field(..., description="cpu ou cuda.")
    revisao: Optional[str] = Field(None, description="Commit do Hub, quando fixado.")


class MetadadosProcessamento(BaseModel):
    tempo_inferencia_ms: float
    n_caracteres: int
    n_tokens: Optional[int] = Field(None, description="Tokens do texto (None se o tokenizador não estiver acessível).")
    truncado: bool = Field(..., description="True se o texto excedeu o limite de tokens e foi truncado pelo modelo.")
    processado_em: str = Field(..., description="Data/hora ISO 8601 do processamento.")


class ProcessarTextoResponse(BaseModel):
    texto_original: str
    texto_processado: str = Field(..., description="Texto após normalização de espaços (o que o modelo recebeu).")
    tipo_analise: Literal["classificacao_sentimento"]
    resultado: ResultadoSentimento
    modelo: InfoModelo
    metadados: MetadadosProcessamento


class ItemLote(BaseModel):
    indice: int = Field(..., description="Posição do texto na lista enviada (começa em 0).")
    texto_processado: str
    resultado: ResultadoSentimento
    truncado: bool


class ProcessarLoteResponse(BaseModel):
    tipo_analise: Literal["classificacao_sentimento"]
    total: int
    resultados: list[ItemLote]
    modelo: InfoModelo
    tempo_total_ms: float
    processado_em: str


class LimitesModelo(BaseModel):
    max_caracteres: int
    max_tokens: int
    max_lote: int
    timeout_s: float
    max_pendentes: int


class StatusModelo(BaseModel):
    modelo_id: str
    revisao: Optional[str] = None
    carregado: bool = Field(..., description="True se o modelo já está na memória.")
    dependencias_instaladas: bool = Field(..., description="torch e transformers estão instalados.")
    dispositivo: str
    offline: bool = Field(..., description="True: a API nunca baixa o modelo durante uma requisição.")
    pasta_cache: str
    cache_presente: bool = Field(..., description="Os arquivos do modelo já estão na pasta de cache local.")
    tempo_carga_s: Optional[float] = None
    carregado_em: Optional[str] = None
    ultimo_erro: Optional[str] = None
    total_requisicoes: int
    total_erros: int
    limites: LimitesModelo


class DetalheErro(BaseModel):
    campo: Optional[str] = Field(None, description="Campo com problema (quando aplicável).")
    problema: str


class ErroResposta(BaseModel):
    """Envelope padrão de erro — o mesmo formato em TODAS as rotas e códigos de status."""

    codigo: str = Field(..., description="Código estável para tratamento programático (ex.: MODELO_INDISPONIVEL).")
    mensagem: str = Field(..., description="Explicação em português.")
    detalhes: list[DetalheErro] = Field(default_factory=list)
    sugestao: Optional[str] = Field(None, description="Como resolver.")
    request_id: Optional[str] = Field(None, description="Identificador da requisição (também no header X-Request-ID).")
