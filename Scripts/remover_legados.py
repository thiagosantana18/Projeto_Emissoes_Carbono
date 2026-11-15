"""
Remove arquivos de versões anteriores do projeto que contradizem a estrutura atual.

Por que existe: extrair um .zip novo por cima de uma pasta de projeto existente NÃO apaga os arquivos
que foram removidos na versão nova — eles ficam como "lixo" e confundem (ex.: um README antigo
descrevendo um módulo que não existe mais).

Uso (a partir da raiz do projeto):
    python Scripts/remover_legados.py             # só LISTA o que seria removido (nada é apagado)
    python Scripts/remover_legados.py --executar  # remove

Remove: App/dashboard/README_app.md e Code/genai_reporting/ (apenas se contiver só README.md).
Apenas AVISA (nunca apaga) sobre suspeitos: app.py/README_demo.md na raiz e pastas pages/ em App/dashboard.
"""
import argparse
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVOS_LEGADOS = ["App/dashboard/README_app.md"]
PASTAS_LEGADAS = ["Code/genai_reporting"]          # substituída por Code/llm + Code/esg_core/llm
SUSPEITOS = ["app.py", "README_demo.md", "App/dashboard/pages"]


def listar(raiz: Path) -> dict:
    remover, bloqueados, suspeitos = [], [], []
    for rel in ARQUIVOS_LEGADOS:
        if (raiz / rel).is_file():
            remover.append(rel)
    for rel in PASTAS_LEGADAS:
        pasta = raiz / rel
        if pasta.is_dir():
            outros = [f for f in pasta.rglob("*") if f.is_file() and f.name != "README.md"]
            (bloqueados if outros else remover).append(rel)
    suspeitos = [rel for rel in SUSPEITOS if (raiz / rel).exists()]
    return {"remover": remover, "bloqueados": bloqueados, "suspeitos": suspeitos}


def remover(raiz: Path, itens: list) -> None:
    for rel in itens:
        alvo = raiz / rel
        shutil.rmtree(alvo) if alvo.is_dir() else alvo.unlink()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--executar", action="store_true", help="apaga de verdade (sem isso, só lista)")
    a = ap.parse_args()
    r = listar(RAIZ)
    if not (r["remover"] or r["bloqueados"] or r["suspeitos"]):
        print("Nenhum legado encontrado. Projeto limpo.")
    for rel in r["remover"]:
        print(("REMOVENDO  " if a.executar else "seria removido: ") + rel)
    for rel in r["bloqueados"]:
        print(f"NÃO REMOVIDO (contém arquivos além de README.md; verifique manualmente): {rel}")
    for rel in r["suspeitos"]:
        print(f"ATENÇÃO (provável versão antiga; confira e apague à mão se for o caso): {rel}")
    if a.executar:
        remover(RAIZ, r["remover"])
        print("Concluído.")
    elif r["remover"]:
        print("\nNada foi apagado. Rode com --executar para remover.")
