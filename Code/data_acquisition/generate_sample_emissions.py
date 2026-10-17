"""
Gera o dataset sintético de atividade/emissões em Data/processed/amostra_emissoes.csv.
Reprodutível (seed fixa). Uso: python Code/data_acquisition/generate_sample_emissions.py [--meses 24] [--fim 2026-09]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esg_core import paths  # noqa: E402
from esg_core.amostra import gerar_amostra_emissoes  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", type=int, default=24)
    ap.add_argument("--fim", default="2026-09", help="último mês (AAAA-MM)")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    df = gerar_amostra_emissoes(a.meses, a.fim, a.seed)
    destino = paths.caminho_emissoes_base()
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, index=False)
    print(f"OK: {len(df)} linhas ({df['mes_referencia'].min()} a {df['mes_referencia'].max()}) em {destino}")
