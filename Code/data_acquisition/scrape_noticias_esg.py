"""
Code/data_acquisition/scrape_noticias_esg.py

Coleta manchetes de notícias sobre ESG/pegada de carbono (BeautifulSoup).

O que foi aprimorado nesta fase (Etapa 3):
  * parsing separado da rede (extrair_manchetes_de_html) => testável offline;
  * filtros de relevância de URL (mesmo domínio, profundidade >= 2, sem páginas de autor/tag);
  * novas colunas: fonte, resumo (linha fina da listagem, truncada), tags temáticas;
  * deduplicação por URL e por título;
  * sessão HTTP com retentativas e logging.

Só metadados exibidos na página de listagem são salvos (título, link, data, linha
fina truncada) — nunca o corpo das matérias.

Saídas: Data/raw/noticias_esg.csv e Data/raw/noticias_esg.txt
Uso:    python Code/data_acquisition/scrape_noticias_esg.py
"""
from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Code/
sys.path.insert(0, str(Path(__file__).resolve().parent))            # esta pasta
from scraping_utils import configurar_log, criar_sessao, log, normalizar_data, pode_coletar, truncar  # noqa: E402
from esg_core import paths  # noqa: E402

URL_LISTAGEM = "https://exame.com/esg/"
COLUNAS = ["titulo", "data_publicacao", "url_materia", "data_coleta", "fonte", "resumo", "tags"]
CAMINHOS_IGNORADOS = ("/autor/", "/tag/", "/tags/", "/arquivo/", "/busca", "/newsletter", "/assine")

TAGS_TEMATICAS = {
    "carbono": ("carbono", "descarboniz"),
    "emissoes": ("emissões", "emissoes"),
    "esg": ("esg",),
    "clima": ("clima", "climát", "aquecimento"),
    "energia": ("energia", "biometano", "renovável", "renovavel", "elétric", "eletric"),
    "sustentabilidade": ("sustentab",),
    "neutralidade": ("neutralidade", "net zero"),
    "regulacao": ("cvm", "obrigat", "regulament", "lei "),
}


def classificar_tags(texto: str) -> list[str]:
    t = texto.lower()
    return [tag for tag, termos in TAGS_TEMATICAS.items() if any(x in t for x in termos)]


def _contexto(link):
    return link.find_parent(["article", "li", "div"]) or link.parent


def extrair_data_publicacao(link) -> str:
    ctx = _contexto(link)
    if ctx is None:
        return ""
    tag_time = ctx.find("time")
    if tag_time is not None:
        data = normalizar_data(tag_time.get("datetime", "") or tag_time.get_text(" ", strip=True))
        if data:
            return data
    return normalizar_data(ctx.get_text(" ", strip=True))


def extrair_resumo(link, titulo: str) -> str:
    ctx = _contexto(link)
    if ctx is None:
        return ""
    for p in ctx.find_all("p"):
        txt = " ".join(p.get_text(" ", strip=True).split())
        if 30 <= len(txt) <= 600 and txt != titulo and titulo not in txt:
            return truncar(txt, 280)
    return ""


def extrair_manchetes_de_html(html: str, url_base: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    dominio = urlparse(url_base).netloc.replace("www.", "")
    manchetes, urls_vistas, titulos_vistos = [], set(), set()

    for link in soup.find_all("a", href=True):
        url = urljoin(url_base, link["href"]).split("#")[0]
        p = urlparse(url)
        titulo = " ".join(link.get_text(" ", strip=True).split())
        if (len(titulo) <= 25 or p.scheme not in ("http", "https")
                or p.netloc.replace("www.", "") != dominio
                or len([s for s in p.path.split("/") if s]) < 2
                or any(x in p.path for x in CAMINHOS_IGNORADOS)
                or url in urls_vistas or titulo.lower() in titulos_vistos):
            continue
        urls_vistas.add(url)
        titulos_vistos.add(titulo.lower())
        resumo = extrair_resumo(link, titulo)
        manchetes.append({
            "titulo": titulo,
            "data_publicacao": extrair_data_publicacao(link),
            "url_materia": url,
            "fonte": dominio,
            "resumo": resumo,
            "tags": ";".join(classificar_tags(f"{titulo} {resumo}")),
        })
    return manchetes


def main() -> None:
    configurar_log()
    sessao = criar_sessao()
    if not pode_coletar(URL_LISTAGEM, sessao):
        log.error("robots.txt não permite coletar %s — abortando.", URL_LISTAGEM)
        return
    try:
        resp = sessao.get(URL_LISTAGEM, timeout=20)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.error("Falha ao baixar %s: %s", URL_LISTAGEM, exc)
        return
    time.sleep(2)

    manchetes = extrair_manchetes_de_html(resp.text, URL_LISTAGEM)
    if not manchetes:
        log.warning("Nenhuma manchete extraída — o HTML do site pode ter mudado (ou exige renderização "
                    "JavaScript; ver Docs/Project/Decision_Log.md, decisão sobre Selenium).")
        return

    coleta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saida = paths.raw_dir()
    saida.mkdir(parents=True, exist_ok=True)
    with open(saida / "noticias_esg.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        for m in manchetes:
            w.writerow({**m, "data_coleta": coleta})
    (saida / "noticias_esg.txt").write_text("\n".join(m["titulo"] for m in manchetes), encoding="utf-8")
    com_data = sum(1 for m in manchetes if m["data_publicacao"])
    log.info("OK: %d manchetes (%d com data de publicação) em %s", len(manchetes), com_data, saida)


if __name__ == "__main__":
    main()
