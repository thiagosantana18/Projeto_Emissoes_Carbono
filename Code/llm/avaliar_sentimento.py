"""
Sentimento sobre o corpus de notícias: gera previsões e (opcionalmente) avalia contra o gabarito humano.

  python Code/llm/avaliar_sentimento.py prever    -> Data/processed/sentimento_noticias.csv
  python Code/llm/avaliar_sentimento.py avaliar   -> compara com Data/processed/avaliacao/sentimento_gold_template.csv
                                                     (preencha a coluna rotulo_humano: positivo | neutro | negativo)
Usa o serviço local diretamente (a API não precisa estar no ar).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esg_core import data_access as da, paths  # noqa: E402
from esg_core.llm import avaliacao  # noqa: E402
from esg_core.llm.errors import ErroLLM  # noqa: E402
from esg_core.llm.sentimento import ServicoSentimento  # noqa: E402

SAIDA = paths.processed_dir() / "sentimento_noticias.csv"
GABARITO = paths.processed_dir() / "avaliacao" / "sentimento_gold_template.csv"


def prever(servico: ServicoSentimento) -> list:
    docs = [d for d in da.carregar_corpus() if d["tipo"] == "noticia"]
    if not docs:
        sys.exit("Corpus de notícias vazio. Rode: python Code/data_preparation/build_corpus.py")
    linhas = []
    lote = servico.config.max_lote
    for i in range(0, len(docs), lote):
        parte = docs[i:i + lote]
        for d, r in zip(parte, servico.analisar_lote([d["texto"] for d in parte])):
            p = r["resultado"]["probabilidades"]
            linhas.append({"doc_id": d["doc_id"], "titulo": d["titulo"], "rotulo_previsto": r["resultado"]["rotulo"],
                           "confianca": r["resultado"]["confianca"], "p_positivo": p["positivo"], "p_neutro": p["neutro"],
                           "p_negativo": p["negativo"], "modelo": r["modelo"]["id"]})
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    print(f"OK: {len(linhas)} previsões em {SAIDA}")
    return linhas


def avaliar(servico: ServicoSentimento) -> None:
    if not GABARITO.is_file():
        sys.exit(f"Gabarito não encontrado: {GABARITO}")
    gold, avisos = avaliacao.carregar_gabarito(GABARITO)
    for a in avisos:
        print("[AVISO]", a)
    if not gold:
        sys.exit("Nenhuma linha rotulada. Preencha 'rotulo_humano' (positivo | neutro | negativo) no gabarito.")
    previstos, lote = [], servico.config.max_lote
    for i in range(0, len(gold), lote):
        previstos += [r["resultado"]["rotulo"] for r in servico.analisar_lote([g["titulo"] for g in gold[i:i + lote]])]
    m = avaliacao.metricas([g["rotulo_humano"] for g in gold], previstos)
    print(json.dumps(m, ensure_ascii=False, indent=2))
    print(f"\nAcurácia: {m['acuracia']:.1%} | F1 macro: {m['f1_macro']:.3f} | n = {m['n']}")
    if m["n"] < 50:
        print("Atenção: menos de 50 itens rotulados — a estimativa é pouco confiável.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=["prever", "avaliar"])
    acao = ap.parse_args().acao
    try:
        (prever if acao == "prever" else avaliar)(ServicoSentimento())
    except ErroLLM as exc:
        sys.exit(f"[{exc.codigo}] {exc.mensagem}\nSugestão: {exc.sugestao or '-'}")
