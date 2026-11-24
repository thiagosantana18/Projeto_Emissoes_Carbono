"""
Code/data_preparation/build_corpus.py

Transforma os dados coletados em artefatos prontos para as tarefas com LLM da
próxima etapa (NENHUM LLM é chamado aqui):

  Data/processed/corpus_llm.jsonl                       corpus unificado e rastreável
  Data/processed/contexto_relatorio.json                agregados numéricos p/ geração de relatórios
  Data/processed/avaliacao/sentimento_gold_template.csv gabarito a rotular manualmente
  Data/processed/avaliacao/qa_gold_template.csv         gabarito de perguntas e respostas

Uso: python Code/data_preparation/build_corpus.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esg_core import corpus, data_access as da, paths  # noqa: E402


def main() -> None:
    docs = corpus.construir_corpus()
    corpus.salvar_jsonl(docs, paths.caminho_corpus())

    contexto = corpus.construir_contexto_relatorio(da.carregar_emissoes())
    paths.caminho_contexto_relatorio().write_text(json.dumps(contexto, ensure_ascii=False, indent=2), encoding="utf-8")

    templates = corpus.gerar_templates_avaliacao(docs, paths.processed_dir() / "avaliacao")

    por_tipo = Counter(d["tipo"] for d in docs)
    print(f"Corpus: {len(docs)} documentos {dict(por_tipo)} -> {paths.caminho_corpus()}")
    print(f"Contexto de relatório: {contexto['n_registros']} registros, {contexto['total_kgco2e']:,.2f} kgCO2e")
    for t in templates:
        print(f"Template de avaliação: {t}")


if __name__ == "__main__":
    main()
