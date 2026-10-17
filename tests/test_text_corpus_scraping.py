import json
import os
import tempfile
import unittest
from pathlib import Path

import _setup  # noqa: F401
import pandas as pd

from esg_core import corpus, data_access as da, paths
from esg_core.amostra import gerar_amostra_emissoes
from esg_core.text_utils import contar_palavras, frequencia_palavras, tokenizar
import scraping_utils as su
import scrape_noticias_esg as sn
import scrape_ods_ecycle as so

HTML_NOTICIAS = """
<html><body>
<nav><a href="/esg/">ESG</a> <a href="/autor/fulano/">Fulano de Tal da Silva Santos Oliveira</a></nav>
<article>
  <a href="/esg/vivo-reduz-emissoes-em-91-e-antecipa-neutralidade-climatica">Vivo reduz emissões em 91% e antecipa neutralidade climática</a>
  <time datetime="2026-05-27T10:00:00-03:00">27/05/2026</time>
  <p>Operadora detalha metas de redução e uso de energia renovável em seus data centers.</p>
</article>
<article>
  <a href="https://exame.com/esg/cafe-com-menor-pegada-de-carbono-chega-a-colheita">Café com menor pegada de carbono chega à primeira colheita</a>
  <span>30/05/2026</span>
</article>
<article>
  <a href="/esg/vivo-reduz-emissoes-em-91-e-antecipa-neutralidade-climatica">Vivo reduz emissões em 91% e antecipa neutralidade climática</a>
</article>
<a href="https://outro-site.com/esg/materia-qualquer-de-outro-dominio-aqui">Matéria qualquer de outro domínio aqui presente</a>
<a href="/curto">Curto</a>
</body></html>
"""

HTML_ODS = """
<html><body><h1>ODS 12: assegurar o consumo sustentável</h1>
<article>
 <h2>O que é o ODS 12</h2>
 <p>Curto demais.</p>
 <p>O ODS 12 busca assegurar padrões de produção e de consumo sustentáveis em todo o mundo.</p>
 <h2>Metas</h2>
 <p>Meta 12.2: até 2030, alcançar a gestão sustentável e o uso eficiente dos recursos naturais.</p>
</article></body></html>
"""

ROBOTS_BLOQUEIA = "User-agent: *\nDisallow: /esg/\n"
ROBOTS_LIBERA = "User-agent: *\nDisallow: /admin/\n"


class TextoTests(unittest.TestCase):
    def test_tokenizacao_e_frequencia(self):
        self.assertEqual(tokenizar("A pegada de carbono e o carbono!"), ["pegada", "carbono", "carbono"])
        self.assertEqual(frequencia_palavras(["carbono clima", "carbono"], 1), [("carbono", 2)])
        self.assertEqual(contar_palavras("uma frase com cinco palavras"), 5)


