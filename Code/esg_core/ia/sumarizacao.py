"""
Sumarização de textos e documentos com LLM: chamada com saída JSON validada, divisão de textos longos em trechos,
map-reduce para grandes volumes, verificação de fidelidade e linha de base extrativa (sem IA) para comparação.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Optional, Sequence

from ..text_utils import tokenizar
from .errors import IARespostaInvalidaError, TextoInvalidoError
from .fidelidade import verificar_fidelidade
from .prompts import (OBJETIVO_PADRAO, VERSAO_SUMARIO, VERSOES_SUMARIO, construir_prompt_parcial,
                      construir_prompt_reducao, construir_prompt_sumario)


# ---------------------------------------------------------------- JSON do modelo
def extrair_json(texto: str) -> dict:
    """Extrai o primeiro objeto JSON de uma resposta (tolera ```json ... ``` e texto antes/depois)."""
    t = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", (texto or "").strip(), flags=re.IGNORECASE)
    ini = t.find("{")
    if ini == -1:
        raise ValueError("sem objeto JSON")
    obj, _ = json.JSONDecoder().raw_decode(t[ini:])
    if not isinstance(obj, dict):
        raise ValueError("JSON não é um objeto")
    return obj


def chamar_json(cliente, sistema: str, usuario: str, max_tokens: Optional[int] = None) -> tuple:
    """Chama o modelo e devolve (dict, [respostas]). Se o JSON vier inválido, tenta UMA vez pedir a correção."""
    r1 = cliente.gerar(sistema, usuario, max_tokens)
    try:
        return extrair_json(r1.texto), [r1]
    except ValueError:
        if r1.truncada:
            raise IARespostaInvalidaError("A resposta do modelo foi cortada por atingir o limite de tokens.",
                                          sugestao="Aumente ESG_IA_MAX_TOKENS ou envie menos texto.") from None
    r2 = cliente.gerar(sistema, usuario + "\n\nSua resposta anterior não era um JSON válido. "
                                          "Responda novamente APENAS com o objeto JSON pedido.", max_tokens)
    try:
        return extrair_json(r2.texto), [r1, r2]
    except ValueError:
        raise IARespostaInvalidaError("O modelo não devolveu um JSON válido, mesmo após uma nova tentativa.",
                                      sugestao="Tente novamente ou use outro modelo/provedor.") from None


def _lista_str(v, maximo: int = 12) -> list:
    return [str(x).strip() for x in v if str(x).strip()][:maximo] if isinstance(v, list) else []


def _ods(v) -> Optional[str]:
    d = re.sub(r"\D", "", str(v or ""))
    return d if d in ("12", "13") else None


def validar_sumario(d: dict) -> dict:
    """Garante o esquema do sumário: preenche o que faltar, descarta itens malformados, falha se não houver resumo."""
    resumo = str((d or {}).get("resumo_executivo") or "").strip()
    if not resumo:
        raise IARespostaInvalidaError("O modelo devolveu um resumo vazio.")
    riscos = []
    for x in d.get("riscos_e_oportunidades") or []:
        if isinstance(x, dict) and str(x.get("descricao") or "").strip():
            tipo = str(x.get("tipo") or "").lower()
            riscos.append({"tipo": tipo if tipo in ("risco", "oportunidade") else "outro",
                           "descricao": str(x["descricao"]).strip(), "fontes": _lista_str(x.get("fontes"), 8)})
    recs = []
    for x in d.get("recomendacoes") or []:
        if isinstance(x, dict) and str(x.get("acao") or "").strip():
            recs.append({"acao": str(x["acao"]).strip(), "justificativa": str(x.get("justificativa") or "").strip(),
                         "ods": _ods(x.get("ods"))})
    return {"resumo_executivo": resumo, "pontos_chave": _lista_str(d.get("pontos_chave")),
            "riscos_e_oportunidades": riscos[:8], "recomendacoes": recs[:8],
            "lacunas": _lista_str(d.get("lacunas")), "fontes_citadas": _lista_str(d.get("fontes_citadas"), 40)}


def textos_do_sumario(s: dict) -> list:
    """Todos os trechos gerados (para a checagem de números)."""
    saida = [s["resumo_executivo"], *s["pontos_chave"], *s["lacunas"]]
    saida += [r["descricao"] for r in s["riscos_e_oportunidades"]]
    saida += [f"{r['acao']} {r['justificativa']}" for r in s["recomendacoes"]]
    return saida


# ---------------------------------------------------------------- texto
def dividir_em_trechos(texto: str, max_chars: int = 8000) -> list:
    """Quebra um texto longo em trechos de até `max_chars`, respeitando parágrafos e, se preciso, frases."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", texto.strip()) if p.strip()]
    pedacos = []
    for p in paragrafos:
        if len(p) <= max_chars:
            pedacos.append(p)
            continue
        atual = ""
        for frase in re.split(r"(?<=[.!?])\s+", p):
            while len(frase) > max_chars:                      # frase gigante: corte duro
                pedacos.append(frase[:max_chars])
                frase = frase[max_chars:]
            if atual and len(atual) + len(frase) + 1 > max_chars:
                pedacos.append(atual)
                atual = ""
            atual = f"{atual} {frase}".strip()
        if atual:
            pedacos.append(atual)
    trechos, atual = [], ""
    for p in pedacos:
        if atual and len(atual) + len(p) + 2 > max_chars:
            trechos.append(atual)
            atual = ""
        atual = f"{atual}\n\n{p}".strip()
    if atual:
        trechos.append(atual)
    return trechos


