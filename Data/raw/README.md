# Data/raw

Dados brutos, como coletados/recebidos. Não editar à mão.

| Arquivo | Origem | Gerado por | Versionado |
|---|---|---|---|
| `noticias_esg.csv` / `.txt` | manchetes de portal de notícias ESG | `Code/data_acquisition/scrape_noticias_esg.py` | sim |
| `ods_conteudo.csv` / `.txt` | trechos das páginas dos ODS 12/13 | `Code/data_acquisition/scrape_ods_ecycle.py` | sim |
| `emissoes_enviadas_api.csv` | registros recebidos via `POST /emissoes` | API (`App/api`) | **não** (dado de usuário) |

⚠️ Os arquivos de notícias/ODS que acompanham o projeto são uma **amostra** (as URLs de notícia apontam para a página de listagem). Rode os scrapers para obter uma coleta real e, depois, `build_corpus.py`.
Veja `NOTA_COLETA.md` para o histórico de como os dados foram obtidos.
