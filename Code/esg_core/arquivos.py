"""Extração de texto de arquivos enviados pelo usuário (relatórios de sustentabilidade em PDF, TXT, MD)."""
from __future__ import annotations

import io
from pathlib import Path


def extrair_texto(nome: str, conteudo: bytes, max_paginas: int = 200) -> tuple:
    """Devolve (texto, avisos). PDF exige `pypdf` (opcional); PDFs escaneados (imagem) não têm texto extraível."""
    ext = Path(nome).suffix.lower()
    avisos: list = []
    if ext in (".txt", ".md", ".csv"):
        for cod in ("utf-8", "latin-1"):
            try:
                return conteudo.decode(cod), avisos
            except UnicodeDecodeError:
                continue
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Para ler PDF instale o pacote opcional: pip install pypdf") from exc
        leitor = PdfReader(io.BytesIO(conteudo))
        paginas = leitor.pages[:max_paginas]
        if len(leitor.pages) > max_paginas:
            avisos.append(f"O PDF tem {len(leitor.pages)} páginas; só as primeiras {max_paginas} foram lidas.")
        texto = "\n\n".join((p.extract_text() or "").strip() for p in paginas).strip()
        if not texto:
            avisos.append("Nenhum texto foi extraído: o PDF pode ser escaneado (imagem). Use um PDF com texto selecionável ou OCR.")
        return texto, avisos
    raise ValueError(f"Formato não suportado: '{ext or nome}'. Use .txt, .md ou .pdf.")