class ScrapingTests(unittest.TestCase):
    def test_robots(self):
        u = "https://exame.com/esg/"
        self.assertFalse(su.avaliar_robots(ROBOTS_BLOQUEIA, 200, u))
        self.assertTrue(su.avaliar_robots(ROBOTS_LIBERA, 200, u))
        self.assertTrue(su.avaliar_robots(None, 404, u))
        self.assertFalse(su.avaliar_robots("", 403, u))
        self.assertFalse(su.avaliar_robots(None, None, u))       # erro de rede => conservador
        self.assertFalse(su.avaliar_robots(None, 503, u))

    def test_normalizar_data_e_truncar(self):
        self.assertEqual(su.normalizar_data("2026-05-27T10:00:00-03:00"), "2026-05-27")
        self.assertEqual(su.normalizar_data("publicado em 30/05/2026"), "2026-05-30")
        self.assertEqual(su.normalizar_data("ontem"), "")
        self.assertLessEqual(len(su.truncar("palavra " * 100, 50)), 51)

    def test_manchetes(self):
        m = sn.extrair_manchetes_de_html(HTML_NOTICIAS, "https://exame.com/esg/")
        titulos = [x["titulo"] for x in m]
        self.assertEqual(len(m), 2)                              # dedupe + filtros de domínio/autor/curto
        self.assertIn("Vivo reduz emissões em 91% e antecipa neutralidade climática", titulos)
        vivo = m[0]
        self.assertEqual(vivo["data_publicacao"], "2026-05-27")
        self.assertEqual(vivo["fonte"], "exame.com")
        self.assertTrue(vivo["resumo"].startswith("Operadora detalha"))
        self.assertIn("emissoes", vivo["tags"])
        self.assertEqual(m[1]["data_publicacao"], "2026-05-30")  # data em texto solto

    def test_tags(self):
        self.assertEqual(set(sn.classificar_tags("CVM define regras de emissões de carbono")),
                         {"regulacao", "emissoes", "carbono"})

    def test_ods(self):
        d = so.extrair_trechos_de_html(HTML_ODS)
        self.assertEqual(d["titulo"], "ODS 12: assegurar o consumo sustentável")
        self.assertEqual(len(d["itens"]), 2)                     # parágrafo curto descartado
        self.assertEqual(d["itens"][0]["secao"], "O que é o ODS 12")
        self.assertEqual(d["itens"][1]["secao"], "Metas")


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ESG_DATA_DIR"] = self.tmp.name
        for d in ("raw", "processed"):
            (Path(self.tmp.name) / d).mkdir()
        gerar_amostra_emissoes().to_csv(paths.caminho_emissoes_base(), index=False)
        pd.DataFrame({"titulo": ["Vivo reduz emissões em 91%", "Vivo reduz emissões em 91%", "Outra manchete aqui"],
                      "data_publicacao": ["2026-05-27", "2026-05-27", ""], "url_materia": ["https://exame.com/esg/a"] * 2 + ["https://exame.com/esg/b"],
                      "data_coleta": ["2026-09-16 00:00:00"] * 3, "tags": ["emissoes", "emissoes", ""]}
                     ).to_csv(paths.caminho_noticias(), index=False)
        pd.DataFrame({"ods": ["ODS 12"], "titulo_pagina": ["t"], "secao": ["Metas"], "trecho": ["Meta 12.2 texto"],
                      "url_fonte": ["https://www.ecycle.com.br/ods-12/"], "data_coleta": ["2026-09-16"]}
                     ).to_csv(paths.caminho_ods(), index=False)

    def tearDown(self):
        os.environ.pop("ESG_DATA_DIR", None)
        self.tmp.cleanup()

    def test_corpus_schema_dedupe_e_jsonl(self):
        docs = corpus.construir_corpus()
        self.assertEqual(len(docs), 3)                           # 2 notícias únicas + 1 trecho
        chaves = {"doc_id", "tipo", "fonte", "url", "titulo", "texto", "data_publicacao", "data_coleta",
                  "idioma", "n_palavras", "secao", "tags", "usos_previstos"}
        for d in docs:
            self.assertEqual(set(d), chaves)
        self.assertEqual(len({d["doc_id"] for d in docs}), 3)
        corpus.salvar_jsonl(docs, paths.caminho_corpus())
        self.assertEqual(da.carregar_corpus(), docs)
        self.assertEqual(docs[0]["tags"], ["emissoes"])
        self.assertIsNone(docs[1]["data_publicacao"])

    def test_contexto_relatorio(self):
        c = corpus.construir_contexto_relatorio(da.carregar_emissoes())
        self.assertAlmostEqual(sum(x["percentual"] for x in c["por_tipo_atividade"]), 100, delta=0.5)
        self.assertEqual(len(c["maiores_fontes"]), 3)
        self.assertEqual(len(c["por_mes"]), 24)
        self.assertIsNotNone(c["variacao_ultimo_mes_pct"])
        json.dumps(c, ensure_ascii=False)                         # serializável

    def test_templates(self):
        docs = corpus.construir_corpus()
        sent, qa = corpus.gerar_templates_avaliacao(docs, Path(self.tmp.name) / "processed" / "avaliacao")
        self.assertEqual(len(pd.read_csv(sent)), 2)
        self.assertEqual(list(pd.read_csv(qa).columns), ["pergunta", "resposta_esperada", "doc_id_fonte", "tipo_pergunta"])


if __name__ == "__main__":
    unittest.main()
