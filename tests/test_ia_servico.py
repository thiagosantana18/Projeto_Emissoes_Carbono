import os
import tempfile
import unittest
from pathlib import Path

import _setup  # noqa: F401
import pandas as pd

from esg_core import corpus as corpus_mod, data_access as da, paths
from esg_core.amostra import gerar_amostra_emissoes
from esg_core.ia import errors as E
from esg_core.ia.config import ConfigIA
from esg_core.ia.controle import AuditoriaIA, CacheIA, ClienteMedido, LimiteUso
from esg_core.ia.insights import br, gerar_insights, renderizar_contexto_emissoes, validar_insights
from esg_core.ia.qa import IndiceBM25, responder, tokens_busca
from esg_core.ia.servico import ServicoIA
from esg_core.previsao import prever_emissoes, serie_mensal
from ia_helpers import ClienteFalso, sumario

NOTICIAS = [("Vivo reduz emissões em 91% e antecipa neutralidade climática para 2035", "2026-05-27", "emissoes;neutralidade"),
            ("Gerdau reduz pela metade pegada de carbono do aço e amplia aposta em energia limpa", "2026-05-27", "carbono;energia"),
            ("Café com menor pegada de carbono chega a primeira colheita no Brasil", "2026-05-30", "carbono"),
            ("CVM retira obrigatoriedade de relatório financeiro de sustentabilidade", "2026-05-30", "regulacao;sustentabilidade")]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ESG_DATA_DIR"] = self.tmp.name
        for d in ("raw", "processed", "interim"):
            (Path(self.tmp.name) / d).mkdir()
        gerar_amostra_emissoes().to_csv(paths.caminho_emissoes_base(), index=False)
        pd.DataFrame({"titulo": [n[0] for n in NOTICIAS], "data_publicacao": [n[1] for n in NOTICIAS], "tags": [n[2] for n in NOTICIAS],
                      "url_materia": [f"https://exame.com/esg/{i}" for i in range(4)], "data_coleta": ["2026-09-16 00:00:00"] * 4,
                      "fonte": ["exame.com"] * 4}).to_csv(paths.caminho_noticias(), index=False)
        pd.DataFrame({"ods": ["ODS 13"], "titulo_pagina": ["t"], "secao": ["Metas"], "trecho": ["Meta 13.2: integrar medidas da mudança do clima ao planejamento."],
                      "url_fonte": ["https://ecycle/13"], "data_coleta": ["2026-09-16"]}).to_csv(paths.caminho_ods(), index=False)
        corpus_mod.salvar_jsonl(corpus_mod.construir_corpus(), paths.caminho_corpus())

    def tearDown(self):
        os.environ.pop("ESG_DATA_DIR", None)
        self.tmp.cleanup()

    def servico(self, cliente, **cfg):
        base = dict(openai_chave="k", max_chamadas_hora=100)
        base.update(cfg)
        self.cliente = cliente
        return ServicoIA(ConfigIA(**base), fabrica=lambda c, p: cliente, cache=CacheIA(paths.caminho_ia_cache_dir()),
                         auditoria=AuditoriaIA(paths.caminho_ia_dir() / "historico.jsonl"), limite=LimiteUso(base["max_chamadas_hora"]))


class QATests(Base):
    def test_busca(self):
        self.assertEqual(tokens_busca("Quais as EMISSÕES da empresa?"), tokens_busca("emissão"))
        docs = [n[0] for n in NOTICIAS]
        achados = IndiceBM25(docs).buscar("neutralidade climática 2035")
        self.assertEqual(achados[0][0], 0)
        self.assertEqual(IndiceBM25(docs).buscar("xylophone quantum"), [])
        self.assertEqual(IndiceBM25([]).buscar("qualquer"), [])

    def test_sem_trechos_nao_chama_llm(self):
        c = ClienteFalso()                                                      # fila vazia: chamar o LLM quebraria o teste
        r = responder(c, "Qual a receita de bolo de cenoura?", [{"doc_id": "a", "texto": "Emissões de carbono caíram 91%."}])
        self.assertFalse(r["chamou_llm"])
        self.assertEqual((r["confianca"], r["n_chamadas"], c.chamadas), ("baixa", 0, []))

    def test_resposta_ancorada(self):
        docs = [{"doc_id": "x1", "titulo": "Vivo", "texto": "A Vivo reduziu 91% das emissões.", "fonte": "exame"},
                {"doc_id": "x2", "titulo": "Café", "texto": "Café com menor pegada de carbono."}]
        c = ClienteFalso({"resposta": "A Vivo reduziu 91% (d1).", "confianca": "Média", "fontes_citadas": ["d1", "d9"], "lacunas": []})
        r = responder(c, "Quanto a Vivo reduziu de emissões?", docs)
        self.assertEqual((r["confianca"], r["fontes_citadas"], r["trechos"][0]["doc_id"]), ("media", ["d1"], "x1"))
        self.assertEqual(r["fidelidade"]["citacoes_invalidas"], ["d9"])
        self.assertIn("Pergunta do gestor", c.chamadas[0]["usuario"])
        with self.assertRaises(E.TextoInvalidoError):
            responder(c, " ", docs)


