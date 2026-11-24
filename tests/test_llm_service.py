"""Testes do serviço de LLM local com pipelines FALSOS (nada é baixado; roda sem torch/transformers)."""
import csv
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import _setup  # noqa: F401

from esg_core.erros_http import detalhes_de_validacao, montar_erro, traduzir_erro_validacao
from esg_core.llm import avaliacao
from esg_core.llm.config import MODELO_PADRAO, ConfigLLM, carregar_config
from esg_core.llm.errors import (FalhaInferenciaError, ModeloIndisponivelError, ModeloOcupadoError,
                                 TempoLimiteError, TextoInvalidoError)
from esg_core.llm.sentimento import (ServicoSentimento, converter_scores, normalizar_saida_pipeline,
                                     normalizar_texto)


def scores(pos, neu, neg):
    return [{"label": "positive", "score": pos}, {"label": "neutral", "score": neu}, {"label": "negative", "score": neg}]


def pipeline_falso(formato="listas", atraso=0.0, erro=None, saida=None, tokenizer=None):
    chamadas = []

    def pipe(textos, **kw):
        chamadas.append((list(textos), kw))
        if atraso:
            time.sleep(atraso)
        if erro:
            raise erro
        if saida is not None:
            return saida
        res = []
        for t in textos:
            s = scores(0.8, 0.15, 0.05) if "ótimo" in t else scores(0.05, 0.15, 0.8) if "péssimo" in t else scores(0.1, 0.8, 0.1)
            res.append(s)
        if formato == "lista_de_dicts" and len(textos) == 1:
            return res[0]
        return res

    pipe.chamadas, pipe.device = chamadas, "cpu"
    if tokenizer is not None:
        pipe.tokenizer = tokenizer
    return pipe


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.servicos = []

    def tearDown(self):
        for s in self.servicos:
            s._executor.shutdown(wait=False)
        self._tmp.cleanup()

    def servico(self, pipe=None, carregador=None, relogio=time.monotonic, **cfg):
        c = ConfigLLM(pasta_cache=Path(self._tmp.name), **cfg)
        self.carregamentos = []

        def car(_cfg):
            self.carregamentos.append(1)
            return pipe

        s = ServicoSentimento(c, carregador or car, relogio)
        self.servicos.append(s)
        return s


class AnaliseTests(Base):
    def test_resposta_estruturada(self):
        pipe = pipeline_falso()
        r = self.servico(pipe).analisar("  Resultado   ótimo \n para a empresa ")
        self.assertEqual(r["texto_processado"], "Resultado ótimo para a empresa")
        self.assertEqual(r["texto_original"], "  Resultado   ótimo \n para a empresa ")
        self.assertEqual(r["tipo_analise"], "classificacao_sentimento")
        self.assertEqual(r["resultado"]["rotulo"], "positivo")
        self.assertEqual(r["resultado"]["confianca"], 0.8)
        self.assertEqual(set(r["resultado"]["probabilidades"]), {"positivo", "neutro", "negativo"})
        self.assertEqual(r["modelo"]["id"], MODELO_PADRAO)
        self.assertEqual(r["metadados"]["n_caracteres"], len("Resultado ótimo para a empresa"))
        self.assertFalse(r["metadados"]["truncado"])
        _, kw = pipe.chamadas[0]
        self.assertIsNone(kw["top_k"])
        self.assertTrue(kw["truncation"])
        self.assertEqual(kw["max_length"], 256)

    def test_formatos_de_saida_do_pipeline(self):
        r = self.servico(pipeline_falso("lista_de_dicts")).analisar("texto péssimo aqui")
        self.assertEqual(r["resultado"]["rotulo"], "negativo")
        self.assertEqual(normalizar_saida_pipeline(scores(1, 0, 0), 1), [scores(1, 0, 0)])
        self.assertEqual(len(normalizar_saida_pipeline([scores(1, 0, 0), scores(0, 1, 0)], 2)), 2)

    def test_lote_mantem_ordem_e_carrega_uma_vez(self):
        s = self.servico(pipeline_falso())
        out = s.analisar_lote(["ótimo dia", "péssimo dia", "dia comum"])
        self.assertEqual([o["resultado"]["rotulo"] for o in out], ["positivo", "negativo", "neutro"])
        s.analisar("outro texto")
        self.assertEqual(len(self.carregamentos), 1)

    def test_tokens_e_truncamento(self):
        tok = lambda t, **k: {"input_ids": list(range(300))}  # noqa: E731
        r = self.servico(pipeline_falso(tokenizer=tok)).analisar("texto qualquer")
        self.assertEqual(r["metadados"]["n_tokens"], 300)
        self.assertTrue(r["metadados"]["truncado"])


