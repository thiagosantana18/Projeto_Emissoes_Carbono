"""Testes dos clientes de IA online com respostas HTTP SIMULADAS (nenhuma chamada real, nenhuma chave necessária)."""
import copy
import os
import tempfile
import unittest
from pathlib import Path

import _setup  # noqa: F401
import requests

from esg_core.env import carregar_dotenv
from esg_core.ia import errors as E
from esg_core.ia.config import ConfigIA, carregar_config_ia
from esg_core.ia.provedores import ClienteAnthropic, ClienteOpenAI, criar_cliente, redigir_segredos


class Resp:
    def __init__(self, status=200, corpo=None, headers=None, texto=""):
        self.status_code, self.headers, self.text, self._c = status, headers or {}, texto, corpo

    def json(self):
        if self._c is None:
            raise ValueError("sem json")
        return self._c


class HttpFalso:
    def __init__(self, *respostas):
        self.respostas, self.chamadas = list(respostas), []

    def post(self, url, headers=None, json=None, timeout=None):
        self.chamadas.append({"url": url, "headers": headers, "json": copy.deepcopy(json), "timeout": timeout})
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def ok_openai(texto='{"a": 1}', fim="stop"):
    return Resp(200, {"choices": [{"message": {"content": texto}, "finish_reason": fim}],
                      "usage": {"prompt_tokens": 120, "completion_tokens": 40}})


def ok_anthropic(texto='{"a": 1}'):
    return Resp(200, {"content": [{"type": "text", "text": texto}], "stop_reason": "end_turn",
                      "usage": {"input_tokens": 90, "output_tokens": 30}})


def cfg(**kw):
    base = dict(openai_chave="sk-teste-1234567890", anthropic_chave="sk-ant-teste-1234567890", retentativas=2)
    base.update(kw)
    return ConfigIA(**base)


def cliente(cls, http, dormidas=None, **kw):
    return cls(cfg(**kw), http, dormir=(dormidas.append if dormidas is not None else (lambda s: None)))


