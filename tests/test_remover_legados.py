import sys
import tempfile
import unittest
from pathlib import Path

import _setup  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Scripts"))
import remover_legados as rl  # noqa: E402


class RemoverLegadosTests(unittest.TestCase):
    def test_lista_remove_e_protege(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            (raiz / "App/dashboard").mkdir(parents=True)
            (raiz / "App/dashboard/README_app.md").write_text("x")
            (raiz / "Code/genai_reporting").mkdir(parents=True)
            (raiz / "Code/genai_reporting/README.md").write_text("x")
            (raiz / "app.py").write_text("x")
            r = rl.listar(raiz)
            self.assertEqual(sorted(r["remover"]), ["App/dashboard/README_app.md", "Code/genai_reporting"])
            self.assertEqual(r["suspeitos"], ["app.py"])
            self.assertTrue((raiz / "app.py").exists())                       # listar não apaga
            rl.remover(raiz, r["remover"])
            self.assertFalse((raiz / "Code/genai_reporting").exists())
            self.assertFalse((raiz / "App/dashboard/README_app.md").exists())
            self.assertTrue((raiz / "app.py").exists())                       # suspeito nunca é apagado
            # pasta com código de verdade é protegida
            (raiz / "Code/genai_reporting").mkdir()
            (raiz / "Code/genai_reporting/meu_codigo.py").write_text("x")
            r2 = rl.listar(raiz)
            self.assertEqual((r2["remover"], r2["bloqueados"]), ([], ["Code/genai_reporting"]))


if __name__ == "__main__":
    unittest.main()