class ValidacaoTests(Base):
    def test_entradas_invalidas_nao_carregam_o_modelo(self):
        s = self.servico(pipeline_falso(), max_caracteres=50, max_lote=2)
        casos = ["", "   \n\t ", "12345 !!!", "x" * 51, None, 123]
        for texto in casos:
            with self.assertRaises(TextoInvalidoError, msg=repr(texto)) as cm:
                s.analisar(texto)
            self.assertEqual(cm.exception.status_code, 422)
            self.assertEqual(cm.exception.detalhes[0]["campo"], "texto")
        with self.assertRaises(TextoInvalidoError):
            s.analisar_lote([])
        with self.assertRaises(TextoInvalidoError) as cm:
            s.analisar_lote(["a b", "c d", "e f"])
        self.assertIn("Máximo de 2", cm.exception.mensagem)
        with self.assertRaises(TextoInvalidoError) as cm:
            s.analisar_lote(["texto ok", ""])
        self.assertEqual(cm.exception.detalhes[0]["campo"], "textos[1]")
        self.assertEqual(self.carregamentos, [])            # validou ANTES de carregar o modelo

    def test_saida_invalida_do_modelo(self):
        casos = {
            "rótulo desconhecido": [[{"label": "alegria", "score": 1.0}]],
            "faltam rótulos": [[{"label": "positive", "score": 1.0}]],
            "soma errada": [scores(0.9, 0.9, 0.9)],
            "score fora de [0,1]": [scores(1.5, -0.3, -0.2)],
            "nan": [scores(float("nan"), 0.5, 0.5)],
            "quantidade errada": [scores(1, 0, 0), scores(1, 0, 0)],
        }
        for nome, saida in casos.items():
            with self.subTest(nome):
                with self.assertRaises(FalhaInferenciaError) as cm:
                    self.servico(pipeline_falso(saida=saida)).analisar("texto válido aqui")
                self.assertEqual(cm.exception.status_code, 500)

    def test_converter_scores_renormaliza(self):
        c = converter_scores(scores(0.5, 0.25, 0.2501))
        self.assertAlmostEqual(sum(c["probabilidades"].values()), 1.0, delta=0.001)
        self.assertEqual(c["rotulo"], "positivo")


class CargaTests(Base):
    def test_dependencias_ausentes(self):
        def car(_):
            raise ImportError("No module named 'torch'")
        with mock.patch("esg_core.llm.sentimento.dependencias_instaladas", return_value=False):
            with self.assertRaises(ModeloIndisponivelError) as cm:
                self.servico(carregador=car).analisar("texto qualquer")
        self.assertEqual(cm.exception.status_code, 503)
        self.assertIn("requirements-llm", cm.exception.sugestao)

    def test_modelo_nao_baixado_sugere_download(self):
        def car(_):
            raise OSError("We couldn't connect to 'https://huggingface.co'")
        with mock.patch("esg_core.llm.sentimento.dependencias_instaladas", return_value=True):
            with self.assertRaises(ModeloIndisponivelError) as cm:
                self.servico(carregador=car).analisar("texto qualquer")
        self.assertIn(MODELO_PADRAO, cm.exception.mensagem)
        self.assertIn("baixar_modelo.py", cm.exception.sugestao)

    def test_cooldown_e_forcar(self):
        t = [0.0]
        chamadas = []

        def car(_):
            chamadas.append(1)
            if len(chamadas) == 1:
                raise OSError("falha")
            return pipeline_falso()

        s = self.servico(carregador=car, relogio=lambda: t[0], cooldown_falha_s=30)
        with self.assertRaises(ModeloIndisponivelError):
            s.analisar("primeira tentativa")
        with self.assertRaises(ModeloIndisponivelError) as cm:         # dentro do cooldown: não tenta de novo
            s.analisar("segunda tentativa")
        self.assertEqual(len(chamadas), 1)
        self.assertGreaterEqual(cm.exception.retry_after, 1)
        self.assertIsNotNone(s.status()["ultimo_erro"])
        t[0] = 31.0                                                     # cooldown expirou
        self.assertEqual(s.analisar("terceira tentativa")["resultado"]["rotulo"], "neutro")
        self.assertEqual(len(chamadas), 2)
        self.assertIsNone(s.status()["ultimo_erro"])

    def test_forcar_ignora_cooldown(self):
        chamadas = []

        def car(_):
            chamadas.append(1)
            if len(chamadas) == 1:
                raise OSError("falha")
            return pipeline_falso()

        s = self.servico(carregador=car)
        with self.assertRaises(ModeloIndisponivelError):
            s.carregar()
        s.carregar(forcar=True)
        self.assertTrue(s.esta_carregado())

    def test_carga_concorrente_acontece_uma_vez(self):
        def car(_):
            self.carregamentos.append(1)
            time.sleep(0.1)
            return pipeline_falso()
        s = self.servico(carregador=car)
        ts = [threading.Thread(target=s.carregar) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len(self.carregamentos), 1)


