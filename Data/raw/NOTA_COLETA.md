# Nota sobre a execução dos scripts de coleta (scraping)

Os scripts `Code/data_acquisition/scrape_ods_ecycle.py` e
`Code/data_acquisition/scrape_noticias_esg.py` foram desenvolvidos com
**BeautifulSoup + requests**, seguindo as boas práticas:

1. Verificação do `robots.txt` do domínio-alvo via `urllib.robotparser`
   **antes** de qualquer requisição de conteúdo (função `pode_coletar()`).
2. Identificação por User-Agent próprio (não se disfarça de navegador).
3. Delay entre requisições (rate limiting educado).
4. Execução separada da aplicação Streamlit, salvando o resultado em
   `Data/raw/*.csv` e `Data/raw/*.txt`.

## Como reproduzir (recomendado)

Em uma máquina com acesso à internet:

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
bloco `if not pode_coletar(url): ...` em ambos os scripts).

## Correção aplicada (16/09/2026)

Uma inconsistência de schema foi identificada e corrigida: o script
`scrape_noticias_esg.py` originalmente **não gravava** a coluna
`data_publicacao` no CSV de saída (apenas `titulo`, `url_materia` e
`data_coleta`), enquanto `app.py` assumia que essa coluna sempre existiria.
Isso causava um `KeyError: 'data_publicacao'` ao rodar a aplicação com uma
coleta feita pelo script real.

Duas correções foram aplicadas:

1. **No script** (`scrape_noticias_esg.py`): agora tenta extrair a data de
   publicação de cada notícia (heurística best-effort, via tag `<time>` ou
   padrão de data no texto ao redor do link) e sempre grava a coluna
   `data_publicacao` no CSV — vazia quando não for possível extrair.
2. **No app** (`app.py`, função `carregar_noticias()`): tornado defensivo
   contra a ausência/valores vazios dessa coluna, preenchendo com
   `data_coleta` como fallback e nunca lançando `KeyError`, mesmo que o
   schema do CSV mude novamente no futuro.

Se já tinha rodado o script antigo, **não precisa** rodar de novo — o
app agora lida com o CSV antigo (sem `data_publicacao`) sem quebrar. Rodar
o script novamente é recomendado apenas para tentar capturar as datas de
publicação reais.

## Correção adicional (16/09/2026) — resolução automática de caminhos

O app passou a existir em dois layouts possíveis (na raiz do projeto ou
dentro de `App/dashboard/`), e cada versão que eu enviei fixava o número de
níveis até a pasta `Data/` de um jeito diferente. Isso causava a mensagem
"Nenhuma notícia encontrada" sempre que o arquivo `app.py` era movido de um
layout para o outro — mesmo com `Data/raw/noticias_esg.csv` devidamente
preenchido, porque o app procurava no lugar errado.

Corrigido com a função `localizar_raiz_projeto()` em `app.py`: agora o app
sobe a árvore de diretórios a partir de onde ele mesmo está e usa o primeiro
nível em que encontra uma pasta `Data/`. Funciona automaticamente nos dois
layouts, sem precisar editar nada.

Também foi adicionado um painel **"🔍 Diagnóstico de caminhos (debug)"** no
rodapé da aplicação, mostrando os caminhos resolvidos e se cada arquivo
esperado existe — útil para autodiagnóstico caso algo semelhante aconteça
de novo.
