"""API REST (FastAPI) do projeto. Execução: `uvicorn App.api.main:app --reload` a partir da raiz."""
import sys
from pathlib import Path

# Torna o pacote compartilhado Code/esg_core importável (layout: <raiz>/App/api/__init__.py).
_CODE = Path(__file__).resolve().parents[2] / "Code"
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))
