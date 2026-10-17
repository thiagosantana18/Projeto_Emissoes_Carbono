"""Utilitários de texto: stopwords PT-BR, tokenização e frequência de palavras."""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

STOPWORDS_PT = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "um", "uma", "uns", "umas",
    "para", "com", "por", "no", "na", "nos", "nas", "que", "se", "sua", "seu", "suas", "seus",
    "é", "ao", "aos", "à", "às", "entre", "sobre", "mais", "como", "já", "até", "diz", "ser",
    "foi", "são", "pelo", "pela", "pelos", "pelas", "esse", "essa", "este", "esta", "isso",
    "ou", "não", "também", "vai", "após", "tem", "têm", "ter", "há", "mas", "só", "pode",
    "podem", "sem", "quando", "onde", "porque", "cada", "todo", "toda", "todos", "todas",
}

_REGEX_PALAVRA = re.compile(r"[a-zà-ú]+")


def tokenizar(texto: str, minimo: int = 3) -> list[str]:
    """Minúsculas, só letras, sem stopwords e sem tokens muito curtos."""
    return [p for p in _REGEX_PALAVRA.findall(str(texto).lower())
            if p not in STOPWORDS_PT and len(p) >= minimo]


def frequencia_palavras(textos: Iterable[str], top_n: int = 20) -> list[tuple[str, int]]:
    contador: Counter = Counter()
    for t in textos:
        contador.update(tokenizar(t))
    return contador.most_common(top_n)


def contar_palavras(texto: str) -> int:
    """Número de palavras 'brutas' (usado como metadado do corpus)."""
    return len(re.findall(r"\w+", str(texto), flags=re.UNICODE))