class OpenAITests(unittest.TestCase):
    def test_requisicao_e_resposta(self):
        http = HttpFalso(ok_openai())
        r = cliente(ClienteOpenAI, http).gerar("sistema", "usuario", max_tokens=777)
        c = http.chamadas[0]
        self.assertEqual(c["url"], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(c["headers"]["Authorization"], "Bearer sk-teste-1234567890")
        self.assertEqual(c["json"]["max_completion_tokens"], 777)
        self.assertNotIn("max_tokens", c["json"])
        self.assertNotIn("temperature", c["json"])                       # só enviada se configurada
        self.assertEqual([m["role"] for m in c["json"]["messages"]], ["system", "user"])
        self.assertEqual((r.texto, r.tokens_entrada, r.tokens_saida, r.provedor, r.truncada), ('{"a": 1}', 120, 40, "openai", False))

    def test_temperatura_rejeitada_e_removida(self):
        erro = Resp(400, {"error": {"message": "Unsupported value: 'temperature' does not support 0.2 with this model.", "code": "unsupported_value"}})
        http = HttpFalso(erro, ok_openai())
        r = cliente(ClienteOpenAI, http, temperatura=0.2).gerar("s", "u")
        self.assertEqual(http.chamadas[0]["json"]["temperature"], 0.2)
        self.assertNotIn("temperature", http.chamadas[1]["json"])
        self.assertEqual(r.tentativas, 1)                                 # adaptação não gasta retentativa

    def test_servidor_antigo_troca_parametro_de_tokens(self):
        erro = Resp(400, {"error": {"message": "Unsupported parameter: 'max_completion_tokens'"}})
        http = HttpFalso(erro, ok_openai())
        cliente(ClienteOpenAI, http).gerar("s", "u", 50)
        self.assertEqual(http.chamadas[1]["json"]["max_tokens"], 50)

    def test_retentativa_429_com_retry_after_e_5xx(self):
        dormidas = []
        http = HttpFalso(Resp(429, {"error": {"message": "slow down", "code": "rate_limit_exceeded"}}, {"retry-after": "3"}),
                         Resp(503, {"error": {"message": "overloaded"}}), ok_openai())
        r = cliente(ClienteOpenAI, http, dormidas).gerar("s", "u")
        self.assertEqual((r.tentativas, dormidas), (3, [3.0, 2 ** 1]))
        self.assertEqual(len(http.chamadas), 3)

    def test_esgota_retentativas(self):
        http = HttpFalso(*[Resp(429, {"error": {"message": "x"}}, {"retry-after": "7"})] * 3)
        with self.assertRaises(E.IALimiteTaxaError) as cm:
            cliente(ClienteOpenAI, http).gerar("s", "u")
        self.assertEqual((cm.exception.status_code, cm.exception.retry_after), (429, 7))
        http = HttpFalso(*[Resp(500, {"error": {"message": "boom"}})] * 3)
        with self.assertRaises(E.IAProvedorError) as cm:
            cliente(ClienteOpenAI, http).gerar("s", "u")
        self.assertEqual(cm.exception.status_code, 502)

    def test_erros_definitivos_nao_repetem(self):
        casos = [
            (Resp(401, {"error": {"message": "Incorrect API key provided: sk-teste-1234567890"}}), E.IACredencialError, 503),
            (Resp(429, {"error": {"message": "You exceeded your current quota", "code": "insufficient_quota"}}), E.IACotaError, 503),
            (Resp(404, {"error": {"message": "The model `x` does not exist"}}), E.IAProvedorError, 502),
            (Resp(400, {"error": {"message": "bad request"}}), E.IAProvedorError, 502),
        ]
        for resp, exc, status in casos:
            with self.subTest(resp.status_code):
                http = HttpFalso(resp)
                with self.assertRaises(exc) as cm:
                    cliente(ClienteOpenAI, http).gerar("s", "u")
                self.assertEqual((len(http.chamadas), cm.exception.status_code), (1, status))
                self.assertNotIn("sk-teste-1234567890", cm.exception.mensagem)          # chave redigida

    def test_timeout_e_rede(self):
        http = HttpFalso(*[requests.exceptions.Timeout()] * 3)
        with self.assertRaises(E.IATempoLimiteError) as cm:
            cliente(ClienteOpenAI, http).gerar("s", "u")
        self.assertEqual(cm.exception.status_code, 504)
        http = HttpFalso(requests.exceptions.ConnectionError("dns"), ok_openai())
        self.assertEqual(cliente(ClienteOpenAI, http).gerar("s", "u").tentativas, 2)

    def test_saidas_problematicas(self):
        with self.assertRaises(E.IARespostaInvalidaError) as cm:                         # raciocínio consumiu os tokens
            cliente(ClienteOpenAI, HttpFalso(ok_openai("", "length"))).gerar("s", "u")
        self.assertIn("ESG_IA_MAX_TOKENS", cm.exception.sugestao)
        with self.assertRaises(E.IARespostaInvalidaError):
            cliente(ClienteOpenAI, HttpFalso(Resp(200, {"choices": [{"message": {"refusal": "não posso", "content": None}}]}))).gerar("s", "u")
        with self.assertRaises(E.IARespostaInvalidaError):
            cliente(ClienteOpenAI, HttpFalso(Resp(200, {"sem": "choices"}))).gerar("s", "u")
        with self.assertRaises(E.IARespostaInvalidaError):
            cliente(ClienteOpenAI, HttpFalso(Resp(200, None))).gerar("s", "u")
        r = cliente(ClienteOpenAI, HttpFalso(ok_openai('{"parcial": ', "length"))).gerar("s", "u")
        self.assertTrue(r.truncada)                                                      # texto parcial é devolvido, marcado

    def test_servidor_local_compativel_nao_exige_chave(self):
        c = ConfigIA(openai_base_url="http://localhost:11434/v1", openai_modelo="llama3.2")
        self.assertTrue(c.configurado("openai"))
        http = HttpFalso(ok_openai())
        ClienteOpenAI(c, http).gerar("s", "u")
        self.assertEqual(http.chamadas[0]["url"], "http://localhost:11434/v1/chat/completions")


class AnthropicTests(unittest.TestCase):
    def test_requisicao_e_resposta(self):
        http = HttpFalso(ok_anthropic())
        r = cliente(ClienteAnthropic, http).gerar("sistema", "usuario", 500)
        c = http.chamadas[0]
        self.assertEqual(c["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual((c["headers"]["x-api-key"], c["headers"]["anthropic-version"]), ("sk-ant-teste-1234567890", "2023-06-01"))
        self.assertEqual((c["json"]["system"], c["json"]["max_tokens"], c["json"]["model"]), ("sistema", 500, "claude-haiku-5-5"))
        self.assertEqual(c["json"]["messages"], [{"role": "user", "content": "usuario"}])
        self.assertEqual((r.tokens_entrada, r.tokens_saida, r.provedor), (90, 30, "anthropic"))

    def test_erros(self):
        with self.assertRaises(E.IACredencialError):
            cliente(ClienteAnthropic, HttpFalso(Resp(401, {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}))).gerar("s", "u")
        with self.assertRaises(E.IACotaError):
            cliente(ClienteAnthropic, HttpFalso(Resp(400, {"type": "error", "error": {"type": "invalid_request_error", "message": "Your credit balance is too low"}}))).gerar("s", "u")
        http = HttpFalso(Resp(529, {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}), ok_anthropic())
        self.assertEqual(cliente(ClienteAnthropic, http).gerar("s", "u").tentativas, 2)
        with self.assertRaises(E.IARespostaInvalidaError):
            cliente(ClienteAnthropic, HttpFalso(Resp(200, {"content": []}))).gerar("s", "u")


class ConfigTests(unittest.TestCase):
    def test_fabrica(self):
        with self.assertRaises(E.IANaoConfiguradaError) as cm:
            criar_cliente(ConfigIA())
        self.assertIn("OPENAI_API_KEY", cm.exception.sugestao)
        self.assertIsInstance(criar_cliente(ConfigIA(anthropic_chave="k")), ClienteAnthropic)    # cai no provedor configurado
        self.assertIsInstance(criar_cliente(cfg(), "anthropic"), ClienteAnthropic)
        self.assertIsInstance(criar_cliente(cfg()), ClienteOpenAI)
        with self.assertRaises(E.TextoInvalidoError):
            criar_cliente(cfg(), "gemini")

    def test_chaves_nao_vazam_no_repr(self):
        self.assertNotIn("sk-teste", repr(cfg()))
        self.assertEqual(redigir_segredos("erro com sk-abc123456789 e Bearer abcdefgh12345"), "erro com *** e ***")

    def test_env(self):
        ambiente = {"ESG_IA_PROVIDER": "ANTHROPIC", "ANTHROPIC_API_KEY": "k", "ESG_IA_TEMPERATURA": "0.3",
                    "ESG_IA_MAX_TOKENS": "10", "ESG_IA_TIMEOUT": "abc", "ESG_IA_CACHE": "0"}
        antigo = {k: os.environ.get(k) for k in list(ambiente) + ["OPENAI_API_KEY"]}
        try:
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.update(ambiente)
            c = carregar_config_ia()
        finally:
            for k, v in antigo.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.assertEqual((c.provedor_padrao, c.temperatura, c.max_tokens, c.timeout_s, c.cache_ativo), ("anthropic", 0.3, 256, 90.0, False))
        self.assertEqual(c.provedor_efetivo(), "anthropic")

    def test_dotenv_nao_sobrescreve(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text('# comentário\nESG_TESTE_A=1\nESG_TESTE_B="com aspas"\nESG_TESTE_C=valor # nota\nESG_TESTE_D=\n', encoding="utf-8")
            os.environ["ESG_TESTE_A"] = "ja-existe"
            try:
                n = carregar_dotenv(p)
                self.assertEqual((os.environ["ESG_TESTE_A"], os.environ["ESG_TESTE_B"], os.environ["ESG_TESTE_C"]), ("ja-existe", "com aspas", "valor"))
                self.assertEqual((n, "ESG_TESTE_D" in os.environ), (2, False))
            finally:
                for k in ("ESG_TESTE_A", "ESG_TESTE_B", "ESG_TESTE_C"):
                    os.environ.pop(k, None)


if __name__ == "__main__":
    unittest.main()