class RobustezTests(Base):
    def test_timeout_e_recuperacao(self):
        s = self.servico(pipeline_falso(atraso=0.3), timeout_s=0.05)
        with self.assertRaises(TempoLimiteError) as cm:
            s.analisar("texto demorado aqui")
        self.assertEqual(cm.exception.status_code, 504)
        time.sleep(0.4)                                                  # a inferência presa termina
        s._cfg = ConfigLLM(pasta_cache=Path(self._tmp.name), timeout_s=5)   # sem timeout apertado
        self.assertIn("rotulo", s.analisar("outro texto agora")["resultado"])

    def test_fila_cheia_devolve_ocupado(self):
        s = self.servico(pipeline_falso(atraso=0.4), timeout_s=0.05, max_pendentes=1)
        with self.assertRaises(TempoLimiteError):
            s.analisar("primeiro texto lento")
        with self.assertRaises(ModeloOcupadoError) as cm:
            s.analisar("segundo texto imediato")
        self.assertEqual((cm.exception.status_code, cm.exception.retry_after), (429, 5))
        time.sleep(0.5)
        s._cfg = ConfigLLM(pasta_cache=Path(self._tmp.name), timeout_s=5, max_pendentes=1)
        self.assertIn("resultado", s.analisar("terceiro texto depois"))

    def test_erro_na_inferencia(self):
        s = self.servico(pipeline_falso(erro=RuntimeError("out of memory")))
        with self.assertRaises(FalhaInferenciaError) as cm:
            s.analisar("texto qualquer aqui")
        self.assertIn("RuntimeError", cm.exception.mensagem)
        self.assertIn("out of memory", cm.exception.mensagem)

    def test_status_e_contadores(self):
        s = self.servico(pipeline_falso())
        st = s.status()
        self.assertFalse(st["carregado"])
        self.assertTrue(st["offline"])
        self.assertEqual(st["limites"]["max_lote"], 32)
        s.analisar("ótimo texto aqui")
        with self.assertRaises(TextoInvalidoError):
            s.analisar("")
        st = s.status()
        self.assertTrue(st["carregado"])
        self.assertEqual((st["total_requisicoes"], st["total_erros"]), (2, 1))
        self.assertIsNotNone(st["tempo_carga_s"])
        self.assertEqual(st["dispositivo"], "cpu")


