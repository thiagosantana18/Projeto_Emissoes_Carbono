"""Verificação automática de fidelidade: todo número gerado precisa existir na fonte e toda citação precisa ser de um documento real."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Iterable

_NUMERO = re.compile(r"(?<![\w.,])(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)%?")
_IGNORAR = re.compile(r"\bODS[\s-]*\d+(?:[.,]\d+)?|\bAgenda\s*2030", re.IGNORECASE)


def normalizar_numero(token: str) -> str:
    """'1.234,5' (pt-BR), '1,234.5' (en-US) e '1234.5' viram a mesma forma canônica; '%' é descartado."""
    t = token.strip().rstrip("%").strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", t):
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+,\d+", t):
        t = t.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    try:
        return format(Decimal(t).normalize(), "f")
    except InvalidOperation:
        return t


def extrair_numeros(texto: str) -> set:
    return {normalizar_numero(m.group(0)) for m in _NUMERO.finditer(texto or "")}


def numeros_relevantes(texto: str) -> set:
    """Números que merecem checagem: ignora inteiros de 1 dígito sem '%' (contagens como '3 pontos') e menções a ODS/Agenda 2030."""
    limpo = _IGNORAR.sub(" ", texto or "")
    saida = set()
    for m in _NUMERO.finditer(limpo):
        bruto = m.group(0)
        if "%" in bruto or "," in bruto or "." in bruto or len(bruto) >= 2:
            saida.add(normalizar_numero(bruto))
    return saida


def verificar_fidelidade(gerados: Iterable[str], fonte: str, ids_validos: Iterable[str], ids_citados: Iterable[str]) -> dict:
    gerado_nums = set()
    for t in gerados:
        gerado_nums |= numeros_relevantes(t)
    base = extrair_numeros(fonte)
    faltantes = sorted(gerado_nums - base, key=lambda x: (len(x), x))
    invalidas = sorted(set(ids_citados) - set(ids_validos))
    return {"ok": not faltantes and not invalidas, "numeros_verificados": len(gerado_nums),
            "numeros_nao_encontrados": faltantes, "citacoes_invalidas": invalidas,
            "observacao": ("Todos os números e citações conferem com as fontes." if not faltantes and not invalidas else
                           "Há números ou citações que não constam nas fontes: confira antes de usar (o modelo pode ter calculado ou inventado).")}
