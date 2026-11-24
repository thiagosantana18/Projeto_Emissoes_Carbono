# Code/data_acquisition

| Script | Função |
|---|---|
| `scraping_utils.py` | robots.txt, sessão HTTP com retentativas, normalização de datas |
| `scrape_ods_ecycle.py` | trechos dos ODS 12/13 → `Data/raw/ods_conteudo.csv` |
| `scrape_noticias_esg.py` | manchetes ESG → `Data/raw/noticias_esg.csv` |
| `generate_sample_emissions.py` | dataset sintético → `Data/processed/amostra_emissoes.csv` |

Todos rodam **separados** do dashboard. Ordem completa: `python Scripts/atualizar_dados.py`.
Selenium não é usado (ADR-003 em `Docs/Project/Decision_Log.md`).