class ConfigEHelpersTests(unittest.TestCase):
    def test_config_padrao_e_env(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in [k for k in os.environ if k.startswith("ESG_LLM_")]:
                os.environ.pop(k)
            c = carregar_config()
            self.assertEqual((c.modelo_id, c.offline, c.dispositivo, c.max_caracteres), (MODELO_PADRAO, True, "cpu", 2000))
        env = {"ESG_LLM_MODEL": "outro/modelo", "ESG_LLM_OFFLINE": "0", "ESG_LLM_TIMEOUT": "7.5",
               "ESG_LLM_DEVICE": "AUTO", "ESG_LLM_THREADS": "2", "ESG_LLM_MAX_CHARS": "abc"}
        with mock.patch.dict(os.environ, env):
            c = carregar_config()
        self.assertEqual((c.modelo_id, c.offline, c.timeout_s, c.dispositivo, c.threads), ("outro/modelo", False, 7.5, "auto", 2))
        self.assertEqual(c.max_caracteres, 2000)                          # valor inválido -> padrão

    def test_normalizar_texto(self):
        self.assertEqual(normalizar_texto("a \n  b\tc"), "a b c")

    def test_envelope_e_traducao_de_erros(self):
        e = montar_erro("X", "msg")
        self.assertEqual(set(e), {"codigo", "mensagem", "detalhes", "sugestao", "request_id"})
        self.assertEqual(e["detalhes"], [])
        erros = [
            {"type": "missing", "loc": ["body", "texto"], "msg": "Field required"},
            {"type": "string_too_short", "loc": ["body", "texto"], "msg": "x", "ctx": {"min_length": 1}},
            {"type": "string_pattern_mismatch", "loc": ["body", "mes_referencia"], "msg": "x", "ctx": {"pattern": "^a$"}},
            {"type": "greater_than", "loc": ["body", "quantidade"], "msg": "x", "ctx": {"gt": 0}},
            {"type": "value_error", "loc": ["body"], "msg": "Value error, emissão diverge"},
            {"type": "json_invalid", "loc": ["body", 0], "msg": "x"},
            {"type": "literal_error", "loc": ["body", "tarefa"], "msg": "x", "ctx": {"expected": "'sentimento'"}},
        ]
        d = detalhes_de_validacao(erros)
        self.assertEqual(d[0], {"campo": "texto", "problema": "campo obrigatório ausente"})
        self.assertEqual(d[1]["problema"], "tamanho mínimo: 1")
        self.assertIn("^a$", d[2]["problema"])
        self.assertEqual(d[3]["problema"], "deve ser maior que 0")
        self.assertEqual(d[4], {"campo": None, "problema": "emissão diverge"})
        self.assertEqual(d[5]["problema"], "JSON malformado")
        self.assertIn("sentimento", d[6]["problema"])
        self.assertEqual(traduzir_erro_validacao({"type": "algo_novo", "msg": "mensagem original"}), "mensagem original")


class AvaliacaoTests(unittest.TestCase):
    def test_metricas(self):
        reais = ["positivo", "positivo", "negativo", "neutro", "neutro"]
        prev = ["positivo", "negativo", "negativo", "neutro", "positivo"]
        m = avaliacao.metricas(reais, prev)
        self.assertEqual(m["n"], 5)
        self.assertEqual(m["acuracia"], 0.6)
        self.assertEqual(m["por_classe"]["positivo"], {"precisao": 0.5, "revocacao": 0.5, "f1": 0.5, "suporte": 2})
        self.assertEqual(m["por_classe"]["negativo"]["precisao"], 0.5)
        self.assertEqual(m["por_classe"]["neutro"]["revocacao"], 0.5)
        self.assertEqual(m["matriz_confusao"]["positivo"]["negativo"], 1)
        self.assertEqual(avaliacao.metricas([], [])["acuracia"], 0.0)
        with self.assertRaises(ValueError):
            avaliacao.metricas(["positivo"], [])

    def test_gabarito(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "g.csv"
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["doc_id", "titulo", "rotulo_humano", "anotador", "observacao"])
                w.writerow(["a", "t1", "Positivo", "", ""])
                w.writerow(["b", "t2", "", "", ""])
                w.writerow(["c", "t3", "alegre", "", ""])
                w.writerow(["d", "t4", "negative", "", ""])
            itens, avisos = avaliacao.carregar_gabarito(p)
        self.assertEqual([i["rotulo_humano"] for i in itens], ["positivo", "negativo"])
        self.assertEqual(len(avisos), 1)
        self.assertIn("Linha 4", avisos[0])


if __name__ == "__main__":
    unittest.main()
