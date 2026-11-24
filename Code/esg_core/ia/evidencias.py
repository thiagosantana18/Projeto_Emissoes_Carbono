"""
Evidências de uso real da IA: roda os casos de uso sobre os dados do projeto e produz um relatório em Markdown com as saídas,
a verificação de fidelidade, o consumo de tokens e (opcional) a comparação entre versões de prompt.
Executado por Scripts/gerar_evidencias_ia.py com a SUA chave; nada aqui é gerado sem chamar o provedor de verdade.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from .. import data_access as da
from ..llm.errors import ErroLLM

PERGUNTAS = ["Qual atividade mais contribui para as emissões da empresa e quanto representa?",
             "O que as notícias coletadas dizem sobre neutralidade climática?",
             "O que a meta 13.2 do ODS 13 propõe?",
             "Qual é a receita de bolo de cenoura?"]          # pergunta de controle: a IA deve dizer que não sabe


def _tentar(nome: str, tipo: str, entrada: str, fn) -> dict:
    try:
        return {"nome": nome, "tipo": tipo, "entrada": entrada, "resultado": fn()}
    except ErroLLM as exc:
        return {"nome": nome, "tipo": tipo, "entrada": entrada, "erro": {"codigo": exc.codigo, "mensagem": exc.mensagem, "sugestao": exc.sugestao}}


def coletar_evidencias(servico, comparar_prompts: bool = False, provedor: Optional[str] = None) -> dict:
    itens = [_tentar("Resumo das notícias ESG coletadas", "sumario_corpus", "corpus (tipo=noticia, até 15 documentos)",
                     lambda: servico.sumarizar_corpus(tipo="noticia", limite=15, provedor=provedor))]
    ods = da.carregar_ods()
    if not ods.empty:
        texto = "\n\n".join(f"{r.ods} — {r.secao or ''}\n{r.trecho}" for r in ods.itertuples())
        itens.append(_tentar("Resumo do texto dos ODS 12 e 13 coletados", "sumario_texto", f"texto de {len(texto)} caracteres",
                             lambda: servico.sumarizar_texto(texto, titulo="Trechos dos ODS 12 e 13", provedor=provedor)))
    for p in PERGUNTAS:
        itens.append(_tentar(f"Pergunta: {p}", "pergunta", p, lambda p=p: servico.perguntar(p, provedor=provedor)))
    itens.append(_tentar("Insights sobre as emissões", "insights", "dados agregados de emissões + previsão",
                         lambda: servico.insights_emissoes(foco="reduzir as maiores fontes de emissão", provedor=provedor)))
    if comparar_prompts:
        for v in ("sumario_v1", "sumario_v2"):
            itens.append(_tentar(f"Comparação de prompts — {v}", "comparacao", "corpus (tipo=noticia)",
                                 lambda v=v: servico.sumarizar_corpus(tipo="noticia", limite=15, provedor=provedor, versao_prompt=v)))
    return {"gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": servico.status(), "itens": itens}


def _uso(r: dict) -> str:
    return (f"`{r.get('provedor')}/{r.get('modelo')}` · prompt `{r.get('versao_prompt')}` · {r.get('n_chamadas')} chamada(s) · "
            f"{r.get('tokens_entrada')} tokens de entrada / {r.get('tokens_saida')} de saída · " + ("do cache" if r.get("cache") else "gerado agora"))


def _fid(f: Optional[dict]) -> str:
    if not f:
        return "_(sem verificação: nenhum trecho foi recuperado, a IA não foi chamada)_"
    return ("✅ números e citações conferem com as fontes" if f["ok"] else
            f"⚠️ REVISAR — números fora das fontes: {f['numeros_nao_encontrados'] or '—'}; citações inválidas: {f['citacoes_invalidas'] or '—'}")


def renderizar_md(ev: dict) -> str:
    st = ev["status"]
    linhas = ["# Evidências de uso da IA online", "",
              f"> Gerado automaticamente em {ev['gerado_em']} por `Scripts/gerar_evidencias_ia.py`, com saídas **reais** do provedor "
              f"(`{st['provedor_padrao']}`) sobre os dados do projeto. Revise antes de usar em decisões: a IA pode errar.", ""]
    comparacao = []
    for it in ev["itens"]:
        linhas += [f"## {it['nome']}", f"*Entrada:* {it['entrada']}", ""]
        if "erro" in it:
            e = it["erro"]
            linhas += [f"❌ **Falhou** — `{e['codigo']}`: {e['mensagem']}", f"💡 {e['sugestao']}" if e.get("sugestao") else "", ""]
            continue
        r = it["resultado"]
        if it["tipo"] in ("sumario_corpus", "sumario_texto", "comparacao"):
            s = r["resumo"]
            linhas += [s["resumo_executivo"], ""]
            if s["pontos_chave"]:
                linhas += ["**Pontos-chave**", *[f"- {p}" for p in s["pontos_chave"]], ""]
            if s["recomendacoes"]:
                linhas += ["**Recomendações**", *[f"- {x['acao']} — {x['justificativa']}" + (f" (ODS {x['ods']})" if x["ods"] else "") for x in s["recomendacoes"]], ""]
            if s["lacunas"]:
                linhas += ["**Lacunas declaradas**", *[f"- {x}" for x in s["lacunas"]], ""]
            if it["tipo"] == "comparacao":
                comparacao.append((r["versao_prompt"], s, r))
        elif it["tipo"] == "pergunta":
            linhas += [f"**Resposta** (confiança {r['confianca']}): {r['resposta']}", "", f"Fontes citadas: {', '.join(r['fontes_citadas']) or '—'}", ""]
        elif it["tipo"] == "insights":
            ins = r["insights"]
            linhas += ["**Destaques**", *[f"- **{d['titulo']}** — {d['detalhe']}" for d in ins["destaques"]], ""]
            if ins["riscos"]:
                linhas += ["**Riscos**", *[f"- ({x['gravidade']}) {x['descricao']}" for x in ins["riscos"]], ""]
            linhas += ["**Recomendações**", *[f"- ({x['prioridade']}) {x['acao']} — {x['justificativa']}" for x in ins["recomendacoes"]], ""]
        linhas += [f"Fidelidade: {_fid(r.get('fidelidade'))}", "", _uso(r) if r.get("provedor") else "", ""]
    if comparacao:
        linhas += ["## Comparação de versões de prompt", "", "| prompt | saída estruturada | pontos-chave | recomendações | lacunas | números verificados | números fora das fontes | tokens (ent/saída) |",
                   "|---|---|---|---|---|---|---|---|"]
        for v, s, r in comparacao:
            f = r["fidelidade"]
            linhas.append(f"| {v} | {'sim' if s['pontos_chave'] or s['recomendacoes'] else 'não (texto livre)'} | {len(s['pontos_chave'])} | {len(s['recomendacoes'])} | "
                          f"{len(s['lacunas'])} | {f['numeros_verificados']} | {len(f['numeros_nao_encontrados'])} | {r['tokens_entrada']}/{r['tokens_saida']} |")
        linhas.append("")
    return "\n".join(linhas)
