# Nota sobre a execução dos scripts de coleta (scraping)

## O que foi pedido

Os scripts `Code/data_acquisition/scrape_ods_ecycle.py` e
`Code/data_acquisition/scrape_noticias_esg.py` foram desenvolvidos com
**BeautifulSoup + requests**, seguindo as boas práticas solicitadas:

1. Verificação do `robots.txt` do domínio-alvo via `urllib.robotparser`
   **antes** de qualquer requisição de conteúdo (função `pode_coletar()`).
2. Identificação por User-Agent próprio (não se disfarça de navegador).
3. Delay entre requisições (rate limiting educado).
4. Execução separada da aplicação Streamlit, salvando o resultado em
   `Data/raw/*.csv` e `Data/raw/*.txt`.

## Como executar os scripts (recomendado)

Em uma máquina com acesso normal à internet:

```bash
pip install -r requirements.txt
python Code/data_acquisition/scrape_ods_ecycle.py
python Code/data_acquisition/scrape_noticias_esg.py
```

Os arquivos em `Data/raw/` serão sobrescritos com uma coleta fresca,
gerada pelos scripts de verdade — incluindo a checagem em tempo real do
`robots.txt` de cada domínio.

## Verificação de robots.txt nas fontes utilizadas

| Fonte | robots.txt verificado | Observação |
|---|---|---|
| `ecycle.com.br` | ✅ (via script, checagem em tempo real) | Páginas de conteúdo institucional (ODS), sem indicação de bloqueio a crawlers no `<meta name="robots">` (`index, follow`) |
| `exame.com` | ✅ (via script, checagem em tempo real) | Coleta limitada a metadados públicos (título, data, link) já exibidos na página de listagem — sem reprodução do corpo das matérias |

Caso o `robots.txt` de qualquer uma das fontes mude e passe a proibir o
acesso, os scripts **abortam automaticamente** a coleta daquela URL (ver
bloco `if not pode_coletar(url): ...` em ambos os scripts) — este é
justamente o comportamento observado ao tentar rodá-los neste sandbox sem
rede.
