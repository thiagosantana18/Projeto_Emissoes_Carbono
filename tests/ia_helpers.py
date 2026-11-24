"""Dublês compartilhados pelos testes de IA: um cliente de LLM roteirizado (sem rede)."""
import json

from esg_core.ia.provedores import RespostaLLM


class ClienteFalso:
    provedor, modelo = "openai", "modelo-falso"

    def __init__(self, *respostas, funcao=None):
        """`funcao(usuario) -> resposta` é usada quando a fila roteirizada esgota (útil para volumes variáveis)."""
        self.respostas, self.chamadas, self.funcao = list(respostas), [], funcao

    def gerar(self, sistema, usuario, max_tokens=None):
        self.chamadas.append({"sistema": sistema, "usuario": usuario, "max_tokens": max_tokens})
        r = self.respostas.pop(0) if self.respostas else self.funcao(usuario)
        if isinstance(r, Exception):
            raise r
        if isinstance(r, RespostaLLM):
            return r
        texto = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        return RespostaLLM(texto, self.provedor, self.modelo, 100, 50, "stop", 1, 10.0)


def sumario(resumo="A empresa reduziu 91% das emissões (d1).", fontes=("d1",), **extra):
    base = {"resumo_executivo": resumo, "pontos_chave": ["Redução de 91% (d1)."],
            "riscos_e_oportunidades": [{"tipo": "oportunidade", "descricao": "Neutralidade em 2035.", "fontes": list(fontes)}],
            "recomendacoes": [{"acao": "Acompanhar metas.", "justificativa": "Meta 2035 (d1).", "ods": "13"}],
            "lacunas": ["Custo não informado."], "fontes_citadas": list(fontes)}
    base.update(extra)
    return base
