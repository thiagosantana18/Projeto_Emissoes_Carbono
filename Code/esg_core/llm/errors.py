"""
Exceções do serviço de LLM local.

Cada exceção carrega o status HTTP que a API deve devolver, um código estável (para o cliente
tratar programaticamente), uma mensagem em português e, quando possível, uma sugestão de correção.
Ficam fora do FastAPI de propósito: o serviço funciona (e é testado) sem nenhum framework web.
"""
from __future__ import annotations

from typing import Optional


class ErroLLM(Exception):
    status_code: int = 500
    codigo: str = "ERRO_LLM"

    def __init__(self, mensagem: str, *, detalhes: Optional[list] = None,
                 sugestao: Optional[str] = None, retry_after: Optional[int] = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = detalhes
        self.sugestao = sugestao
        self.retry_after = retry_after


class TextoInvalidoError(ErroLLM):
    """Entrada inválida (vazia, sem letras, longa demais...)."""
    status_code = 422
    codigo = "TEXTO_INVALIDO"


class ModeloIndisponivelError(ErroLLM):
    """Dependências ausentes, modelo não baixado ou falha ao carregar."""
    status_code = 503
    codigo = "MODELO_INDISPONIVEL"


class ModeloOcupadoError(ErroLLM):
    """Fila de processamento cheia (proteção contra sobrecarga em máquina modesta)."""
    status_code = 429
    codigo = "MODELO_OCUPADO"


class TempoLimiteError(ErroLLM):
    """A inferência passou do tempo máximo configurado."""
    status_code = 504
    codigo = "TEMPO_LIMITE_EXCEDIDO"


class FalhaInferenciaError(ErroLLM):
    """O modelo falhou ou devolveu uma saída que não passou na validação."""
    status_code = 500
    codigo = "FALHA_INFERENCIA"
