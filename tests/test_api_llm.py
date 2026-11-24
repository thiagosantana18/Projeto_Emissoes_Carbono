"""Testes das rotas de LLM e do tratamento de erros. Exigem fastapi + httpx (requirements-dev.txt); senão são pulados.
Usam um serviço com pipeline FALSO injetado via dependency_overrides: nada é baixado."""
import os
import tempfile
import time
import unittest
from pathlib import Path

import _setup  # noqa: F401

try:
    from fastapi.testclient import TestClient
    HAS_API = True
except Exception:  # noqa: BLE001
    HAS_API = False

from esg_core.llm.config import ConfigLLM
from esg_core.llm.sentimento import ServicoSentimento
from test_llm_service import pipeline_falso


class ServicoQuebrado:
    def analisar(self, texto):
        return 1 / 0


class ServicoRespostaInvalida:
    def analisar(self, texto):
        return {"foo": "bar"}


@unittest.skipUnless(HAS_API, "fastapi/httpx não instalados")
class ApiLLMTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ESG_DATA_DIR"] = self.tmp.name
        from App.api.main import app
        from App.api.routers.llm import get_servico
        self.app, self.get_servico = app, get_servico
        self.client = TestClient(app, raise_server_exceptions=False)
        self.servicos = []

    def tearDown(self):
        self.app.dependency_overrides.clear()
        for s in self.servicos:
            s._executor.shutdown(wait=False)
        os.environ.pop("ESG_DATA_DIR", None)
        self.tmp.cleanup()

    def usar(self, pipe=None, carregador=None, **cfg):
        c = ConfigLLM(pasta_cache=Path(self.tmp.name), **cfg)
        s = ServicoSentimento(c, carregador or (lambda _c: pipe))
        self.servicos.append(s)
        self.app.dependency_overrides[self.get_servico] = lambda: s
        return s

    def assertEnvelope(self, r, status, codigo):
        self.assertEqual(r.status_code, status, r.text)
        j = r.json()
        self.assertEqual(set(j), {"codigo", "mensagem", "detalhes", "sugestao", "request_id"})
        self.assertEqual(j["codigo"], codigo)
        self.assertTrue(j["mensagem"])
        self.assertEqual(j["request_id"], r.headers["X-Request-ID"])
        return j

    # ---- sucesso
    def test_processar_texto_ok(self):
        self.usar(pipeline_falso())
        r = self.client.post("/processar_texto", json={"texto": "Resultado ótimo para a empresa"})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual(j["tipo_analise"], "classificacao_sentimento")
        self.assertEqual(j["resultado"]["rotulo"], "positivo")
        self.assertEqual(set(j["resultado"]["probabilidades"]), {"positivo", "neutro", "negativo"})
        self.assertIn("id", j["modelo"])
        self.assertIn("tempo_inferencia_ms", j["metadados"])
        self.assertIn("X-Request-ID", r.headers)

    def test_lote_ok(self):
        self.usar(pipeline_falso())
        r = self.client.post("/processar_texto/lote", json={"textos": ["ótimo dia", "péssimo dia"]})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual(j["total"], 2)
        self.assertEqual([x["resultado"]["rotulo"] for x in j["resultados"]], ["positivo", "negativo"])
        self.assertEqual([x["indice"] for x in j["resultados"]], [0, 1])

    # ---- 422
    def test_entrada_invalida_422(self):
        self.usar(pipeline_falso(), max_caracteres=50, max_lote=2)
        j = self.assertEnvelope(self.client.post("/processar_texto", json={"texto": "   "}), 422, "DADOS_INVALIDOS")
        self.assertEqual(j["detalhes"][0]["campo"], "texto")
        j = self.assertEnvelope(self.client.post("/processar_texto", json={}), 422, "DADOS_INVALIDOS")
        self.assertIn("obrigatório", j["detalhes"][0]["problema"])
        self.assertEnvelope(self.client.post("/processar_texto", json={"texto": "ok ok", "tarefa": "resumo"}), 422, "DADOS_INVALIDOS")
        r = self.client.post("/processar_texto", content=b"{oops", headers={"Content-Type": "application/json"})
        self.assertEnvelope(r, 422, "DADOS_INVALIDOS")
        self.assertEnvelope(self.client.post("/processar_texto", json={"texto": "12345 !!!"}), 422, "TEXTO_INVALIDO")
        self.assertEnvelope(self.client.post("/processar_texto", json={"texto": "x" * 60}), 422, "TEXTO_INVALIDO")
        self.assertEnvelope(self.client.post("/processar_texto/lote", json={"textos": ["a b", "c d", "e f"]}), 422, "TEXTO_INVALIDO")
        self.assertEnvelope(self.client.post("/processar_texto/lote", json={"textos": []}), 422, "DADOS_INVALIDOS")

    # ---- 503 / 504 / 429 / 500
    def test_modelo_indisponivel_503(self):
        def car(_c):
            raise OSError("sem cache local")
        self.usar(carregador=car)
        j = self.assertEnvelope(self.client.post("/processar_texto", json={"texto": "texto qualquer aqui"}), 503, "MODELO_INDISPONIVEL")
        self.assertTrue(j["sugestao"])
        r2 = self.client.post("/processar_texto", json={"texto": "texto qualquer aqui"})   # dentro do cooldown
        self.assertEqual(r2.status_code, 503)
        self.assertIn("Retry-After", r2.headers)

    def test_timeout_504(self):
        self.usar(pipeline_falso(atraso=0.3), timeout_s=0.05)
        self.assertEnvelope(self.client.post("/processar_texto", json={"texto": "texto lento aqui"}), 504, "TEMPO_LIMITE_EXCEDIDO")
        time.sleep(0.4)

    def test_fila_cheia_429(self):
        self.usar(pipeline_falso(atraso=0.4), timeout_s=0.05, max_pendentes=1)
        self.client.post("/processar_texto", json={"texto": "primeiro texto lento"})
        r = self.client.post("/processar_texto", json={"texto": "segundo texto imediato"})
        self.assertEnvelope(r, 429, "MODELO_OCUPADO")
        self.assertEqual(r.headers["Retry-After"], "5")
        time.sleep(0.5)

    def test_falha_de_inferencia_500(self):
        self.usar(pipeline_falso(erro=RuntimeError("out of memory")))
        j = self.assertEnvelope(self.client.post("/processar_texto", json={"texto": "texto qualquer aqui"}), 500, "FALHA_INFERENCIA")
        self.assertIn("out of memory", j["mensagem"])

    def test_erro_inesperado_nao_vaza_traceback(self):
        self.app.dependency_overrides[self.get_servico] = lambda: ServicoQuebrado()
        r = self.client.post("/processar_texto", json={"texto": "texto qualquer aqui"})
        self.assertEnvelope(r, 500, "ERRO_INTERNO")
        self.assertNotIn("Traceback", r.text)
        self.assertNotIn("ZeroDivisionError", r.text)

    def test_resposta_fora_do_contrato_500(self):
        self.app.dependency_overrides[self.get_servico] = lambda: ServicoRespostaInvalida()
        self.assertEnvelope(self.client.post("/processar_texto", json={"texto": "texto qualquer aqui"}), 500, "RESPOSTA_INVALIDA")

    # ---- status, 404/405, request id
    def test_status_e_carregar(self):
        self.usar(pipeline_falso())
        s = self.client.get("/modelo/status").json()
        self.assertFalse(s["carregado"])
        self.assertIn("limites", s)
        r = self.client.post("/modelo/carregar")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["carregado"])

    def test_carregar_com_falha_503(self):
        def car(_c):
            raise ImportError("No module named 'torch'")
        self.usar(carregador=car)
        self.assertEnvelope(self.client.post("/modelo/carregar"), 503, "MODELO_INDISPONIVEL")

    def test_404_405_no_mesmo_envelope(self):
        self.assertEnvelope(self.client.get("/rota-inexistente"), 404, "NAO_ENCONTRADO")
        self.assertEnvelope(self.client.get("/processar_texto"), 405, "METODO_NAO_PERMITIDO")

    def test_request_id_propagado(self):
        self.usar(pipeline_falso())
        r = self.client.post("/processar_texto", json={"texto": ""}, headers={"X-Request-ID": "abc123"})
        self.assertEqual(r.headers["X-Request-ID"], "abc123")
        self.assertEqual(r.json()["request_id"], "abc123")

    def test_health_inclui_llm(self):
        j = self.client.get("/health").json()
        self.assertIn("dependencias_instaladas", j["llm"])


if __name__ == "__main__":
    unittest.main()
