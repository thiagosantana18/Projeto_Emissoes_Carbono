"""
Atualiza o pipeline de dados em ordem:
  1. (opcional) regenera a amostra sintética de emissões
  2. scraping de ODS e notícias (precisa de internet; respeita robots.txt)
  3. reconstrói corpus_llm.jsonl, contexto_relatorio.json e templates de avaliação

Uso (a partir da raiz):
    python Scripts/atualizar_dados.py                  # scraping + corpus
    python Scripts/atualizar_dados.py --sem-scraping   # só reconstrói o corpus
    python Scripts/atualizar_dados.py --regenerar-amostra
Um scraper que falhe (sem rede, robots.txt bloqueando) NÃO interrompe as etapas seguintes.
"""
import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def rodar(rotulo: str, script: str, *args: str) -> bool:
    print(f"\n=== {rotulo}")
    r = subprocess.run([sys.executable, str(RAIZ / script), *args], cwd=RAIZ)
    if r.returncode != 0:
        print(f"[AVISO] {rotulo} terminou com código {r.returncode}")
    return r.returncode == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-scraping", action="store_true")
    ap.add_argument("--regenerar-amostra", action="store_true")
    a = ap.parse_args()
    if a.regenerar_amostra:
        rodar("Amostra sintética de emissões", "Code/data_acquisition/generate_sample_emissions.py")
    if not a.sem_scraping:
        rodar("Scraping ODS 12/13", "Code/data_acquisition/scrape_ods_ecycle.py")
        rodar("Scraping notícias ESG", "Code/data_acquisition/scrape_noticias_esg.py")
    ok = rodar("Corpus para LLM", "Code/data_preparation/build_corpus.py")
    sys.exit(0 if ok else 1)
