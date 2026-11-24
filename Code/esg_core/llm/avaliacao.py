"""Métricas de classificação (sem dependências externas) para avaliar o sentimento contra o gabarito humano."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional, Sequence

ROTULOS = ("positivo", "neutro", "negativo")
_ALIAS = {"positive": "positivo", "neutral": "neutro", "negative": "negativo",
          "positivo": "positivo", "neutro": "neutro", "negativo": "negativo"}


def normalizar_rotulo(valor) -> Optional[str]:
    return _ALIAS.get(str(valor).strip().lower()) if valor is not None else None


def matriz_confusao(reais: Sequence[str], previstos: Sequence[str], rotulos=ROTULOS) -> dict:
    m = {r: {p: 0 for p in rotulos} for r in rotulos}
    for r, p in zip(reais, previstos):
        m[r][p] += 1
    return m


def metricas(reais: Sequence[str], previstos: Sequence[str], rotulos=ROTULOS) -> dict:
    if len(reais) != len(previstos):
        raise ValueError("reais e previstos devem ter o mesmo tamanho")
    n = len(reais)
    conf = matriz_confusao(reais, previstos, rotulos)
    por_classe = {}
    for r in rotulos:
        vp = conf[r][r]
        fp = sum(conf[o][r] for o in rotulos if o != r)
        fn = sum(conf[r][o] for o in rotulos if o != r)
        prec = vp / (vp + fp) if vp + fp else 0.0
        rev = vp / (vp + fn) if vp + fn else 0.0
        f1 = 2 * prec * rev / (prec + rev) if prec + rev else 0.0
        por_classe[r] = {"precisao": round(prec, 4), "revocacao": round(rev, 4), "f1": round(f1, 4),
                         "suporte": sum(conf[r].values())}
    com_suporte = [r for r in rotulos if por_classe[r]["suporte"] > 0]
    f1_macro = sum(por_classe[r]["f1"] for r in com_suporte) / len(com_suporte) if com_suporte else 0.0
    acertos = sum(conf[r][r] for r in rotulos)
    return {"n": n, "acuracia": round(acertos / n, 4) if n else 0.0, "f1_macro": round(f1_macro, 4),
            "por_classe": por_classe, "matriz_confusao": conf}


def carregar_gabarito(caminho: Path) -> tuple[list[dict], list[str]]:
    """Lê o gabarito rotulado. Linhas sem rótulo são ignoradas; rótulos inválidos geram aviso."""
    itens, avisos = [], []
    with open(caminho, newline="", encoding="utf-8") as f:
        for i, linha in enumerate(csv.DictReader(f), start=2):
            bruto = (linha.get("rotulo_humano") or "").strip()
            if not bruto:
                continue
            rot = normalizar_rotulo(bruto)
            if rot is None:
                avisos.append(f"Linha {i}: rótulo inválido {bruto!r} (use positivo, neutro ou negativo).")
                continue
            itens.append({"doc_id": linha.get("doc_id", ""), "titulo": linha.get("titulo", ""), "rotulo_humano": rot})
    return itens, avisos
