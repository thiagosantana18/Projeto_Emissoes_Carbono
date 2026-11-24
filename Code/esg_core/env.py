"""Carregador mínimo de arquivo .env (sem dependências). Não sobrescreve variáveis já definidas no ambiente."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from . import paths


def carregar_dotenv(caminho: Optional[Path] = None) -> int:
    """Lê `<raiz>/.env` (formato CHAVE=valor, # comentários, aspas opcionais). Devolve quantas variáveis definiu."""
    if caminho is None:
        try:
            caminho = paths.raiz_projeto() / ".env"
        except FileNotFoundError:
            return 0
    if not caminho.is_file():
        return 0
    definidas = 0
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave, valor = chave.strip(), valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        elif " #" in valor:
            valor = valor.split(" #", 1)[0].strip()
        if chave and valor and chave not in os.environ:
            os.environ[chave] = valor
            definidas += 1
    return definidas
