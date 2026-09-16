"""
Code/data_acquisition/scrape_noticias_esg.py

Objetivo:
    Coletar manchetes/títulos de notícias recentes sobre ESG e pegada de
    carbono a partir de um portal de notícias, para alimentar a tabela de
    "notícias" e a nuvem de palavras da aplicação.

Boas práticas aplicadas:
    - Verificação do robots.txt via urllib.robotparser ANTES de acessar a
      página de listagem de notícias.
    - User-Agent identificado.
    - Delay entre requisições.
    - Coleta apenas de metadados públicos já exibidos na página de listagem
      (título, link, data), sem reproduzir o corpo integral das matérias —
      preservando os direitos autorais do veículo de imprensa.

Saídas:
    Data/raw/noticias_esg.csv  -> título, data, autor, url da matéria
    Data/raw/noticias_esg.txt  -> corpus de títulos (para nuvem de palavras)

Como executar (fora do sandbox, com acesso à internet):
    python Code/data_acquisition/scrape_noticias_esg.py
"""

import csv
import re
import time
import urllib.robotparser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "ProjetoESG-CarbonoBot/1.0 (+uso educacional; contato: equipe-projeto@exemplo.com)"
HEADERS = {"User-Agent": USER_AGENT}

# Página de listagem de notícias ESG (fonte configurável)
URL_LISTAGEM = "https://exame.com/esg/"

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "Data" / "raw"
CSV_PATH = OUTPUT_DIR / "noticias_esg.csv"
TXT_PATH = OUTPUT_DIR / "noticias_esg.txt"


def pode_coletar(url: str) -> bool:
    """Verifica permissão de coleta no robots.txt do domínio."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:
        print(f"[AVISO] Não foi possível ler {robots_url}: {exc}")
        return False

    permitido = rp.can_fetch(USER_AGENT, url)
    print(f"[robots.txt] {url} -> {'PERMITIDO' if permitido else 'BLOQUEADO'}")
    return permitido


def extrair_manchetes(url: str) -> list[dict]:
    """
    Faz o parsing da página de listagem e extrai título + link de cada
    manchete encontrada. A heurística de seleção (tag <a> com texto longo o
    suficiente para ser um título de matéria) é propositalmente simples e
    pode precisar de ajuste conforme mudanças no HTML do site-alvo.
    """
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    manchetes = []
    vistos = set()

    for link in soup.find_all("a", href=True):
        texto = link.get_text(strip=True)
        href = link["href"]

        # Heurística: título de matéria costuma ter mais de 25 caracteres
        # e o link aponta para uma URL absoluta do próprio domínio.
        if len(texto) > 25 and href.startswith("http") and texto not in vistos:
            manchetes.append({"titulo": texto, "url_materia": href})
            vistos.add(texto)

    return manchetes


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not pode_coletar(URL_LISTAGEM):
        print(f"[PARANDO] {URL_LISTAGEM} não permite coleta segundo o robots.txt.")
        return

    try:
        manchetes = extrair_manchetes(URL_LISTAGEM)
    except requests.RequestException as exc:
        print(f"[ERRO] Falha ao coletar {URL_LISTAGEM}: {exc}")
        return

    time.sleep(2)  # rate limiting educado

    data_coleta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["titulo", "url_materia", "data_coleta"]
        )
        writer.writeheader()
        for m in manchetes:
            writer.writerow(
                {
                    "titulo": m["titulo"],
                    "url_materia": m["url_materia"],
                    "data_coleta": data_coleta,
                }
            )

    with open(TXT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(m["titulo"] for m in manchetes))

    print(f"OK: {len(manchetes)} manchetes salvas em {CSV_PATH}")
    print(f"OK: corpus de títulos salvo em {TXT_PATH}")


if __name__ == "__main__":
    main()
