# Registro de decisões (Etapa 3)

Formato: contexto → decisão → consequências. Complementa o Project Charter v3.

## ADR-001 — Camada de dados compartilhada (`Code/esg_core`)
**Contexto.** Dashboard, API e scripts precisavam ler os mesmos CSV; antes cada um tinha seu próprio código (e já houve
dois bugs por divergência: `KeyError: 'data_publicacao'` e `app.py` procurando `Data/` no lugar errado).
**Decisão.** Um pacote sem dependência de Streamlit/FastAPI, com caminhos centralizados (`paths.py`), loaders com schema
defensivo (`data_access.py`), validação (`validation.py`), texto e corpus. Dashboard e API importam dele.
**Consequências.** Regra escrita uma vez e testada sem framework (30 testes). Os entrypoints precisam adicionar `Code/` ao `sys.path`.

## ADR-002 — Streamlit multipágina com `st.navigation`
**Decisão.** 7 páginas em `App/dashboard/views/`, agrupadas em 4 seções no menu. Pasta chamada `views/` (e não `pages/`) para não
acionar o modo automático do Streamlit. Filtros persistem entre páginas reatribuindo o estado a cada execução (`manter_estado`).
Cache com chave = data de modificação dos arquivos (muda o CSV → cache invalida sozinho). Gráficos com Plotly.

## ADR-003 — Selenium NÃO adotado nesta fase
**Contexto.** O enunciado pede Selenium apenas se houver conteúdo dinâmico (formulários, carregamento assíncrono).
**Avaliação.** As duas fontes de scraping (páginas dos ODS no eCycle e listagem ESG da Exame) entregam as manchetes/trechos no HTML
inicial — os scrapers com BeautifulSoup populam os CSV na prática. As demais fontes são API (Climatiq) ou download direto (SEEG, EPA, DEFRA).
**Decisão.** Manter requests + BeautifulSoup e investir no aprimoramento dos dados: separação rede/parsing (testável offline), filtros de
relevância, deduplicação, novas colunas (`fonte`, `resumo`, `tags`, `secao`), retentativas e logging.
**Quando reavaliar (gatilhos).** (a) scraper devolve 0 itens mas a página mostra conteúdo no navegador; (b) a fonte exige clique/formulário/rolagem
infinita e **não** há API ou download oficial; (c) o `robots.txt` e os termos permitem. Antes de Selenium, procurar o endpoint JSON que a página chama.
**Custos evitados.** Driver de navegador, execução lenta, fragilidade e dependência extra.

## ADR-004 — API FastAPI simples, sem autenticação
**Decisão.** 9 operações (ver `Docs/API/API_Documentation.md`): GET/POST de emissões, resumo, lote, e GETs de textos/corpus. Validação com
Pydantic v2 (422 em dados inválidos). Escrita por *append* em `Data/raw/emissoes_enviadas_api.csv`, protegida por lock de processo.
**Consequências.** Sem autenticação nem controle de concorrência entre processos: **somente protótipo local**. Próximos passos: chave de API,
banco de dados, idempotência.

## ADR-005 — Dataset sintético enriquecido
**Contexto.** A amostra anterior tinha 1 linha por mês, insuficiente para gráficos úteis e para a modelagem futura.
**Decisão.** 24 meses × 9 pares unidade/atividade = 216 linhas, com tendência, sazonalidade e ruído (seed fixa).
**Ressalva.** Os fatores de emissão são **valores de referência fixos rotulados por fonte** (Climatiq/EPA/DEFRA); ainda **não** há consulta
real à Climatiq API. Isso está declarado no dicionário de dados e no contexto de relatório.

## ADR-006 — Corpus JSONL e rastreabilidade
**Decisão.** `corpus_llm.jsonl` unifica notícias e trechos de ODS (doc_id, fonte, url, data, tags, usos previstos). **Data de coleta nunca vira
data de publicação no corpus** (o app usa o fallback apenas para exibir/ordenar). `contexto_relatorio.json` guarda agregados numéricos para
geração de texto com checagem de fidelidade. Gabaritos de avaliação ficam em `Data/processed/avaliacao/`.
**Direitos autorais.** Notícias: só metadados (título, link, data, linha fina ≤ 280 caracteres). ODS: trechos ≤ 600 caracteres.

## ADR-007 — Versionamento de dados (.gitignore)
Versionados: amostras pequenas necessárias para rodar/reproduzir (raw de scraping, processed). Não versionados: dados enviados por usuários
via API, `interim/`, `external/` (licenças próprias), binários pesados, `.env`. **Atenção:** se o repositório for público, avalie remover
`Data/raw/ods_conteudo.*` do versionamento (texto de terceiros).

## ADR-008 — Testes
`unittest` (stdlib) para rodar sem dependências extras; compatível com `pytest`. Cobrem validação, acesso a dados (incluindo regressão do
`KeyError`), corpus, parsing dos scrapers com HTML de exemplo, e a API (pulada se FastAPI/httpx ausentes).

## Lições aprendidas
1. **Schema drift** entre scraper e app derrubou o dashboard → loaders defensivos + teste de regressão.
2. **Duas versões do mesmo arquivo** com caminhos diferentes causaram "dados não encontrados" → uma só versão e raiz detectada automaticamente.
3. **Testar só a lógica "feliz" não basta**: o teste do corpus revelou que preencher data de publicação com data de coleta enganaria citações futuras.
