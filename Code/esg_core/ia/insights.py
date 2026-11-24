"""Insights de gestão de emissões gerados por LLM a partir de dados REAIS DO PROJETO (agregados), com checagem de fidelidade numérica."""
from __future__ import annotations

from typing import Optional

from .errors import IARespostaInvalidaError
from .fidelidade import verificar_fidelidade
from .prompts import VERSAO_INSIGHTS, construir_prompt_insights
from .sumarizacao import _lista_str, _ods, _soma, chamar_json


def br(v: float, casas: int = 2) -> str:
    """Formato brasileiro: 1.234,56"""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def renderizar_contexto_emissoes(ctx: dict) -> str:
    p = ctx.get("periodo") or {}
    linhas = [f"Período analisado: {p.get('inicio')} a {p.get('fim')}, {ctx.get('n_registros')} registros de atividade.",
              f"Emissão total no período: {br(ctx.get('total_kgco2e', 0))} kgCO2e.", "Emissão por tipo de atividade (maior para menor):"]
    linhas += [f"- {x['nome']}: {br(x['kgco2e'])} kgCO2e ({br(x['percentual'], 1)}% do total)" for x in ctx.get("por_tipo_atividade", [])]
    linhas.append("Emissão por unidade (maior para menor):")
    linhas += [f"- {x['nome']}: {br(x['kgco2e'])} kgCO2e ({br(x['percentual'], 1)}% do total)" for x in ctx.get("por_unidade", [])]
    if ctx.get("variacao_ultimo_mes_pct") is not None:
        linhas.append(f"Variação do último mês em relação ao anterior: {br(ctx['variacao_ultimo_mes_pct'], 1)}%.")
    ultimos = (ctx.get("por_mes") or [])[-6:]
    if ultimos:
        linhas.append("Emissão mensal (últimos meses): " + "; ".join(f"{m['mes']}: {br(m['kgco2e'])} kgCO2e" for m in ultimos) + ".")
    fatores = ctx.get("fatores_utilizados") or []
    if fatores:
        linhas.append("Fatores de emissão usados (kgCO2e por unidade de medida): " + "; ".join(
            f"{f['tipo_atividade']}: {str(f['fator_emissao_kgco2e']).replace('.', ',')} por {f['unidade_medida']} (rótulo de fonte: {f['fonte_fator']})" for f in fatores) + ".")
    linhas += [f"Observação sobre os dados: {o}" for o in ctx.get("observacoes", [])]
    return "\n".join(linhas)


def renderizar_previsao(prev: dict) -> str:
    linhas = [f"Previsão de emissões mensais (método {prev['melhor']}; erro percentual médio no backtest: {br(prev['mape_melhor'], 1)}%; "
              f"meta de {br(prev['meta_mape'], 0)}% {'atingida' if prev['atinge_meta'] else 'NÃO atingida'}). Dados de base: série de {prev['serie']['n_meses']} meses."]
    linhas += [f"{x['mes']}: {br(x['previsto'])} kgCO2e (faixa {br(x['min'])} a {br(x['max'])})" for x in prev["previsoes"]]
    linhas.append(f"Observação: {prev['intervalo']}.")
    return "\n".join(linhas)


def renderizar_sentimento(contagem: dict) -> str:
    total = sum(contagem.values())
    return (f"Sentimento das {total} manchetes de notícias ESG classificadas por modelo local: "
            + ", ".join(f"{k}: {v}" for k, v in contagem.items()) + ". São previsões de um modelo, sem validação contra rótulos humanos.")


def validar_insights(d: dict) -> dict:
    def gravidade(v):
        v = str(v or "").lower().replace("é", "e")
        return v if v in ("alta", "media", "baixa") else "media"
    destaques = [{"titulo": str(x.get("titulo") or "").strip(), "detalhe": str(x.get("detalhe") or "").strip()}
                 for x in d.get("destaques") or [] if isinstance(x, dict) and str(x.get("titulo") or x.get("detalhe") or "").strip()]
    riscos = [{"descricao": str(x["descricao"]).strip(), "gravidade": gravidade(x.get("gravidade"))}
              for x in d.get("riscos") or [] if isinstance(x, dict) and str(x.get("descricao") or "").strip()]
    recs = [{"acao": str(x["acao"]).strip(), "justificativa": str(x.get("justificativa") or "").strip(),
             "impacto_esperado": str(x.get("impacto_esperado") or "").strip(), "prioridade": gravidade(x.get("prioridade")), "ods": _ods(x.get("ods"))}
            for x in d.get("recomendacoes") or [] if isinstance(x, dict) and str(x.get("acao") or "").strip()]
    if not destaques and not recs:
        raise IARespostaInvalidaError("O modelo não devolveu destaques nem recomendações.")
    return {"destaques": destaques[:6], "riscos": riscos[:6], "recomendacoes": recs[:6],
            "alertas_de_dados": _lista_str(d.get("alertas_de_dados"), 6), "fontes_citadas": _lista_str(d.get("fontes_citadas"), 10)}


def gerar_insights(cliente, contexto: dict, foco: Optional[str] = None, previsao: Optional[dict] = None,
                   sentimento: Optional[dict] = None, resumo_noticias: Optional[str] = None, max_tokens: Optional[int] = None) -> dict:
    docs = [{"id": "E1", "titulo": "Emissões da empresa (dados de atividade agregados)", "fonte": "base do projeto",
             "texto": renderizar_contexto_emissoes(contexto)}]
    if previsao:
        docs.append({"id": "E2", "titulo": "Previsão de emissões", "fonte": "modelo de previsão do projeto", "texto": renderizar_previsao(previsao)})
    if sentimento:
        docs.append({"id": "S1", "titulo": "Sentimento das notícias", "fonte": "modelo local", "texto": renderizar_sentimento(sentimento)})
    if resumo_noticias:
        docs.append({"id": "N1", "titulo": "Resumo das notícias ESG recentes", "fonte": "resumo gerado por IA", "texto": resumo_noticias})
    sistema, usuario = construir_prompt_insights(docs, foco)
    bruto, rs = chamar_json(cliente, sistema, usuario, max_tokens)
    ins = validar_insights(bruto)
    ids = {d["id"] for d in docs}
    gerados = [x["titulo"] + " " + x["detalhe"] for x in ins["destaques"]] + [x["descricao"] for x in ins["riscos"]] \
        + [f"{x['acao']} {x['justificativa']} {x['impacto_esperado']}" for x in ins["recomendacoes"]] + ins["alertas_de_dados"]
    fid = verificar_fidelidade(gerados, "\n".join(d["texto"] for d in docs), ids, ins["fontes_citadas"])
    ins["fontes_citadas"] = [i for i in ins["fontes_citadas"] if i in ids]
    return {"insights": ins, "fontes": [{"id": d["id"], "titulo": d["titulo"]} for d in docs], "versao_prompt": VERSAO_INSIGHTS,
            "n_chamadas": len(rs), "provedor": rs[0].provedor, "modelo": rs[0].modelo, "tokens_entrada": _soma(rs, "tokens_entrada"),
            "tokens_saida": _soma(rs, "tokens_saida"), "fidelidade": fid, "texto_contexto": docs[0]["texto"]}
