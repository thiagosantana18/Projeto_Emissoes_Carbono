"""
Utilitários compartilhados pelos scrapers (BeautifulSoup + requests).

Princípios: (1) respeitar o robots.txt SEMPRE antes de coletar; (2) identificar-se
com User-Agent próprio; (3) falhar de forma segura (na dúvida, não coletar);
(4) separar a parte de rede da parte de parsing (esta última é testável offline).
"""
from __future__ import annotations

import logging
import re
import urllib.robotparser
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "ProjetoESG-CarbonoBot/1.0 (+uso educacional; contato: equipe-projeto@exemplo.com)"
log = logging.getLogger("scraping")


def configurar_log() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")


def criar_sessao() -> requests.Session:
    """Sessão com User-Agent identificado e retentativas com backoff para erros transitórios."""
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


def avaliar_robots(texto: Optional[str], status: Optional[int], url: str, user_agent: str = USER_AGENT) -> bool:
    """
    Decide, a partir da resposta do robots.txt, se `url` pode ser coletada.
      * sem resposta (erro de rede)  -> False (conservador)
      * 200                          -> aplica as regras do arquivo
      * 404/410 (não existe)         -> True  (sem restrições declaradas)
      * qualquer outro status        -> False (401/403/5xx: tratamos como bloqueado)
    """
    if status is None:
        return False
    if status in (404, 410):
        return True
    if 200 <= status < 300 and texto is not None:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(texto.splitlines())
        return rp.can_fetch(user_agent, url)
    return False


def pode_coletar(url: str, sessao: Optional[requests.Session] = None) -> bool:
    p = urlparse(url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    sessao = sessao or criar_sessao()
    try:
        resp = sessao.get(robots_url, timeout=15)
        status, texto = resp.status_code, resp.text
    except requests.RequestException as exc:
        log.warning("Não foi possível ler %s (%s)", robots_url, exc)
        status, texto = None, None
    permitido = avaliar_robots(texto, status, url)
    log.info("robots.txt %s -> %s (HTTP %s)", url, "PERMITIDO" if permitido else "BLOQUEADO", status)
    return permitido


def normalizar_data(valor: str) -> str:
    """Extrai AAAA-MM-DD de ISO ou DD/MM/AAAA; devolve '' se não reconhecer."""
    if not valor:
        return ""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", valor)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", valor)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return ""


def truncar(texto: str, limite: int) -> str:
    """Trunca em limite de caracteres, preferindo fim de palavra (cautela com direitos autorais)."""
    texto = " ".join(texto.split())
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(",;:") + "…"
