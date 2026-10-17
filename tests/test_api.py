"""Testes das rotas FastAPI. Rodam apenas se fastapi + httpx estiverem instalados (requirements-dev.txt)."""
import os
import tempfile
import unittest
from pathlib import Path

import _setup  # noqa: F401

try:
    from fastapi.testclient import TestClient
    HAS_API = True
except Exception:  # noqa: BLE001
    HAS_API = False

PAYLOAD = {"mes_referencia": "2026-10", "unidade": "Matriz - SP", "setor": "Administrativo",
           "tipo_atividade": "Eletricidade (rede)", "quantidade": 8500.0, "unidade_medida": "kWh",
           "fator_emissao_kgco2e": 0.0817, "fonte_fator": "Climatiq API"}


@unittest.skipUnless(HAS_API, "fastapi/httpx não instalados")
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ESG_DATA_DIR"] = self.tmp.name
        for d in ("raw", "processed"):
            (Path(self.tmp.name) / d).mkdir()
        from esg_core import paths
        from esg_core.amostra import gerar_amostra_emissoes
        gerar_amostra_emissoes().to_csv(paths.caminho_emissoes_base(), index=False)
        from App.api.main import app
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop("ESG_DATA_DIR", None)
        self.tmp.cleanup()

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")
        self.assertTrue(r.json()["arquivos"]["emissoes_base"])

    def test_get_emissoes_filtros_e_paginacao(self):
        r = self.client.get("/emissoes", params={"unidade": "Filial - RJ", "limit": 5})
        j = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(j["itens"]), 5)
        self.assertEqual(j["total"], 24 * 2)
        self.assertEqual(self.client.get("/emissoes", params={"limit": 0}).status_code, 422)
        self.assertEqual(self.client.get("/emissoes", params={"mes_inicio": "2026-13"}).status_code, 422)

    def test_post_calcula_emissao_e_persiste(self):
        r = self.client.post("/emissoes", json=PAYLOAD)
        self.assertEqual(r.status_code, 201)
        self.assertAlmostEqual(r.json()["emissao_kgco2e"], 694.45, places=2)
        self.assertEqual(r.json()["origem"], "api")
        g = self.client.get("/emissoes", params={"origem": "api"}).json()
        self.assertEqual(g["total"], 1)

    def test_post_invalidos(self):
        self.assertEqual(self.client.post("/emissoes", json={**PAYLOAD, "mes_referencia": "2026-1"}).status_code, 422)
        self.assertEqual(self.client.post("/emissoes", json={**PAYLOAD, "quantidade": 0}).status_code, 422)
        self.assertEqual(self.client.post("/emissoes", json={**PAYLOAD, "emissao_kgco2e": 5000}).status_code, 422)

    def test_lote_e_resumo(self):
        r = self.client.post("/emissoes/lote", json=[PAYLOAD, PAYLOAD])
        self.assertEqual(r.json(), {"inseridos": 2})
        self.assertEqual(self.client.post("/emissoes/lote", json=[]).status_code, 422)
        res = self.client.get("/emissoes/resumo").json()
        self.assertEqual(res["n_registros"], 216 + 2)

    def test_corpus_ausente_retorna_404(self):
        self.assertEqual(self.client.get("/corpus").status_code, 404)
        self.assertEqual(self.client.get("/noticias").json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
