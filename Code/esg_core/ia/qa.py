"""Perguntas e respostas sobre os dados (RAG): recuperação lexical BM25 + resposta do LLM restrita aos trechos recuperados."""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Optional, Sequence

from ..text_utils import STOPWORDS_PT
from .errors import IARespostaInvalidaError, TextoInvalidoError
from .fidelidade import verificar_fidelidade
from .prompts import VERSAO_QA, construir_prompt_qa
from .sumarizacao import _lista_str, _soma, chamar_json

MSG_SEM_BASE = "Os documentos disponíveis não permitem responder a esta pergunta."


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


_STOP = {_sem_acento(w) for w in STOPWORDS_PT} | {"qual", "quais", "quanto", "quantos", "quantas", "como", "onde", "porque", "falam",
                                                   "fala", "dizem", "diz", "foram", "sao", "sobre", "empresa", "empresas"}


def _radical(t: str) -> str:
    """Radicalização rudimentar para o português (emissões/emissão, empresas/empresa)."""
    for sufixo, troca in (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("eis", "el")):
        if t.endswith(sufixo) and len(t) > 4:
            return t[: -len(sufixo)] + troca
    return t[:-1] if t.endswith("s") and len(t) > 3 else t


def tokens_busca(texto: str) -> list:
    return [_radical(t) for t in re.findall(r"[a-z0-9]+", _sem_acento(str(texto).lower()))
            if t not in _STOP and (len(t) >= 3 or t.isdigit() and len(t) >= 2)]


class IndiceBM25:
    def __init__(self, textos: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(tokens_busca(t)) for t in textos]
        self.dl = [sum(c.values()) for c in self.tf]
        self.n = len(textos)
        self.avgdl = (sum(self.dl) / self.n) if self.n else 0.0
        self.df = Counter(t for c in self.tf for t in c)

    def buscar(self, pergunta: str, k: int = 5) -> list:
        termos = set(tokens_busca(pergunta))
        pontos = []
        for i, c in enumerate(self.tf):
            s = 0.0
            for t in termos:
                if t in c:
                    idf = math.log(1 + (self.n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                    s += idf * c[t] * (self.k1 + 1) / (c[t] + self.k1 * (1 - self.b + self.b * self.dl[i] / (self.avgdl or 1)))
            if s > 0:
                pontos.append((i, s))
        return sorted(pontos, key=lambda x: -x[1])[:k]


def responder(cliente, pergunta: str, documentos: Sequence[dict], k: int = 5, max_tokens: Optional[int] = None) -> dict:
    """`documentos`: {doc_id, titulo?, texto, fonte?, url?, data?}. Sem trechos relevantes, NÃO chama o LLM (evita custo e alucinação)."""
    pergunta = (pergunta or "").strip()
    if len(pergunta) < 3:
        raise TextoInvalidoError("A pergunta está vazia ou curta demais.", sugestao="Escreva a pergunta em uma frase completa.")
    indice = IndiceBM25([f"{d.get('titulo') or ''} {d['texto']}" for d in documentos])
    achados = indice.buscar(pergunta, k)
    base = {"versao_prompt": VERSAO_QA, "trechos": [], "fontes_citadas": [], "lacunas": [], "n_chamadas": 0, "chamou_llm": False,
            "provedor": None, "modelo": None, "tokens_entrada": None, "tokens_saida": None, "fidelidade": None}
    if not achados:
        return {**base, "resposta": MSG_SEM_BASE, "confianca": "baixa",
                "lacunas": ["Nenhum documento disponível contém termos da pergunta."]}
    docs_p, trechos = [], []
    for pos, (i, score) in enumerate(achados, start=1):
        d = documentos[i]
        pid = f"d{pos}"
        docs_p.append({"id": pid, "texto": d["texto"][:3000], "titulo": d.get("titulo"), "fonte": d.get("fonte"), "data": d.get("data")})
        trechos.append({"id": pid, "doc_id": d.get("doc_id"), "titulo": d.get("titulo"), "fonte": d.get("fonte"), "url": d.get("url"),
                        "score": round(score, 3), "trecho": d["texto"][:300]})
    sistema, usuario = construir_prompt_qa(pergunta, docs_p)
    bruto, rs = chamar_json(cliente, sistema, usuario, max_tokens)
    resposta = str(bruto.get("resposta") or "").strip()
    if not resposta:
        raise IARespostaInvalidaError("O modelo devolveu uma resposta vazia.")
    conf = _sem_acento(str(bruto.get("confianca") or "").lower())
    ids = {d["id"] for d in docs_p}
    citados = _lista_str(bruto.get("fontes_citadas"), 10)
    fid = verificar_fidelidade([resposta], "\n".join(d["texto"] for d in docs_p), ids, citados)
    return {**base, "resposta": resposta, "confianca": conf if conf in ("alta", "media", "baixa") else "baixa",
            "fontes_citadas": [c for c in citados if c in ids], "lacunas": _lista_str(bruto.get("lacunas"), 5), "trechos": trechos,
            "fidelidade": fid, "chamou_llm": True, "n_chamadas": len(rs), "provedor": rs[0].provedor, "modelo": rs[0].modelo,
            "tokens_entrada": _soma(rs, "tokens_entrada"), "tokens_saida": _soma(rs, "tokens_saida")}
