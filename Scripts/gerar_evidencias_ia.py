"""
Roda a IA online sobre os dados do projeto e grava as evidências (saídas reais, fidelidade, tokens):
  Docs/Project/Evidencias_IA.md   e   Data/processed/ia/evidencias.json
REQUER chave de API no .env (OPENAI_API_KEY ou ANTHROPIC_API_KEY) e internet. Gera custo no provedor (poucas chamadas).

Uso (a partir da raiz):
    python Scripts/gerar_evidencias_ia.py
    python Scripts/gerar_evidencias_ia.py --provedor anthropic --comparar-prompts
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Code"))
from esg_core import paths  # noqa: E402
from esg_core.env import carregar_dotenv  # noqa: E402
from esg_core.ia.evidencias import coletar_evidencias, renderizar_md  # noqa: E402
from esg_core.ia.servico import ServicoIA  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provedor", choices=["openai", "anthropic"])
    ap.add_argument("--comparar-prompts", action="store_true", help="adiciona 2 chamadas comparando sumario_v1 × v2")
    a = ap.parse_args()
    carregar_dotenv()
    servico = ServicoIA()
    if not servico.status()["algum_configurado"]:
        sys.exit("Nenhuma chave de IA configurada. Copie .env.example para .env e defina OPENAI_API_KEY (ou ANTHROPIC_API_KEY).")
    print("Gerando evidências (cada item é uma chamada ao provedor; respostas idênticas vêm do cache)...")
    ev = coletar_evidencias(servico, a.comparar_prompts, a.provedor)
    paths.caminho_ia_dir().mkdir(parents=True, exist_ok=True)
    (paths.caminho_ia_dir() / "evidencias.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
    destino = RAIZ / "Docs" / "Project" / "Evidencias_IA.md"
    destino.write_text(renderizar_md(ev), encoding="utf-8")
    falhas = [i["nome"] for i in ev["itens"] if "erro" in i]
    print(f"OK: {destino}  ({len(ev['itens']) - len(falhas)} de {len(ev['itens'])} itens gerados)")
    for nome in falhas:
        print(f"  ✗ {nome}")
    sys.exit(1 if falhas else 0)
