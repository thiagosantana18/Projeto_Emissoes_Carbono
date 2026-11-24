"""
Gera o Data Quality Report (TDSP) a partir dos dados atuais: Docs/Data_Report/Data_Quality_Report.md
Uso (a partir da raiz): python Scripts/gerar_relatorio_qualidade.py
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Code"))
from esg_core.qualidade import relatorio_qualidade, renderizar_relatorio_md  # noqa: E402

if __name__ == "__main__":
    destino = RAIZ / "Docs" / "Data_Report" / "Data_Quality_Report.md"
    destino.write_text(renderizar_relatorio_md(relatorio_qualidade()), encoding="utf-8")
    print(f"OK: {destino}")
