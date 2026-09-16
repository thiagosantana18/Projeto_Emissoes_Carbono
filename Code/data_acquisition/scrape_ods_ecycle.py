"""
Code/data_acquisition/scrape_ods_ecycle.py

Objetivo:
    Coletar o conteúdo introdutório dos ODS 12 e 13 (Agenda 2030) publicado
    pelo portal eCycle, para alimentar a seção de contexto/estatísticas da
    aplicação (nuvem de palavras e estatísticas básicas).

Por que este script roda separado da aplicação Streamlit:
    Scraping é uma operação de rede, mais lenta e sujeita a bloqueios/latência.
    Rodá-lo separadamente (fora do ciclo de vida do Streamlit) evita repetir a
    coleta a cada interação do usuário — o resultado é salvo em CSV/TXT e a
    aplicação apenas lê esses arquivos (com cache).

Boas práticas aplicadas:
    - Verificação do robots.txt via urllib.robotparser ANTES de qualquer
      requisição às páginas de conteúdo.
    - User-Agent identificado (não se passa por navegador).
    - Delay entre requisições (rate limiting educado).
    - Falha de forma clara e não silenciosa se o robots.txt proibir o acesso.

Saídas:
    Data/raw/ods_conteudo.csv  -> dados estruturados (ods, título, meta, texto)
    Data/raw/ods_conteudo.txt  -> corpus de texto (para nuvem de palavras)

Como executar (fora do sandbox, com acesso à internet):
    python Code/data_acquisition/scrape_ods_ecycle.py
"""

import csv
import time
import urllib.robotparser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "ProjetoESG-CarbonoBot/1.0 (+uso educacional; contato: equipe-projeto@exemplo.com)"
HEADERS = {"User-Agent": USER_AGENT}

# Páginas-alvo: descrição oficial (traduzida) dos ODS 12 e 13 da Agenda 2030
FONTES = [
    {"ods": "ODS 12", "url": "https://www.ecycle.com.br/ods-12/"},
    {"ods": "ODS 13", "url": "https://www.ecycle.com.br/ods-13/"},
]

# Diretório de saída (raiz do projeto / Data / raw)
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "Data" / "raw"
CSV_PATH = OUTPUT_DIR / "ods_conteudo.csv"
TXT_PATH = OUTPUT_DIR / "ods_conteudo.txt"


def pode_coletar(url: str) -> bool:
    """
    Verifica no robots.txt do domínio se o nosso User-Agent tem permissão
    para acessar a URL informada. Retorna True/False.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:
        print(f"[AVISO] Não foi possível ler {robots_url}: {exc}")
        # Postura conservadora: se não conseguimos ler o robots.txt,
        # não assumimos permissão.
        return False

    permitido = rp.can_fetch(USER_AGENT, url)
    print(f"[robots.txt] {url} -> {'PERMITIDO' if permitido else 'BLOQUEADO'}")
    return permitido


def extrair_conteudo(url: str) -> dict:
    """Baixa a página e extrai título + parágrafos principais do artigo."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    titulo = soup.find("h1")
    titulo = titulo.get_text(strip=True) if titulo else ""

    # Parágrafos dentro do corpo do artigo (heurística: tag <article> ou <p> gerais)
    artigo = soup.find("article") or soup
    paragrafos = [
        p.get_text(" ", strip=True)
        for p in artigo.find_all("p")
        if len(p.get_text(strip=True)) > 40  # ignora parágrafos muito curtos (menus, avisos)
    ]

    return {"titulo": titulo, "paragrafos": paragrafos}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    linhas_csv = []
    textos_corpus = []

    for fonte in FONTES:
        url = fonte["url"]
        ods = fonte["ods"]

        if not pode_coletar(url):
            print(f"[PULANDO] {url} não permite coleta segundo o robots.txt.")
            continue

        try:
            conteudo = extrair_conteudo(url)
        except requests.RequestException as exc:
            print(f"[ERRO] Falha ao coletar {url}: {exc}")
            continue

        data_coleta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for paragrafo in conteudo["paragrafos"]:
            linhas_csv.append(
                {
                    "ods": ods,
                    "titulo_pagina": conteudo["titulo"],
                    "trecho": paragrafo,
                    "url_fonte": url,
                    "data_coleta": data_coleta,
                }
            )
            textos_corpus.append(paragrafo)

        # Rate limiting educado entre requisições
        time.sleep(2)

    if not linhas_csv:
        print("Nenhum conteúdo coletado (robots.txt bloqueou ou houve erro de rede).")
        return

    # --- Salva CSV estruturado ---
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["ods", "titulo_pagina", "trecho", "url_fonte", "data_coleta"]
        )
        writer.writeheader()
        writer.writerows(linhas_csv)

    # --- Salva corpus em TXT (para nuvem de palavras) ---
    with open(TXT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(textos_corpus))

    print(f"OK: {len(linhas_csv)} trechos salvos em {CSV_PATH}")
    print(f"OK: corpus de texto salvo em {TXT_PATH}")


if __name__ == "__main__":
    main()
