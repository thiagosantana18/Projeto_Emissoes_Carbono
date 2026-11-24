import os
import tempfile
import unittest
from pathlib import Path

import _setup  # noqa: F401
import pandas as pd

from esg_core import corpus as corpus_mod, paths
from esg_core.amostra import gerar_amostra_emissoes
from esg_core.ia import errors as E
from esg_core.ia.config import ConfigIA
from esg_core.ia.controle import AuditoriaIA, CacheIA, LimiteUso
from esg_core.ia.evidencias import PERGUNTAS, coletar_evidencias, renderizar_md
from esg_core.ia.servico import ServicoIA
from esg_core.qualidade import checks, relatorio_qualidade, renderizar_relatorio_md
from ia_helpers import ClienteFalso, sumario


class EvidenciasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ESG_DATA_DIR"] = self.tmp.name
        for d in ("raw", "processed", "interim"):
            (Path(self.tmp.name) / d).mkdir()
        gerar_amostra_emissoes().to_csv(paths.caminho_emissoes_base(), index=False)
        pd.DataFrame({"titulo": ["Vivo reduz emissões em 91% e antecipa neutralidade climática para 2035", "Gerdau reduz pegada de carbono do aço"],
                      "data_publicacao": ["2026-05-27"] * 2, "tags": ["emissoes", "carbono"], "url_materia": ["https://exame.com/esg/a", "https://exame.com/esg/b"],
                      "data_coleta": ["2026-09-16"] * 2, "fonte": ["exame.com"] * 2}).to_csv(paths.caminho_noticias(), index=False)
        pd.DataFrame({"ods": ["ODS 13"], "titulo_pagina": ["t"], "secao": ["Metas"], "trecho": ["Meta 13.2: integrar medidas da mudança do clima ao planejamento nacional."],
                      "url_fonte": ["https://ecycle/13"], "data_coleta": ["2026-09-16"]}).to_csv(paths.caminho_ods(), index=False)
        corpus_mod.salvar_jsonl(corpus_mod.construir_corpus(), paths.caminho_corpus())

    def tearDown(self):
        os.environ.pop("ESG_DATA_DIR", None)
        self.tmp.cleanup()

    def servico(self, funcao):
        cli = ClienteFalso(funcao=funcao)
        return ServicoIA(ConfigIA(openai_chave="k", max_chamadas_hora=100), fabrica=lambda c, p: cli, cache=CacheIA(paths.caminho_ia_cache_dir()),
                         auditoria=AuditoriaIA(paths.caminho_ia_dir() / "h.jsonl"), limite=LimiteUso(100)), cli

    @staticmethod
    def responder(u):
        if "Pergunta do gestor" in u:
            return {"resposta": "Não sei.", "confianca": "baixa", "fontes_citadas": [], "lacunas": []}
        if "gerar insights" in u:
            return {"destaques": [{"titulo": "Diesel", "detalhe": "E1"}], "riscos": [], "recomendacoes": [], "alertas_de_dados": [], "fontes_citadas": ["E1"]}
        return sumario("Vivo: 91% e 2035 (d1).", fontes=("d1",), recomendacoes=[], riscos_e_oportunidades=[])

    def test_coleta_e_relatorio(self):
        s, cli = self.servico(self.responder)
        ev = coletar_evidencias(s, comparar_prompts=True)
        tipos = [i["tipo"] for i in ev["itens"]]
        self.assertEqual(tipos.count("pergunta"), len(PERGUNTAS))
        self.assertEqual(tipos.count("comparacao"), 2)
        pergunta_controle = [i for i in ev["itens"] if i["entrada"].startswith("Qual é a receita")][0]
        self.assertFalse(pergunta_controle["resultado"]["chamou_llm"])         # sem base: a IA nem é chamada
        md = renderizar_md(ev)
        for trecho in ("# Evidências de uso da IA online", "## Resumo das notícias ESG", "## Insights sobre as emissões", "## Comparação de versões de prompt",
                       "| sumario_v1 |", "| sumario_v2 |", "a IA não foi chamada", "Fidelidade"):
            self.assertIn(trecho, md)

    def test_falha_de_um_item_nao_derruba_os_demais(self):
        def funcao(u):
            if "gerar insights" in u:
                return E.IAProvedorError("provedor fora do ar", sugestao="tente depois")
            return self.responder(u)
        class Falho(ClienteFalso):
            def gerar(self, s, u, m=None):
                r = funcao(u)
                if isinstance(r, Exception):
                    raise r
                return super().gerar(s, u, m)
        cli = Falho(funcao=self.responder)
        s = ServicoIA(ConfigIA(openai_chave="k"), fabrica=lambda c, p: cli, cache=CacheIA(paths.caminho_ia_cache_dir(), False),
                      auditoria=AuditoriaIA(paths.caminho_ia_dir() / "h.jsonl"), limite=LimiteUso(100))
        ev = coletar_evidencias(s)
        erros = [i for i in ev["itens"] if "erro" in i]
        self.assertEqual([e["erro"]["codigo"] for e in erros], ["IA_PROVEDOR_INDISPONIVEL"])
        self.assertIn("❌ **Falhou**", renderizar_md(ev))
        self.assertGreater(len(ev["itens"]) - len(erros), 3)

    def test_relatorio_de_qualidade_md(self):
        rel = relatorio_qualidade()
        md = renderizar_relatorio_md(rel)
        feitas = sum(ok for _, ok, _ in checks(rel))
        self.assertIn(f"**{feitas} de {len(checks(rel))} verificações aprovadas.**", md)
        for secao in ("## 2. Emissões", "## 3. Notícias coletadas", "## 5. Corpus para IA", "## 7. Achados e ações"):
            self.assertIn(secao, md)
        self.assertNotIn("|z|", md)
        linhas_tabela = [l for l in md.splitlines() if l.startswith("| ") and "Verificação" not in l and "---" not in l][:len(checks(rel))]
        self.assertTrue(all(l.count("|") == 4 for l in linhas_tabela), "pipe extra quebra a tabela")


if __name__ == "__main__":
    unittest.main()