class InsightsTests(Base):
    def test_contexto_formatado_em_ptbr(self):
        ctx = corpus_mod.construir_contexto_relatorio(da.carregar_emissoes())
        texto = renderizar_contexto_emissoes(ctx)
        self.assertIn(br(ctx["total_kgco2e"]), texto)
        self.assertRegex(texto, r"\d\.\d{3},\d{2} kgCO2e")
        self.assertIn("Diesel (frota)", texto)
        self.assertIn("sintéticos", texto)

    def test_insights_fiel_e_invencao(self):
        ctx = corpus_mod.construir_contexto_relatorio(da.carregar_emissoes())
        topo = ctx["por_tipo_atividade"][0]
        bom = {"destaques": [{"titulo": f"{topo['nome']} lidera", "detalhe": f"Responde por {br(topo['percentual'], 1)}% do total (E1)."}],
               "riscos": [{"descricao": "Concentração.", "gravidade": "Alta"}],
               "recomendacoes": [{"acao": "Reduzir diesel", "justificativa": "Maior fonte (E1).", "impacto_esperado": "queda", "prioridade": "alta", "ods": "13"}],
               "alertas_de_dados": ["Dados sintéticos."], "fontes_citadas": ["E1", "Z9"]}
        r = gerar_insights(ClienteFalso(bom), ctx)
        self.assertTrue(r["fidelidade"]["ok"] is False and r["fidelidade"]["citacoes_invalidas"] == ["Z9"])
        bom["fontes_citadas"] = ["E1"]
        self.assertTrue(gerar_insights(ClienteFalso(bom), ctx)["fidelidade"]["ok"])
        bom["destaques"][0]["detalhe"] = "Responde por 99,9% do total (E1)."
        self.assertIn("99.9", gerar_insights(ClienteFalso(bom), ctx)["fidelidade"]["numeros_nao_encontrados"])
        with self.assertRaises(E.IARespostaInvalidaError):
            validar_insights({"destaques": [], "recomendacoes": []})


class ControleTests(unittest.TestCase):
    def test_limite_janela_deslizante(self):
        t = [0.0]
        lim = LimiteUso(2, lambda: t[0])
        lim.registrar(); lim.registrar()
        with self.assertRaises(E.IAUsoExcedidoError) as cm:
            lim.registrar()
        self.assertEqual((cm.exception.status_code, cm.exception.retry_after), (429, 3601))
        t[0] = 3601.0
        lim.registrar()
        self.assertEqual(lim.usadas(), 1)

    def test_cache_e_auditoria(self):
        with tempfile.TemporaryDirectory() as d:
            c = CacheIA(Path(d) / "c")
            k = CacheIA.chave("a", 1, "b")
            self.assertEqual(k, CacheIA.chave("a", 1, "b"))
            self.assertNotEqual(k, CacheIA.chave("a", 2, "b"))
            self.assertIsNone(c.obter(k))
            c.salvar(k, {"x": "ç"})
            self.assertEqual(c.obter(k), {"x": "ç"})
            (Path(d) / "c" / f"{k}.json").write_text("{corrompido", encoding="utf-8")
            self.assertIsNone(c.obter(k))
            off = CacheIA(Path(d) / "off", ativo=False)
            off.salvar(k, {"x": 1})
            self.assertIsNone(off.obter(k))
            a = AuditoriaIA(Path(d) / "a" / "h.jsonl")
            self.assertEqual(a.ler(), [])
            for i in range(5):
                a.registrar({"i": i})
            with open(a.caminho, "a", encoding="utf-8") as f:
                f.write("lixo\n")
            self.assertEqual([x["i"] for x in a.ler(3)], [4, 3, 2])
            self.assertIn("em", a.ler(1)[0])

    def test_cliente_medido(self):
        lim = LimiteUso(1)
        cm = ClienteMedido(ClienteFalso({"a": 1}, {"a": 2}), lim)
        cm.gerar("s", "u")
        with self.assertRaises(E.IAUsoExcedidoError):
            cm.gerar("s", "u")
        self.assertEqual((cm.chamadas, cm.provedor), (1, "openai"))