def resumo_extrativo(texto: str, n_frases: int = 3) -> list:
    """Linha de base SEM IA: escolhe as frases com maior soma de frequência de termos (mantendo a ordem original)."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+|\n+", texto) if len(f.strip()) > 25]
    if len(frases) <= n_frases:
        return frases
    freq = Counter(tokenizar(texto))
    def pontuacao(f):
        toks = tokenizar(f)
        return sum(freq[t] for t in toks) / (len(toks) ** 0.5) if toks else 0.0
    melhores = sorted(range(len(frases)), key=lambda i: pontuacao(frases[i]), reverse=True)[:n_frases]
    return [frases[i] for i in sorted(melhores)]


# ---------------------------------------------------------------- orquestração
def _soma(respostas, campo: str) -> Optional[int]:
    vals = [getattr(r, campo) for r in respostas if getattr(r, campo) is not None]
    return sum(vals) if vals else None


def _lotes(docs: list, max_chars: int) -> list:
    lotes, atual, tam = [], [], 0
    for d in docs:
        n = len(d["texto"])
        if atual and tam + n > max_chars:
            lotes.append(atual)
            atual, tam = [], 0
        atual.append(d)
        tam += n
    if atual:
        lotes.append(atual)
    return lotes


def sumarizar_documentos(cliente, documentos: Sequence[dict], objetivo: str = OBJETIVO_PADRAO, nivel: str = "executivo",
                         versao: str = VERSAO_SUMARIO, max_chars_lote: int = 24000, max_lotes: int = 8,
                         max_tokens: Optional[int] = None, prefixo_id: str = "d", incluir_baseline: bool = True) -> dict:
    """
    `documentos`: dicts com {doc_id, texto, titulo?, fonte?, data?, url?}. Até `max_chars_lote` caracteres vai numa só chamada;
    acima disso usa map-reduce (um resumo por lote + um resumo final). Devolve o sumário validado + metadados + fidelidade.
    """
    if versao not in VERSOES_SUMARIO:
        raise TextoInvalidoError(f"Versão de prompt desconhecida: {versao!r}.", sugestao=f"Opções: {', '.join(VERSOES_SUMARIO)}.")
    docs, fontes = [], []
    for i, d in enumerate(documentos, start=1):
        texto = str(d.get("texto") or "").strip()
        if not texto:
            continue
        pid = f"{prefixo_id}{i}"
        docs.append({"id": pid, "texto": texto[: max_chars_lote // 2], "titulo": d.get("titulo"), "fonte": d.get("fonte"), "data": d.get("data")})
        fontes.append({"id": pid, "doc_id": d.get("doc_id"), "titulo": d.get("titulo"), "fonte": d.get("fonte"), "url": d.get("url"), "data": d.get("data")})
    if not docs:
        raise TextoInvalidoError("Não há texto para resumir.", sugestao="Envie ao menos um documento com conteúdo.")
    lotes = _lotes(docs, max_chars_lote)
    if len(lotes) > max_lotes:
        raise TextoInvalidoError(f"O volume de texto exige {len(lotes)} lotes (máximo {max_lotes}).",
                                 sugestao="Filtre os documentos (tipo, tag) ou reduza a quantidade.")
    ids = {d["id"] for d in docs}
    fonte_total = "\n".join(d["texto"] for d in docs)
    respostas, avisos, ids_r = [], [], {}

    if versao == "sumario_v1":                                         # linha de base de prompt: texto livre
        sistema, usuario = construir_prompt_sumario(docs, objetivo, nivel, versao)
        r = cliente.gerar(sistema, usuario, max_tokens)
        respostas.append(r)
        resumo = {"resumo_executivo": r.texto.strip(), "pontos_chave": [], "riscos_e_oportunidades": [], "recomendacoes": [],
                  "lacunas": [], "fontes_citadas": []}
        metodo = "direto"
    elif len(lotes) == 1:
        sistema, usuario = construir_prompt_sumario(docs, objetivo, nivel, versao)
        bruto, rs = chamar_json(cliente, sistema, usuario, max_tokens)
        respostas += rs
        resumo, metodo = validar_sumario(bruto), "direto"
    else:
        parciais = []
        for k, lote in enumerate(lotes, start=1):
            sistema, usuario = construir_prompt_parcial(lote, objetivo, k, len(lotes))
            bruto, rs = chamar_json(cliente, sistema, usuario, max_tokens)
            respostas += rs
            texto_parcial = str(bruto.get("resumo_parcial") or "").strip()
            if not texto_parcial:
                raise IARespostaInvalidaError(f"O resumo parcial do lote {k} veio vazio.")
            ids_lote = [d["id"] for d in lote]
            ids_r[f"r{k}"] = ids_lote
            pontos = " | ".join(_lista_str(bruto.get("pontos_chave"), 8))
            parciais.append({"id": f"r{k}", "titulo": f"resumo parcial {k}", "fonte": "resumo intermediário",
                             "texto": f"[documentos originais: {', '.join(ids_lote)}] {texto_parcial}" + (f"\nPontos: {pontos}" if pontos else "")})
        sistema, usuario = construir_prompt_reducao(parciais, objetivo, nivel)
        bruto, rs = chamar_json(cliente, sistema, usuario, max_tokens)
        respostas += rs
        resumo, metodo = validar_sumario(bruto), "map_reduce"

    # citações: expande ids de resumos parciais (r1) para os documentos originais e separa as inválidas
    citados_brutos = list(resumo["fontes_citadas"]) + [f for r in resumo["riscos_e_oportunidades"] for f in r["fontes"]]
    def expandir(lista):
        saida = []
        for i in lista:
            saida += ids_r.get(i, [i])
        return saida
    resumo["fontes_citadas"] = sorted({i for i in expandir(resumo["fontes_citadas"]) if i in ids}, key=lambda x: (len(x), x))
    for r in resumo["riscos_e_oportunidades"]:
        r["fontes"] = [i for i in expandir(r["fontes"]) if i in ids]
    fid = verificar_fidelidade(textos_do_sumario(resumo), fonte_total, ids | set(ids_r), citados_brutos)
    if versao == "sumario_v1":
        fid["observacao"] += " (prompt v1 em texto livre: não há citações estruturadas para verificar)"
    r0 = respostas[0]
    return {
        "resumo": resumo, "fontes": fontes, "metodo": metodo, "n_documentos": len(docs), "n_lotes": len(lotes),
        "n_chamadas": len(respostas), "versao_prompt": versao, "provedor": r0.provedor, "modelo": r0.modelo,
        "tokens_entrada": _soma(respostas, "tokens_entrada"), "tokens_saida": _soma(respostas, "tokens_saida"),
        "latencia_ms": round(sum(r.latencia_ms for r in respostas), 1), "fidelidade": fid, "avisos": avisos,
        "baseline_extrativo": resumo_extrativo(fonte_total, 3) if incluir_baseline else [],
    }


def sumarizar_texto(cliente, texto: str, objetivo: str = OBJETIVO_PADRAO, nivel: str = "executivo", titulo: str = "Texto enviado",
                    max_chars_trecho: int = 8000, **kw) -> dict:
    """Resume um texto longo (relatório, artigo): divide em trechos e usa sumarizar_documentos (map-reduce se necessário)."""
    trechos = dividir_em_trechos(texto, max_chars_trecho)
    docs = [{"doc_id": f"trecho-{i}", "texto": t, "titulo": f"{titulo} — parte {i}/{len(trechos)}", "fonte": "texto enviado"}
            for i, t in enumerate(trechos, start=1)]
    kw.setdefault("prefixo_id", "p")
    return sumarizar_documentos(cliente, docs, objetivo, nivel, **kw)
