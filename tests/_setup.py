"""Torna Code/ e a raiz do projeto importáveis nos testes."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
for p in (RAIZ / "Code", RAIZ / "Code" / "data_acquisition", RAIZ):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
