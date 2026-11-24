"""Erros da camada de IA online. Herdam de ErroLLM: o tratador da API já os converte em respostas HTTP padronizadas."""
from __future__ import annotations

from ..llm.errors import ErroLLM, TextoInvalidoError  # noqa: F401  (TextoInvalidoError reaproveitado: 422)


class IANaoConfiguradaError(ErroLLM):
    status_code, codigo = 503, "IA_NAO_CONFIGURADA"


class IACredencialError(ErroLLM):
    """O provedor rejeitou a chave (401/403): problema do servidor, não do cliente da API."""
    status_code, codigo = 503, "IA_CREDENCIAL_INVALIDA"


class IACotaError(ErroLLM):
    """Sem crédito/cota no provedor: tentar de novo não resolve."""
    status_code, codigo = 503, "IA_COTA_EXCEDIDA"


class IALimiteTaxaError(ErroLLM):
    """O provedor aplicou limite de taxa (429) mesmo após as retentativas."""
    status_code, codigo = 429, "IA_LIMITE_TAXA"


class IAUsoExcedidoError(ErroLLM):
    """Limite LOCAL de chamadas por hora (proteção contra custo inesperado)."""
    status_code, codigo = 429, "IA_LIMITE_LOCAL"


class IAProvedorError(ErroLLM):
    """Provedor fora do ar, erro 5xx, rede ou requisição recusada."""
    status_code, codigo = 502, "IA_PROVEDOR_INDISPONIVEL"


class IATempoLimiteError(ErroLLM):
    status_code, codigo = 504, "IA_TEMPO_LIMITE"


class IARespostaInvalidaError(ErroLLM):
    """O modelo respondeu, mas a saída não é utilizável (JSON inválido, truncada, vazia, recusa)."""
    status_code, codigo = 502, "IA_RESPOSTA_INVALIDA"


class DadosIndisponiveisError(ErroLLM):
    status_code, codigo = 404, "DADOS_INDISPONIVEIS"
