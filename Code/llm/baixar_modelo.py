"""
Baixa o modelo de sentimento para o cache local (Models/hf_cache). Execute UMA vez, com internet.
Depois disso a API roda 100% offline.

Uso:  python Code/llm/baixar_modelo.py
Requer: pip install -r requirements-llm.txt
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esg_core.llm.config import carregar_config  # noqa: E402
from esg_core.llm.download import baixar_modelo  # noqa: E402

if __name__ == "__main__":
    cfg = carregar_config()
    print(f"Baixando '{cfg.modelo_id}' para {cfg.pasta_cache} (tamanho aproximado: 0,5 GB)...")
    try:
        info = baixar_modelo(cfg)
    except ImportError as exc:
        sys.exit(f"Dependências ausentes ({exc}). Instale: pip install -r requirements-llm.txt")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Falha no download: {type(exc).__name__}: {exc}\nConfira a conexão e o espaço em disco.")
    print(f"OK: {info['tamanho_mb']} MB em {info['pasta']} ({info['tempo_s']} s).")
    print("Próximo passo: python Code/llm/verificar_modelo.py")
