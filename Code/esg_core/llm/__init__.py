"""LLM local (Hugging Face) — serviço de sentimento, configuração, erros e métricas de avaliação."""
from .errors import (ErroLLM, FalhaInferenciaError, ModeloIndisponivelError, ModeloOcupadoError,  # noqa: F401
                     TempoLimiteError, TextoInvalidoError)
from .sentimento import ServicoSentimento, definir_servico, obter_servico  # noqa: F401