class PrevisaoTests(Base):
    def _serie(self, valores, inicio="2023-01"):
        meses = pd.period_range(inicio, periods=len(valores), freq="M").astype(str)
        return pd.DataFrame({"mes_referencia": meses, "emissao_kgco2e": valores})

    def test_serie_e_lacunas(self):
        df = self._serie([10.0, 20.0, 30.0]).drop(index=1)
        s = serie_mensal(df)
        self.assertEqual((len(s), s.iloc[1]), (3, 20.0))                       # mês faltante interpolado
        with self.assertRaises(ValueError):
            prever_emissoes(self._serie([1.0] * 10))

    def test_padrao_sazonal_exato(self):
        base = [100, 110, 130, 150, 170, 160, 150, 140, 130, 120, 110, 100]
        r = prever_emissoes(self._serie(base * 3))
        self.assertLess(r["mape_melhor"], 0.5)
        self.assertEqual([round(p["previsto"]) for p in r["previsoes"]], base[:6])
        self.assertEqual(r["previsoes"][0]["mes"], "2026-01")
        self.assertTrue(r["atinge_meta"])

    def test_constante_e_faixa(self):
        r = prever_emissoes(self._serie([500.0] * 20))
        self.assertTrue(all(m["mape"] == 0 for m in r["metodos"]))
        for p in r["previsoes"]:
            self.assertTrue(p["min"] <= p["previsto"] <= p["max"])

    def test_amostra_do_projeto(self):
        r = prever_emissoes(da.carregar_emissoes())
        self.assertEqual((r["serie"]["n_meses"], len(r["previsoes"]), r["melhor"]), (24, 6, "tendencia_sazonal"))
        self.assertTrue(r["atinge_meta"])
        self.assertEqual([m["metodo"] for m in r["metodos"]][0], r["melhor"])
        self.assertEqual(len(r["historico"]), 24)


