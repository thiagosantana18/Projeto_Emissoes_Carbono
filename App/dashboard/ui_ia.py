"""Componentes de interface compartilhados pelas páginas de IA: erros, seletor de provedor e exibição de resultados estruturados."""
from __future__ import annotations

import json
from typing import Optional

import pandas as pd
import streamlit as st

import api_client

ROTULO_PADRAO = "(padrão do servidor)"
ICONE_GRAV = {"alta": "🔴", "media": "🟡", "baixa": "🟢"}


def mostrar_erro(exc: Exception) -> None:
    """Traduz falhas da API em mensagens claras, com a ação sugerida."""
    if isinstance(exc, api_client.ApiIndisponivel):
        st.error(str(exc))
        st.code("uvicorn App.api.main:app --reload      # a partir da raiz do projeto", language="bash")
        return
    if not isinstance(exc, api_client.ApiErro):
        st.error(f"Erro inesperado: {type(exc).__name__}: {exc}")
        return
    titulos = {404: "Dados indisponíveis", 422: "Entrada inválida", 429: "Limite atingido", 500: "Falha no processamento",
               502: "Problema com o provedor de IA", 503: "Serviço indisponível", 504: "Tempo limite excedido"}
    texto = f"**{titulos.get(exc.status, 'Erro da API')}** ({exc.codigo}) — {exc.mensagem}"
    (st.warning if exc.status in (404, 429, 504) else st.error)(texto)
    for d in exc.detalhes:
        st.write(f"- `{d.get('campo') or 'corpo'}`: {d.get('problema')}")
    if exc.sugestao:
        st.info(f"💡 {exc.sugestao}")
    if exc.retry_after:
        st.caption(f"Tente novamente em ~{exc.retry_after} s.")


def status_e_provedor(base: str, chave: str = "ia_provedor") -> tuple:
    """Mostra o estado da IA online e devolve (status|None, provedor escolhido|None). None = usar o padrão do servidor."""
    try:
        status = api_client.status_ia(base)
    except Exception as exc:  # noqa: BLE001
        mostrar_erro(exc)
        return None, None
    configurados = [p["nome"] for p in status["provedores"] if p["configurado"]]
    if not configurados:
        st.warning("Nenhum provedor de IA online está configurado no servidor. Defina `OPENAI_API_KEY` (ou `ANTHROPIC_API_KEY`) no arquivo `.env` "
                   "e reinicie a API. Respostas já geradas e guardadas em cache ainda podem ser exibidas.")
    opcoes = [ROTULO_PADRAO] + configurados
    if st.session_state.get(chave) not in opcoes:
        st.session_state[chave] = ROTULO_PADRAO
    escolha = st.selectbox("Provedor de IA", opcoes, key=chave,
                           help="O padrão é definido por ESG_IA_PROVIDER no servidor. A chave nunca passa pelo navegador.")
    modelos = {p["nome"]: p["modelo"] for p in status["provedores"]}
    st.caption(f"Modelo: `{modelos.get(escolha if escolha != ROTULO_PADRAO else status['provedor_padrao'])}` · "
               f"chamadas na última hora: {status['chamadas_ultima_hora']}/{int(status['limites']['max_chamadas_hora'])} · cache {'ligado' if status['cache_ativo'] else 'desligado'}")
    return status, (None if escolha == ROTULO_PADRAO else escolha)


def render_fidelidade(f: Optional[dict]) -> None:
    if not f:
        return
    if f["ok"]:
        st.success(f"✅ Fidelidade: {f['numeros_verificados']} número(s) verificado(s); todos e todas as citações conferem com as fontes.")
    else:
        st.warning("⚠️ **Confira antes de usar.** " + f["observacao"])
        if f["numeros_nao_encontrados"]:
            st.write("Números que não constam nas fontes: " + ", ".join(f"`{n}`" for n in f["numeros_nao_encontrados"]))
        if f["citacoes_invalidas"]:
            st.write("Citações inexistentes: " + ", ".join(f"`{c}`" for c in f["citacoes_invalidas"]))


