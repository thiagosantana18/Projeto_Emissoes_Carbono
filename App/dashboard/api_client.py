"""
Cliente HTTP da API do projeto (sem dependência de Streamlit, para ser testável).

Dois tipos de falha, tratados de forma diferente pelas páginas:
  * ApiIndisponivel — não foi possível falar com a API (desligada, URL errada, tempo esgotado);
  * ApiErro         — a API respondeu com erro; carrega o envelope padrão (codigo, mensagem, sugestao...).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import requests


class ApiIndisponivel(Exception):
    pass


class ApiErro(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str, sugestao: Optional[str] = None,
                 detalhes: Optional[list] = None, retry_after: Optional[str] = None):
        super().__init__(f"[{status} {codigo}] {mensagem}")
        self.status, self.codigo, self.mensagem = status, codigo, mensagem
        self.sugestao, self.detalhes, self.retry_after = sugestao, detalhes or [], retry_after


def erro_de_resposta(resposta) -> ApiErro:
    """Converte uma resposta HTTP de erro em ApiErro, mesmo que o corpo não siga o envelope."""
    try:
        corpo = resposta.json()
    except ValueError:
        corpo = {}
    if isinstance(corpo, dict) and "codigo" in corpo:
        return ApiErro(resposta.status_code, corpo["codigo"], corpo.get("mensagem", ""), corpo.get("sugestao"),
                       corpo.get("detalhes"), resposta.headers.get("Retry-After"))
    texto = (getattr(resposta, "text", "") or "")[:200]
    return ApiErro(resposta.status_code, "ERRO_HTTP", texto or "Resposta de erro sem corpo.")


def _requisitar(base: str, metodo: str, caminho: str, timeout: float = 10, **kwargs):
    url = base.rstrip("/") + caminho
    try:
        resposta = requests.request(metodo, url, timeout=timeout, **kwargs)
    except requests.exceptions.Timeout as exc:
        raise ApiIndisponivel(f"A API não respondeu em {timeout:g} s ({url}).") from exc
    except requests.exceptions.RequestException as exc:
        raise ApiIndisponivel(f"Não foi possível conectar à API em {base}. Ela está no ar? ({type(exc).__name__})") from exc
    if not resposta.ok:
        raise erro_de_resposta(resposta)
    return resposta.json()


def health(base: str) -> dict:
    return _requisitar(base, "GET", "/health", timeout=5)


def obter_emissoes(base: str, **filtros) -> pd.DataFrame:
    """Busca TODOS os registros que atendem aos filtros, paginando de 1000 em 1000."""
    itens, offset = [], 0
    while True:
        params = {k: v for k, v in filtros.items() if v not in (None, "")}
        j = _requisitar(base, "GET", "/emissoes", params={**params, "limit": 1000, "offset": offset})
        itens += j["itens"]
        offset += len(j["itens"])
        if not j["itens"] or offset >= j["total"]:
            break
    return pd.DataFrame(itens)


def obter_noticias(base: str, limite: int = 500) -> pd.DataFrame:
    return pd.DataFrame(_requisitar(base, "GET", "/noticias", params={"limit": limite})["itens"])


def status_modelo(base: str) -> dict:
    return _requisitar(base, "GET", "/modelo/status", timeout=8)


def carregar_modelo(base: str, forcar: bool = False) -> dict:
    return _requisitar(base, "POST", "/modelo/carregar", timeout=180, params={"forcar": str(forcar).lower()})


def processar_texto(base: str, texto: str) -> dict:
    return _requisitar(base, "POST", "/processar_texto", timeout=60, json={"texto": texto})


def processar_lote(base: str, textos: list, tamanho_lote: int = 32) -> list:
    """Envia em partes de `tamanho_lote` (limite da API) e devolve os resultados na ordem original."""
    resultados = []
    for i in range(0, len(textos), tamanho_lote):
        j = _requisitar(base, "POST", "/processar_texto/lote", timeout=180, json={"textos": textos[i:i + tamanho_lote]})
        resultados += j["resultados"]
    return resultados


# ---------------------------------------------------------------- IA online, previsão e qualidade
def status_ia(base: str) -> dict:
    return _requisitar(base, "GET", "/ia/status", timeout=8)


def historico_ia(base: str, limite: int = 50) -> list:
    return _requisitar(base, "GET", "/ia/historico", timeout=10, params={"limite": limite})["itens"]


def sumarizar_texto(base: str, texto: str, **kw) -> dict:
    return _requisitar(base, "POST", "/sumarizar", timeout=300, json={"texto": texto, **{k: v for k, v in kw.items() if v is not None}})


def sumarizar_corpus(base: str, **kw) -> dict:
    return _requisitar(base, "POST", "/sumarizar/corpus", timeout=300, json={k: v for k, v in kw.items() if v not in (None, "")})


def perguntar(base: str, pergunta: str, **kw) -> dict:
    return _requisitar(base, "POST", "/perguntar", timeout=120, json={"pergunta": pergunta, **{k: v for k, v in kw.items() if v is not None}})


def insights_emissoes(base: str, **kw) -> dict:
    return _requisitar(base, "POST", "/insights/emissoes", timeout=300, json={k: v for k, v in kw.items() if v not in (None, "")})


def previsao_emissoes(base: str, horizonte: int = 6) -> dict:
    return _requisitar(base, "GET", "/previsao/emissoes", timeout=15, params={"horizonte": horizonte})


def qualidade(base: str) -> dict:
    return _requisitar(base, "GET", "/qualidade", timeout=15)