class ServicoTests(Base):
    TEXTO = "A empresa reduziu 91% das emissões e antecipou a neutralidade para 2035. " * 4

    def test_status(self):
        s = ServicoIA(ConfigIA(), cache=CacheIA(paths.caminho_ia_cache_dir()), auditoria=AuditoriaIA(paths.caminho_ia_dir() / "h.jsonl"))
        st = s.status()
        self.assertFalse(st["algum_configurado"])
        self.assertEqual([p["nome"] for p in st["provedores"]], ["openai", "anthropic"])
        self.assertTrue(self.servico(ClienteFalso()).status()["algum_configurado"])

    def test_sem_chave(self):
        s = ServicoIA(ConfigIA(), cache=CacheIA(paths.caminho_ia_cache_dir()), auditoria=AuditoriaIA(paths.caminho_ia_dir() / "h.jsonl"))
        with self.assertRaises(E.IANaoConfiguradaError):
            s.sumarizar_texto(self.TEXTO)

    def test_cache_auditoria_e_reuso(self):
        s = self.servico(ClienteFalso(sumario("Resumo: 91% e 2035 (p1).", fontes=("p1",), recomendacoes=[], riscos_e_oportunidades=[])))
        r1 = s.sumarizar_texto(self.TEXTO)
        r2 = s.sumarizar_texto(self.TEXTO)                                      # a fila do falso está vazia: só o cache responde
        self.assertEqual((r1["cache"], r2["cache"], len(self.cliente.chamadas)), (False, True, 1))
        self.assertEqual(r2["resumo"]["resumo_executivo"], r1["resumo"]["resumo_executivo"])
        h = s.historico()
        self.assertEqual((len(h), h[0]["cache"], h[1]["cache"], h[1]["tipo"]), (2, True, False, "sumario_texto"))
        self.assertTrue(h[1]["fidelidade_ok"])
        self.assertNotIn(self.TEXTO[:30], str(h))                               # a entrada não vai para o log (só o hash/tamanho)
        self.assertEqual(h[1]["n_caracteres_entrada"], len(self.TEXTO.strip()))

    def test_saida_com_numero_inventado_nao_e_cacheada(self):
        ruim = sumario("A empresa reduziu 77% (p1).", fontes=("p1",), recomendacoes=[], riscos_e_oportunidades=[], pontos_chave=[])
        s = self.servico(ClienteFalso(ruim, ruim))
        self.assertFalse(s.sumarizar_texto(self.TEXTO)["fidelidade"]["ok"])
        s.sumarizar_texto(self.TEXTO)
        self.assertEqual(len(self.cliente.chamadas), 2)                         # não foi congelada no cache

    def test_validacoes(self):
        s = self.servico(ClienteFalso(), max_chars_entrada=100)
        for texto in ("curto", "x" * 101):
            with self.assertRaises(E.TextoInvalidoError):
                s.sumarizar_texto(texto)
        with self.assertRaises(E.TextoInvalidoError):
            s.sumarizar_texto("y" * 80, versao_prompt="v99")
        with self.assertRaises(E.TextoInvalidoError):
            s.sumarizar_texto("y" * 80, provedor="gemini")

    def test_limite_local_mas_cache_continua(self):
        a = sumario("Resumo de 91% (p1).", fontes=("p1",), recomendacoes=[], riscos_e_oportunidades=[], pontos_chave=[])
        s = self.servico(ClienteFalso(a), max_chamadas_hora=1)
        s.sumarizar_texto(self.TEXTO)
        with self.assertRaises(E.IAUsoExcedidoError):
            s.sumarizar_texto(self.TEXTO + " outro texto diferente para evitar o cache.")
        self.assertTrue(s.sumarizar_texto(self.TEXTO)["cache"])

    def test_corpus(self):
        resp = sumario("Notícias: 91% e 2035 (d1).", fontes=("d1",), recomendacoes=[], riscos_e_oportunidades=[], pontos_chave=[])
        s = self.servico(ClienteFalso(resp))
        r = s.sumarizar_corpus(tipo="noticia", tag="carbono", limite=5)
        self.assertEqual(r["n_documentos"], 2)
        usr = self.cliente.chamadas[0]["usuario"]
        self.assertIn("Gerdau", usr)
        self.assertNotIn("Vivo", usr)
        self.assertTrue(r["fontes"][0]["doc_id"])
        for kw in ({"tag": "inexistente"}, {"tipo": "outro"}):
            with self.assertRaises(E.DadosIndisponiveisError):
                s.sumarizar_corpus(**kw)
        os.remove(paths.caminho_corpus())
        with self.assertRaises(E.DadosIndisponiveisError) as cm:
            s.sumarizar_corpus()
        self.assertIn("build_corpus", cm.exception.sugestao)

    def test_perguntar_inclui_emissoes(self):
        s = self.servico(ClienteFalso({"resposta": "O diesel (frota) é a maior fonte (d1).", "confianca": "alta", "fontes_citadas": ["d1"], "lacunas": []}))
        r = s.perguntar("Qual atividade de diesel emite mais?")
        self.assertIn("Diesel (frota)", self.cliente.chamadas[0]["usuario"])
        self.assertEqual(r["trechos"][0]["doc_id"], "EMISSOES")
        self.assertTrue(r["chamou_llm"])

    def test_insights_completo(self):
        pd.DataFrame({"doc_id": ["a", "b", "c"], "titulo": ["x"] * 3, "rotulo_previsto": ["positivo", "positivo", "neutro"]}).to_csv(
            paths.processed_dir() / "sentimento_noticias.csv", index=False)
        ctx, _ = ServicoIA._contexto_emissoes(self.servico(ClienteFalso()))
        topo = ctx["por_tipo_atividade"][0]
        resumo = sumario("Notícias: 91% e 2035 (d1).", fontes=("d1",), recomendacoes=[], riscos_e_oportunidades=[], pontos_chave=[])
        ins = {"destaques": [{"titulo": topo["nome"], "detalhe": f"{br(topo['percentual'], 1)}% (E1)"}], "riscos": [], "recomendacoes": [
            {"acao": "Priorizar", "justificativa": "E1", "impacto_esperado": "x", "prioridade": "alta", "ods": "13"}], "alertas_de_dados": [], "fontes_citadas": ["E1"]}
        s = self.servico(ClienteFalso(resumo, ins))
        r = s.insights_emissoes(foco="reduzir diesel", incluir_noticias=True)
        usr = self.cliente.chamadas[1]["usuario"]
        for trecho in ("Previsão de emissões", "Sentimento das 3 manchetes", "positivo: 2", "reduzir diesel", "Resumo das notícias ESG"):
            self.assertIn(trecho, usr)
        self.assertEqual((len(self.cliente.chamadas), len(s.historico())), (2, 2))
        self.assertTrue(r["fidelidade"]["ok"], r["fidelidade"])
        self.assertEqual(r["avisos"], [])
        os.remove(paths.caminho_emissoes_base())
        with self.assertRaises(E.DadosIndisponiveisError):
            self.servico(ClienteFalso()).insights_emissoes()


if __name__ == "__main__":
    unittest.main()
