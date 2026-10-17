"""
Gerador (reprodutível) do dataset SINTÉTICO de atividade/emissões.

Cada unidade possui um perfil de atividades; as quantidades mensais seguem
tendência + sazonalidade + ruído. Os fatores de emissão são VALORES DE
REFERÊNCIA FIXOS rotulados com a fonte de origem — a integração com a
Climatiq API (consulta real) é uma etapa futura do projeto.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .validation import COLUNAS_EMISSOES, calcular_emissao

# unidade -> (setor, [atividades])
PERFIL_UNIDADES = {
    "Matriz - SP": ("Administrativo", ["Eletricidade (rede)", "Gasolina (frota leve)"]),
    "Filial - RJ": ("Logística", ["Eletricidade (rede)", "Diesel (frota)"]),
    "Filial - MG": ("Produção", ["Eletricidade (rede)", "Gás natural (caldeira)", "Diesel (frota)"]),
    "CD - PR": ("Logística", ["Eletricidade (rede)", "Diesel (frota)"]),
}
# atividade -> (unidade_medida, fator kgCO2e/un, fonte_fator, qtd_base_mensal, amplitude_sazonal)
ATIVIDADES = {
    "Eletricidade (rede)": ("kWh", 0.0817, "Climatiq API", 9000.0, 0.12),
    "Diesel (frota)": ("litro", 2.6712, "EPA", 1800.0, 0.05),
    "Gasolina (frota leve)": ("litro", 2.2120, "EPA", 700.0, 0.04),
    "Gás natural (caldeira)": ("m3", 1.9700, "DEFRA", 2500.0, 0.10),
}
ESCALA_UNIDADE = {"Matriz - SP": 1.0, "Filial - RJ": 0.8, "Filial - MG": 1.4, "CD - PR": 1.1}


def gerar_amostra_emissoes(n_meses: int = 24, fim: str = "2026-09", seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    meses = pd.period_range(end=fim, periods=n_meses, freq="M")
    linhas = []
    for t, mes in enumerate(meses):
        sazonal_fase = np.cos(2 * np.pi * (mes.month - 1) / 12)  # pico em janeiro (verão no Brasil)
        tendencia = 1 + 0.004 * t
        for unidade, (setor, atividades) in PERFIL_UNIDADES.items():
            for atividade in atividades:
                un_medida, fator, fonte, base, amp = ATIVIDADES[atividade]
                ruido = rng.lognormal(mean=0.0, sigma=0.06)
                qtd = base * ESCALA_UNIDADE[unidade] * tendencia * (1 + amp * sazonal_fase) * ruido
                qtd = round(float(qtd), 1)
                linhas.append({
                    "mes_referencia": str(mes),
                    "unidade": unidade,
                    "setor": setor,
                    "tipo_atividade": atividade,
                    "quantidade": qtd,
                    "unidade_medida": un_medida,
                    "fator_emissao_kgco2e": fator,
                    "emissao_kgco2e": calcular_emissao(qtd, fator),
                    "fonte_fator": fonte,
                })
    return pd.DataFrame(linhas, columns=COLUNAS_EMISSOES)
