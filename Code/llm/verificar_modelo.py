"""
Diagnóstico de ponta a ponta do modelo local: dependências, cache, carga, latência, memória e 3 frases de teste.
Sai com código 1 se algo falhar. Use depois de baixar o modelo (e sempre que a API devolver 503).

Uso:  python Code/llm/verificar_modelo.py
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esg_core.llm.errors import ErroLLM  # noqa: E402
from esg_core.llm.sentimento import ServicoSentimento, cache_presente, dependencias_instaladas  # noqa: E402

FRASES = [
    "A empresa reduziu as emissões em 40% e foi premiada pelo desempenho ambiental.",
    "O relatório trata das regras de divulgação de emissões de carbono para companhias abertas.",
    "Vazamento de óleo causa grave dano ambiental e a empresa é multada.",
]


def rss_mb():
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2
    except ImportError:
        return None


def main() -> int:
    servico = ServicoSentimento()
    cfg = servico.config
    print(f"Modelo: {cfg.modelo_id}\nCache:  {cfg.pasta_cache}  (offline={cfg.offline}, dispositivo={cfg.dispositivo})")
    print(f"Dependências (torch + transformers): {'OK' if dependencias_instaladas() else 'AUSENTES'}")
    print(f"Arquivos do modelo no cache: {'sim' if cache_presente(cfg) else 'não'}")
    antes = rss_mb()
    try:
        t0 = time.perf_counter()
        servico.carregar()
        print(f"Carga: {time.perf_counter() - t0:.1f} s")
        depois = rss_mb()
        if antes and depois:
            print(f"Memória do processo: {antes:.0f} MB -> {depois:.0f} MB (+{depois - antes:.0f} MB)")
        for frase in FRASES:
            r = servico.analisar(frase)
            res = r["resultado"]
            print(f"- {res['rotulo']:9s} ({res['confianca']:.2f}) {r['metadados']['tempo_inferencia_ms']:7.1f} ms | {frase[:60]}")
    except ErroLLM as exc:
        print(f"\n[FALHA] {exc.codigo}: {exc.mensagem}")
        if exc.sugestao:
            print(f"Sugestão: {exc.sugestao}")
        return 1
    print("\nTudo certo: o modelo está funcionando localmente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
