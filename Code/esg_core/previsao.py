"""
Previsão de emissões mensais — linha de base transparente (sem bibliotecas de séries temporais).

Três métodos comparados por backtest com origem móvel:
  * ingenuo           — repete o último mês;
  * sazonal_ingenuo   — repete o mesmo mês do ano anterior;
  * tendencia_sazonal — tendência linear + índice sazonal multiplicativo por mês do ano (ajustados iterativamente).
O melhor (menor MAPE) gera a previsão final; a faixa é aproximada, a partir da dispersão dos erros relativos do backtest.
ATENÇÃO: com dados sintéticos o resultado demonstra o método, não a capacidade de prever uma empresa real.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

META_MAPE = 15.0
MIN_MESES = 15


def serie_mensal(df: pd.DataFrame) -> pd.Series:
    """Soma mensal de emissões (kgCO2e). Meses sem registro são interpolados linearmente."""
    s = df.groupby("mes_referencia")["emissao_kgco2e"].sum().sort_index()
    s.index = pd.PeriodIndex(s.index, freq="M")
    s = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"))
    return s.interpolate().astype(float)


def _ingenuo(y, meses, h):
    return np.full(h, y[-1])


def _sazonal_ingenuo(y, meses, h):
    if len(y) < 12:
        return _ingenuo(y, meses, h)
    return np.array([y[len(y) - 12 + (i % 12)] for i in range(h)])


def _tendencia_sazonal(y, meses, h):
    n = len(y)
    if n < 12:
        return _ingenuo(y, meses, h)
    t = np.arange(n)
    idx = np.ones(12)
    for _ in range(3):
        coef = np.polyfit(t, y / idx[meses - 1], 1)
        razoes = y / np.polyval(coef, t)
        idx = np.array([razoes[meses == m].mean() if (meses == m).any() else 1.0 for m in range(1, 13)])
        idx = idx / idx.mean()
    t_fut = np.arange(n, n + h)
    meses_fut = (meses[-1] - 1 + 1 + np.arange(h)) % 12 + 1
    return np.polyval(coef, t_fut) * idx[meses_fut - 1]


METODOS = {"ingenuo": _ingenuo, "sazonal_ingenuo": _sazonal_ingenuo, "tendencia_sazonal": _tendencia_sazonal}


def backtest(serie: pd.Series, horizonte: int = 3, min_treino: int = 12) -> dict:
    y = serie.values
    meses = np.array([p.month for p in serie.index])
    saida = {}
    for nome, fn in METODOS.items():
        pct, quad = [], []
        for k in range(min_treino, len(y) - horizonte + 1):
            prev = fn(y[:k], meses[:k], horizonte)
            real = y[k:k + horizonte]
            pct += list((prev - real) / real * 100)
            quad += list((prev - real) ** 2)
        saida[nome] = {"mape": round(float(np.mean(np.abs(pct))), 2), "rmse": round(float(np.sqrt(np.mean(quad))), 2),
                       "n_previsoes": len(pct), "desvio_erro_pct": float(np.std(pct))}
    return saida


def prever_emissoes(df: pd.DataFrame, horizonte: int = 6, horizonte_backtest: int = 3) -> dict:
    s = serie_mensal(df)
    if len(s) < MIN_MESES:
        raise ValueError(f"São necessários ao menos {MIN_MESES} meses de dados para prever (há {len(s)}).")
    bt = backtest(s, horizonte_backtest, min_treino=MIN_MESES - horizonte_backtest)
    ranking = sorted(({"metodo": k, **{c: v[c] for c in ("mape", "rmse", "n_previsoes")}} for k, v in bt.items()), key=lambda x: x["mape"])
    melhor = ranking[0]["metodo"]
    y, meses = s.values, np.array([p.month for p in s.index])
    prev = METODOS[melhor](y, meses, horizonte)
    faixa = max(1.28 * bt[melhor]["desvio_erro_pct"] / 100, 0.02)
    ultimo = s.index[-1]
    return {
        "serie": {"inicio": str(s.index[0]), "fim": str(ultimo), "n_meses": len(s)},
        "historico": [{"mes": str(p), "kgco2e": round(float(v), 2)} for p, v in s.items()],
        "metodos": ranking, "melhor": melhor, "mape_melhor": ranking[0]["mape"],
        "meta_mape": META_MAPE, "atinge_meta": ranking[0]["mape"] < META_MAPE,
        "previsoes": [{"mes": str(ultimo + i + 1), "previsto": round(float(v), 2),
                       "min": round(float(v) * (1 - faixa), 2), "max": round(float(v) * (1 + faixa), 2)} for i, v in enumerate(prev)],
        "intervalo": f"faixa aproximada (±{faixa * 100:.1f}%) a partir da dispersão dos erros do backtest",
        "avisos": ["Série curta: poucos ciclos sazonais para validar o método." if len(s) < 30 else "",
                   "Previsão sobre dados sintéticos quando a base for a amostra do projeto."],
    }