def render_uso(r: dict) -> None:
    partes = [f"{r.get('provedor')}/{r.get('modelo')}", f"prompt `{r.get('versao_prompt')}`"]
    if r.get("metodo"):
        partes.append(f"método {r['metodo']} ({r.get('n_lotes', 1)} lote(s))")
    partes.append(f"{r.get('n_chamadas', 0)} chamada(s)")
    if r.get("tokens_entrada") is not None:
        partes.append(f"{r['tokens_entrada']} tokens de entrada / {r.get('tokens_saida')} de saída")
    if r.get("latencia_ms"):
        partes.append(f"{r['latencia_ms'] / 1000:.1f} s")
    partes.append("♻️ resposta do cache (sem nova cobrança)" if r.get("cache") else "🆕 gerada agora")
    st.caption(" · ".join(partes))


def sumario_para_markdown(r: dict) -> str:
    s = r["resumo"]
    linhas = ["# Resumo gerado por IA", "", s["resumo_executivo"], "", "## Pontos-chave", *[f"- {p}" for p in s["pontos_chave"]], ""]
    if s["riscos_e_oportunidades"]:
        linhas += ["## Riscos e oportunidades", *[f"- **{x['tipo']}**: {x['descricao']} ({', '.join(x['fontes'])})" for x in s["riscos_e_oportunidades"]], ""]
    if s["recomendacoes"]:
        linhas += ["## Recomendações", *[f"- {x['acao']} — {x['justificativa']}" + (f" (ODS {x['ods']})" if x["ods"] else "") for x in s["recomendacoes"]], ""]
    if s["lacunas"]:
        linhas += ["## Lacunas", *[f"- {x}" for x in s["lacunas"]], ""]
    linhas += ["## Fontes", *[f"- {f['id']}: {f.get('titulo') or ''} — {f.get('url') or f.get('fonte') or ''}" for f in r["fontes"]], "",
               f"_Gerado com {r['provedor']}/{r['modelo']}, prompt {r['versao_prompt']}. Fidelidade: {'ok' if r['fidelidade']['ok'] else 'REVISAR'}._"]
    return "\n".join(linhas)


def render_sumario(r: dict) -> None:
    s = r["resumo"]
    st.markdown("#### Resumo executivo")
    st.info(s["resumo_executivo"])
    if s["pontos_chave"]:
        st.markdown("**Pontos-chave**")
        for p in s["pontos_chave"]:
            st.markdown(f"- {p}")
    if s["riscos_e_oportunidades"]:
        st.markdown("**Riscos e oportunidades**")
        st.dataframe(pd.DataFrame([{"tipo": ("⚠️ " if x["tipo"] == "risco" else "🌱 " if x["tipo"] == "oportunidade" else "") + x["tipo"],
                                    "descrição": x["descricao"], "fontes": ", ".join(x["fontes"])} for x in s["riscos_e_oportunidades"]]), hide_index=True)
    if s["recomendacoes"]:
        st.markdown("**Recomendações**")
        for x in s["recomendacoes"]:
            st.markdown(f"- **{x['acao']}** — {x['justificativa']}" + (f"  `ODS {x['ods']}`" if x["ods"] else ""))
    if s["lacunas"]:
        with st.expander("O que os documentos NÃO permitem concluir"):
            for x in s["lacunas"]:
                st.markdown(f"- {x}")
    render_fidelidade(r["fidelidade"])
    citadas = set(s["fontes_citadas"])
    with st.expander(f"Fontes ({len(r['fontes'])} documento(s); {len(citadas)} citado(s))"):
        st.dataframe(pd.DataFrame([{"id": f["id"], "citada": "✔" if f["id"] in citadas else "", "título": f.get("titulo"), "fonte": f.get("fonte"),
                                    "data": f.get("data"), "url": f.get("url")} for f in r["fontes"]]), hide_index=True,
                     column_config={"url": st.column_config.LinkColumn("URL")})
    if r.get("baseline_extrativo"):
        with st.expander("Comparação: resumo extrativo SEM IA (linha de base)"):
            st.caption("Escolhe as frases mais representativas por frequência de termos. Serve para avaliar o que o LLM acrescenta.")
            for f in r["baseline_extrativo"]:
                st.markdown(f"- {f}")
    render_uso(r)
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Baixar resumo (Markdown)", sumario_para_markdown(r).encode("utf-8"), file_name="resumo_ia.md", mime="text/markdown")
    c2.download_button("⬇️ Baixar resposta completa (JSON)", json.dumps(r, ensure_ascii=False, indent=2).encode("utf-8"),
                       file_name="resumo_ia.json", mime="application/json")
