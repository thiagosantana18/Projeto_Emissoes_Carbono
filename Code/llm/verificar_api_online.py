"""
Teste mínimo da IA online: faz UMA chamada pequena ao provedor configurado e confere se a resposta é um JSON válido.
Use depois de colocar a chave no .env e sempre que a API devolver erros IA_*. Custo: uma chamada com poucos tokens.

Uso:  python Code/llm/verificar_api_online.py [--provedor openai|anthropic]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from esg_core.env import carregar_dotenv  # noqa: E402
from esg_core.ia.config import carregar_config_ia  # noqa: E402
from esg_core.ia.provedores import criar_cliente  # noqa: E402
from esg_core.ia.sumarizacao import chamar_json  # noqa: E402
from esg_core.llm.errors import ErroLLM  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provedor", choices=["openai", "anthropic"])
    a = ap.parse_args()
    n = carregar_dotenv()
    cfg = carregar_config_ia()
    prov = cfg.provedor_efetivo(a.provedor)
    print(f".env: {n} variável(is) carregada(s) | provedor: {prov} | modelo: {cfg.modelo(prov)} | configurado: {'sim' if cfg.configurado(prov) else 'NÃO'}")
    try:
        cliente = criar_cliente(cfg, a.provedor)
        dado, respostas = chamar_json(cliente, "Responda apenas com um objeto JSON válido.", 'Responda com {"ok": true, "mensagem": "olá"}', max_tokens=cfg.max_tokens)
    except ErroLLM as exc:
        print(f"\n[FALHA] {exc.codigo}: {exc.mensagem}")
        if exc.sugestao:
            print(f"Sugestão: {exc.sugestao}")
        sys.exit(1)
    r = respostas[-1]
    print(f"Resposta: {dado}\nLatência: {r.latencia_ms:.0f} ms | tokens: {r.tokens_entrada} entrada / {r.tokens_saida} saída | tentativas: {r.tentativas}")
    print("\nTudo certo: a IA online está funcionando.")
