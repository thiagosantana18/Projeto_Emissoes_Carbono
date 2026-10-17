"""
Code/data_acquisition/scrape_ods_ecycle.py

Coleta trechos das páginas dos ODS 12 e 13 (eCycle) com BeautifulSoup.

Aprimoramentos da Etapa 3: parsing separado da rede (testável offline); coluna `secao`
(último <h2>/<h3> antes do parágrafo — contexto útil para RAG/Q&A); trechos truncados
em 600 caracteres (cautela com direitos autorais); sessão com retentativas.

Saídas: Data/raw/ods_conteudo.csv e Data/raw/ods_conteudo.txt
Uso:    python Code/data_acquisition/scrape_ods_ecycle.py
"""
from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scraping_utils import configurar_log, criar_sessao, log, pode_coletar, truncar  # noqa: E402
from esg_core import paths  # noqa: E402

FONTES = [
    {"ods": "ODS 12", "url": "https://www.ecycle.com.br/ods-12/"},
    {"ods": "ODS 13", "url": "https://www.ecycle.com.br/ods-13/"},
]
COLUNAS = ["ods", "titulo_pagina", "secao", "trecho", "url_fonte", "data_coleta"]
MAX_CHARS_TRECHO = 600
MIN_CHARS_PARAGRAFO = 40


def extrair_trechos_de_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    titulo = h1.get_text(" ", strip=True) if h1 else ""
    corpo = soup.find("article") or soup
    secao, itens = "", []
    for el in corpo.find_all(["h2", "h3", "p"]):
        texto = " ".join(el.get_text(" ", strip=True).split())
        if el.name in ("h2", "h3"):
            secao = texto
        elif len(texto) >= MIN_CHARS_PARAGRAFO:
            itens.append({"secao": secao, "trecho": truncar(texto, MAX_CHARS_TRECHO)})
    return {"titulo": titulo, "itens": itens}


def main() -> None:
    configurar_log()
    sessao = criar_sessao()
    linhas = []
    for fonte in FONTES:
        url = fonte["url"]
        if not pode_coletar(url, sessao):
            log.warning("Pulando %s (robots.txt)", url)
            continue
        try:
            resp = sessao.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            log.error("Falha ao coletar %s: %s", url, exc)
            continue
        dados = extrair_trechos_de_html(resp.text)
        coleta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for it in dados["itens"]:
            linhas.append({"ods": fonte["ods"], "titulo_pagina": dados["titulo"], "secao": it["secao"],
                           "trecho": it["trecho"], "url_fonte": url, "data_coleta": coleta})
        time.sleep(2)

    if not linhas:
        log.warning("Nada coletado (robots.txt bloqueou, erro de rede ou HTML mudou).")
        return
    saida = paths.raw_dir()
    saida.mkdir(parents=True, exist_ok=True)
    with open(saida / "ods_conteudo.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    (saida / "ods_conteudo.txt").write_text("\n".join(l["trecho"] for l in linhas), encoding="utf-8")
    log.info("OK: %d trechos em %s", len(linhas), saida)


if __name__ == "__main__":
    main()
