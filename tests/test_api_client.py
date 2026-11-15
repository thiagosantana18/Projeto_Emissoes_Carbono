import sys
import unittest
from pathlib import Path
from unittest import mock

import _setup  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "App" / "dashboard"))
import requests  # noqa: E402

import api_client as ac  # noqa: E402


def resp(status=200, corpo=None, headers=None, texto=""):
    r = mock.Mock()
    r.status_code, r.ok, r.headers, r.text = status, status < 400, headers or {}, texto
    if corpo is None:
        r.json.side_effect = ValueError("sem json")
    else:
        r.json.return_value = corpo
    return r


class ApiClientTests(unittest.TestCase):
    def test_paginacao_de_emissoes(self):
        paginas = [resp(corpo={"total": 1500, "itens": [{"a": i} for i in range(1000)]}),
                   resp(corpo={"total": 1500, "itens": [{"a": i} for i in range(500)]})]
        with mock.patch("requests.request", side_effect=paginas) as m:
            df = ac.obter_emissoes("http://x:8000/", unidade="Matriz - SP", setor="")
        self.assertEqual(len(df), 1500)
        self.assertEqual(m.call_args_list[1].kwargs["params"]["offset"], 1000)
        self.assertNotIn("setor", m.call_args_list[0].kwargs["params"])          # filtro vazio não é enviado
        self.assertEqual(m.call_args_list[0].args[1], "http://x:8000/emissoes")  # sem barra dupla

    def test_envelope_vira_apierro(self):
        corpo = {"codigo": "MODELO_INDISPONIVEL", "mensagem": "sem modelo", "sugestao": "baixe", "detalhes": [], "request_id": "r1"}
        with mock.patch("requests.request", return_value=resp(503, corpo, {"Retry-After": "12"})):
            with self.assertRaises(ac.ApiErro) as cm:
                ac.processar_texto("http://x", "texto")
        e = cm.exception
        self.assertEqual((e.status, e.codigo, e.sugestao, e.retry_after), (503, "MODELO_INDISPONIVEL", "baixe", "12"))

    def test_erro_sem_envelope(self):
        with mock.patch("requests.request", return_value=resp(502, None, texto="Bad Gateway")):
            with self.assertRaises(ac.ApiErro) as cm:
                ac.health("http://x")
        self.assertEqual((cm.exception.status, cm.exception.codigo), (502, "ERRO_HTTP"))

    def test_api_fora_do_ar_e_timeout(self):
        with mock.patch("requests.request", side_effect=requests.exceptions.ConnectionError("recusada")):
            with self.assertRaises(ac.ApiIndisponivel):
                ac.health("http://x")
        with mock.patch("requests.request", side_effect=requests.exceptions.Timeout()):
            with self.assertRaises(ac.ApiIndisponivel) as cm:
                ac.status_modelo("http://x")
        self.assertIn("não respondeu", str(cm.exception))

    def test_lote_em_partes_preserva_ordem(self):
        def falsa(metodo, url, **kw):
            textos = kw["json"]["textos"]
            return resp(corpo={"resultados": [{"texto_processado": t} for t in textos]})
        textos = [f"t{i}" for i in range(70)]
        with mock.patch("requests.request", side_effect=falsa) as m:
            out = ac.processar_lote("http://x", textos)
        self.assertEqual([r["texto_processado"] for r in out], textos)
        self.assertEqual(m.call_count, 3)                                       # 32 + 32 + 6


if __name__ == "__main__":
    unittest.main()
