# Code/data_acquisition

Scripts Python responsáveis pela coleta de dados externos.

## Scripts disponíveis

- **scrape_ods_ecycle.py** — coleta (via BeautifulSoup + requests) trechos de
  conteúdo público sobre os ODS 12 e 13 do portal eCycle. Verifica o
  `robots.txt` do domínio antes de qualquer requisição. Saída:
  `Data/raw/ods_conteudo.csv` e `.txt`.
- **scrape_noticias_esg.py** — coleta manchetes de notícias sobre ESG/pegada
  de carbono (metadados públicos: título, data, link). Também verifica o
  `robots.txt` antes de coletar. Saída: `Data/raw/noticias_esg.csv` e `.txt`.

Ambos os scripts rodam de forma independente da aplicação Streamlit —
"Execute esses códigos separadamente" — e não fazem nenhuma chamada de rede
quando importados, apenas quando executados via `python script.py`.

Ver `Data/raw/NOTA_COLETA.md` para detalhes sobre como os dados atuais em
`Data/raw/` foram obtidos e como reproduzir a coleta.

## Como rodar

```bash
pip install -r requirements.txt
python Code/data_acquisition/scrape_ods_ecycle.py
python Code/data_acquisition/scrape_noticias_esg.py
```
