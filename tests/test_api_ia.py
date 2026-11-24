"""Testes das rotas de IA online, previsão e qualidade. Exigem fastapi + httpx (requirements-dev.txt); senão são pulados.
O serviço de IA é substituído por um com cliente FALSO (dependency_overrides): nenhuma chave nem rede."""
import os
import tempfile
import unittest
from pathlib import Path

import _setup  # noqa: F401
import pandas as pd

try:
    from fastapi.testclient import TestClient
    HAS_API = True
except Exception:  # noqa: BLE001
    HAS_API = False

from esg_core import corpus as corpus_mod, paths
from esg_core.amostra import gerar_amostra_emissoes
from esg_core.ia import errors as E
from esg_core.ia.config import ConfigIA
from esg_core.ia.controle import AuditoriaIA, CacheIA, LimiteUso
from esg_core.ia.servico import ServicoIA
from ia_helpers import ClienteFalso, sumario

TEXTO = "A empresa reduziu 91% das emissões e antecipou a neutralidade climática para 2035. " * 4


@unittest.skipUnless(HAS_API, "fastapi/httpx não instalados")
class ApiIAtests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ESG_DATA_DIR"] = self.tmp.name
        for d in ("raw", "processed", "interim"):
            (Path(self.tmp.name) / d).mkdir()
        gerar_amostra_emissoes().to_csv(paths.caminho_emissoes_base(), index=False)
        pd.DataFrame({"titulo": ["Vivo reduz emissões em 91%"], "data_publicacao": ["2026-05-27"], "tags": ["emissoes"], "url_materia": ["https://x/a/b"],
                      "data_coleta": ["2026-09-16"], "fonte": ["exame.com"]}).to_csv(paths.caminho_noticias(), index=False)
        corpus_mod.salvar_jsonl(corpus_mod.construir_corpus(), paths.caminho_corpus())
        from App.api.main import app
        from App.api.routers.ia import get_servico_ia
        self.app, self.dep = app, get_servico_ia
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        os.environ.pop("ESG_DATA_DIR", None)
        self.tmp.cleanup()

    def usar(self, *respostas, **cfg):
        base = dict(openai_chave="sk-secreta-123456", max_chamadas_hora=100)
        base.update(cfg)
        cli = ClienteFalso(*respostas)
        s = ServicoIA(ConfigIA(**base), fabrica=lambda c, p: cli, cache=CacheIA(paths.caminho_ia_cache_dir()),
                      auditoria=AuditoriaIA(paths.caminho_ia_dir() / "h.jsonl"), limite=LimiteUso(base["max_chamadas_hora"]))
        self.app.dependency_overrides[self.dep] = lambda: s
        return cli

    def envelope(self, r, status, codigo):
        self.assertEqual(r.status_code, status, r.text)
        self.assertEqual(r.json()["codigo"], codigo)
        return r.json()

    def test_status_nao_vaza_chave(self):
        self.usar()
        r = self.client.get("/ia/status")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("sk-secreta", r.text)
        self.assertTrue(r.json()["algum_configurado"])

    def test_sumarizar_ok_cache_e_historico(self):
        ok = sumario("Redução de 91% até 2035 (p1).", fontes=("p1",), recomendacoes=[], riscos_e_oportunidades=[])
        self.usar(ok)
        r = self.client.post("/sumarizar", json={"texto": TEXTO, "nivel": "executivo"})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertTrue(j["fidelidade"]["ok"])
        self.assertEqual((j["metodo"], j["cache"], j["provedor"]), ("direto", False, "openai"))
        self.assertTrue(j["baseline_extrativo"])
        self.assertTrue(self.client.post("/sumarizar", json={"texto": TEXTO}).json()["cache"])
        h = self.client.get("/ia/historico").json()
        self.assertEqual(h["total"], 2)
        self.assertNotIn(TEXTO[:40], str(h))

    def test_validacao_422(self):
        self.usar()
        self.envelope(self.client.post("/sumarizar", json={"texto": "curto"}), 422, "TEXTO_INVALIDO")
        self.envelope(self.client.post("/sumarizar", json={}), 422, "DADOS_INVALIDOS")
        self.envelope(self.client.post("/sumarizar", json={"texto": TEXTO, "nivel": "enorme"}), 422, "DADOS_INVALIDOS")
        self.envelope(self.client.post("/sumarizar", json={"texto": TEXTO, "provedor": "gemini"}), 422, "DADOS_INVALIDOS")
        self.envelope(self.client.post("/perguntar", json={"pergunta": ""}), 422, "DADOS_INVALIDOS")

    def test_erros_do_provedor_viram_status_corretos(self):
        casos = [(E.IACredencialError("x"), 503, "IA_CREDENCIAL_INVALIDA"), (E.IACotaError("x"), 503, "IA_COTA_EXCEDIDA"),
                 (E.IALimiteTaxaError("x", retry_after=9), 429, "IA_LIMITE_TAXA"), (E.IAProvedorError("x"), 502, "IA_PROVEDOR_INDISPONIVEL"),
                 (E.IATempoLimiteError("x"), 504, "IA_TEMPO_LIMITE"), (E.IARespostaInvalidaError("x"), 502, "IA_RESPOSTA_INVALIDA")]
        for exc, status, codigo in casos:
            with self.subTest(codigo):
                self.usar(exc)
                r = self.client.post("/sumarizar", json={"texto": TEXTO + codigo})
                self.envelope(r, status, codigo)
                if status == 429:
                    self.assertEqual(r.headers["Retry-After"], "9")

    def test_sem_chave_503(self):
        s = ServicoIA(ConfigIA(), cache=CacheIA(paths.caminho_ia_cache_dir()), auditoria=AuditoriaIA(paths.caminho_ia_dir() / "h.jsonl"))
        self.app.dependency_overrides[self.dep] = lambda: s
        j = self.envelope(self.client.post("/sumarizar", json={"texto": TEXTO}), 503, "IA_NAO_CONFIGURADA")
        self.assertIn("OPENAI_API_KEY", j["sugestao"])

    def test_limite_local_429(self):
        ok = sumario("Redução de 91% (p1).", fontes=("p1",), recomendacoes=[], riscos_e_oportunidades=[])
        self.usar(ok, max_chamadas_hora=1)
        self.client.post("/sumarizar", json={"texto": TEXTO})
        self.envelope(self.client.post("/sumarizar", json={"texto": TEXTO + " diferente"}), 429, "IA_LIMITE_LOCAL")

    def test_corpus_perguntar_insights(self):
        self.usar(sumario("Vivo: 91% (d1).", fontes=("d1",), recomendacoes=[], riscos_e_oportunidades=[]))
        r = self.client.post("/sumarizar/corpus", json={"tipo": "noticia", "limite": 5})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["fontes"][0]["doc_id"])
        self.envelope(self.client.post("/sumarizar/corpus", json={"tag": "inexistente"}), 404, "DADOS_INDISPONIVEIS")
        self.usar({"resposta": "A Vivo reduziu 91% (d1).", "confianca": "alta", "fontes_citadas": ["d1"], "lacunas": []})
        r = self.client.post("/perguntar", json={"pergunta": "Quanto a Vivo reduziu?"})
        self.assertEqual((r.status_code, r.json()["chamou_llm"], r.json()["confianca"]), (200, True, "alta"))
        r = self.client.post("/perguntar", json={"pergunta": "receita de bolo de cenoura xyz"})
        self.assertEqual((r.json()["chamou_llm"], r.json()["n_chamadas"]), (False, 0))
        self.usar({"destaques": [{"titulo": "Diesel lidera", "detalhe": "ver E1"}], "riscos": [], "recomendacoes": [],
                   "alertas_de_dados": ["sintético"], "fontes_citadas": ["E1"]})
        r = self.client.post("/insights/emissoes", json={"incluir_previsao": True})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("kgCO2e", r.json()["texto_contexto"])

    def test_previsao_e_qualidade(self):
        r = self.client.get("/previsao/emissoes", params={"horizonte": 3})
        self.assertEqual(r.status_code, 200, r.text)
        j = r.json()
        self.assertEqual((len(j["previsoes"]), j["atinge_meta"], j["serie"]["n_meses"]), (3, True, 24))
        self.assertEqual(self.client.get("/previsao/emissoes", params={"horizonte": 99}).status_code, 422)
        q = self.client.get("/qualidade").json()
        self.assertIn("emissoes", q)
        self.assertTrue(q["resumo_verificacoes"])


if __name__ == "__main__":
    unittest.main()
