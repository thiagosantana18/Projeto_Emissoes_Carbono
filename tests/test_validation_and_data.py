import os
import tempfile
import unittest
from pathlib import Path

import _setup  # noqa: F401
import pandas as pd

from esg_core import data_access as da, paths
from esg_core.amostra import gerar_amostra_emissoes
from esg_core.validation import (COLUNAS_EMISSOES, diagnostico_qualidade_emissoes, emissao_consistente,
                                 validar_emissoes_df)


class ValidacaoTests(unittest.TestCase):
    def linha(self, **kw):
        base = dict(mes_referencia="2026-09", unidade="Matriz - SP", setor="Administrativo",
                    tipo_atividade="Eletricidade (rede)", quantidade=8500.0, unidade_medida="kWh",
                    fator_emissao_kgco2e=0.0817, emissao_kgco2e=694.45, fonte_fator="Climatiq API")
        base.update(kw)
        return base

    def test_consistencia(self):
        self.assertTrue(emissao_consistente(8500, 0.0817, 694.45))
        self.assertFalse(emissao_consistente(8500, 0.0817, 900))

    def test_df_valido(self):
        ok, erros = validar_emissoes_df(pd.DataFrame([self.linha()]))
        self.assertEqual(len(ok), 1)
        self.assertEqual(erros, [])

    def test_colunas_faltando_rejeita_arquivo(self):
        ok, erros = validar_emissoes_df(pd.DataFrame([{"unidade": "x"}]))
        self.assertTrue(ok.empty)
        self.assertIn("Colunas obrigatórias ausentes", erros[0])

    def test_erros_por_linha(self):
        df = pd.DataFrame([self.linha(), self.linha(mes_referencia="2026-13"),
                           self.linha(quantidade=-1), self.linha(emissao_kgco2e=5000.0),
                           self.linha(unidade="")])
        ok, erros = validar_emissoes_df(df)
        self.assertEqual(len(ok), 1)
        self.assertEqual(len(erros), 4)
        self.assertTrue(erros[0].startswith("Linha 3"))

    def test_template_e_valido(self):
        from io import StringIO
        ok, erros = validar_emissoes_df(pd.read_csv(StringIO(da.template_emissoes_csv())))
        self.assertEqual((len(ok), erros), (1, []))


class AmostraTests(unittest.TestCase):
    def test_reprodutivel_e_consistente(self):
        a, b = gerar_amostra_emissoes(), gerar_amostra_emissoes()
        pd.testing.assert_frame_equal(a, b)
        self.assertEqual(len(a), 24 * 9)
        ok, erros = validar_emissoes_df(a)
        self.assertEqual((len(ok), erros), (len(a), []))

    def test_diagnostico_sem_lacunas(self):
        d = diagnostico_qualidade_emissoes(gerar_amostra_emissoes())
        self.assertEqual(d["meses_faltantes"], [])
        self.assertEqual((d["duplicados"], d["emissoes_inconsistentes"]), (0, 0))
        self.assertEqual((d["periodo_inicio"], d["periodo_fim"]), ("2024-10", "2026-09"))

    def test_diagnostico_detecta_lacuna(self):
        df = gerar_amostra_emissoes()
        df = df[df["mes_referencia"] != "2025-03"]
        self.assertEqual(diagnostico_qualidade_emissoes(df)["meses_faltantes"], ["2025-03"])


class DataAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ESG_DATA_DIR"] = self.tmp.name
        (Path(self.tmp.name) / "raw").mkdir()
        (Path(self.tmp.name) / "processed").mkdir()
        gerar_amostra_emissoes().to_csv(paths.caminho_emissoes_base(), index=False)

    def tearDown(self):
        os.environ.pop("ESG_DATA_DIR", None)
        self.tmp.cleanup()

    def test_arquivos_ausentes_retornam_vazio(self):
        os.remove(paths.caminho_emissoes_base())
        self.assertTrue(da.carregar_emissoes().empty)
        self.assertTrue(da.carregar_noticias().empty)
        self.assertEqual(da.carregar_corpus(), [])

    def test_regressao_keyerror_data_publicacao(self):
        """Bug real: CSV de notícias sem a coluna data_publicacao derrubava o app."""
        pd.DataFrame({"titulo": ["Manchete longa de teste aqui"], "url_materia": ["https://x.com/a/b"],
                      "data_coleta": ["2026-09-16 00:30:00"]}).to_csv(paths.caminho_noticias(), index=False)
        df = da.carregar_noticias()
        self.assertEqual(df.loc[0, "data_publicacao"], "2026-09-16 00:30:00")
        for c in da.COLUNAS_NOTICIAS:
            self.assertIn(c, df.columns)

    def test_post_e_origem(self):
        reg = dict(mes_referencia="2026-10", unidade="Matriz - SP", setor="Administrativo",
                   tipo_atividade="Eletricidade (rede)", quantidade=100.0, unidade_medida="kWh",
                   fator_emissao_kgco2e=0.0817, emissao_kgco2e=8.17, fonte_fator="Climatiq API")
        self.assertEqual(da.anexar_emissoes_enviadas([reg, reg]), 2)
        df = da.carregar_emissoes()
        self.assertEqual(len(df), 216 + 2)
        self.assertEqual(set(df["origem"]), {"base", "api"})
        self.assertEqual(len(da.carregar_emissoes(incluir_enviadas=False)), 216)

    def test_filtros_paginacao_resumo(self):
        df = da.carregar_emissoes()
        f = da.filtrar_emissoes(df, unidade="filial - rj", mes_inicio="2026-01", mes_fim="2026-03")
        self.assertEqual(set(f["unidade"]), {"Filial - RJ"})
        self.assertEqual(len(f), 3 * 2)
        self.assertEqual(len(da.paginar(df, 10, 5)), 10)
        r = da.resumo_emissoes(df)
        self.assertAlmostEqual(sum(r["por_unidade"].values()), r["total_kgco2e"], delta=0.05)
        self.assertEqual(len(r["por_mes"]), 24)

    def test_registros_json_safe(self):
        reg = da.df_para_registros(pd.DataFrame({"a": [1.0, None], "b": ["x", None]}))
        self.assertIsNone(reg[1]["a"])
        self.assertIsNone(reg[1]["b"])

    def test_assinatura_muda_com_arquivo(self):
        s1 = da.assinatura_emissoes()
        da.anexar_emissoes_enviadas([dict(mes_referencia="2026-10", unidade="a", setor="b", tipo_atividade="c",
                                          quantidade=1.0, unidade_medida="kWh", fator_emissao_kgco2e=1.0,
                                          emissao_kgco2e=1.0, fonte_fator="x")])
        self.assertNotEqual(s1, da.assinatura_emissoes())

    def test_filtros_texto(self):
        n = pd.DataFrame({"titulo": ["Vivo reduz emissões em 91%", "Café com menor pegada de carbono"],
                          "data_publicacao": ["2026-05-27", "2026-05-30"], "tags": ["emissoes", "carbono"]})
        self.assertEqual(len(da.filtrar_noticias(n, q="vivo")), 1)
        self.assertEqual(da.filtrar_noticias(n, tag="carbono").iloc[0]["titulo"], "Café com menor pegada de carbono")
        self.assertEqual(da.filtrar_noticias(n).iloc[0]["data_publicacao"], "2026-05-30")
        o = pd.DataFrame({"ods": ["ODS 12", "ODS 13"], "trecho": ["a resíduos", "b clima"]})
        self.assertEqual(len(da.filtrar_ods(o, ods="ods 13")), 1)


if __name__ == "__main__":
    unittest.main()
