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

## Etapa 4 — LLM local, API robusta e dashboard consumindo a API

## ADR-009 — Modelo: DistilBERT multilíngue de sentimento
**Decisão.** `lxyuan/distilbert-base-multilingual-cased-sentiments-student` (≈135 M parâmetros, Apache-2.0, português incluído, rótulos
positive/neutral/negative), para **classificação de sentimento**. **Motivo.** Máquina modesta + protótipo; a tarefa casa com os dados que temos
(manchetes) e com o gabarito. Resumo e geração exigem modelos maiores e dados que ainda não existem. Comparação e matriz de decisão em
`LLM_Model_Selection.md`. **Ressalva.** O cartão reporta concordância com o professor (88,29 %), não acurácia contra humanos: a qualidade em manchetes
ESG é **desconhecida** até rotularmos o gabarito. Honestidade de terminologia: é um modelo de linguagem *encoder* pequeno, não um LLM generativo.

## ADR-010 — Execução local, offline por padrão, carga preguiçosa
`transformers` + `torch` (CPU) em `Models/hf_cache` (fora do Git). A API **nunca baixa** o modelo durante uma requisição (`ESG_LLM_OFFLINE=1`);
o download é um passo explícito (`Code/llm/baixar_modelo.py`). Carga na primeira chamada (ou `POST /modelo/carregar`, ou `ESG_LLM_PRELOAD=1`),
protegida por lock. Dependências pesadas ficam em `requirements-llm.txt`: sem elas, API e dashboard funcionam e as rotas de LLM respondem 503 com instrução.

## ADR-011 — Robustez em máquina modesta
Uma thread de inferência, timeout (504), fila de no máx. 4 pendentes (429), espera de 30 s após falha de carga, limites de 2000 caracteres / 256 tokens / 32 textos.
Limitação assumida: um timeout não aborta a thread; ela termina e libera a vaga depois.

## ADR-012 — Envelope de erro único e Response Models
Todo erro (validação, 404/405, falhas do modelo, exceção inesperada) sai como `{codigo, mensagem, detalhes, sugestao, request_id}` + `X-Request-ID`.
Mensagens de validação do Pydantic são traduzidas e **não ecoam o valor enviado**; exceções inesperadas não vazam traceback. As respostas de sucesso
são Response Models Pydantic e a saída do modelo é validada antes (rótulos, [0,1], soma ≈ 1). **Mudança de contrato:** o campo `detail` do FastAPI deixou de existir
(agora `mensagem`/`detalhes`) em todas as rotas; o dashboard foi ajustado.

## ADR-013 — O dashboard consome a API
A página principal (*Dados e gráficos*) lê `GET /emissoes` e a página *Análise de texto* usa `POST /processar_texto` e `/lote`. Há alternância API/LOCAL e **fallback
automático** para os arquivos locais (com aviso visível) quando a API está fora do ar. Cache de 20 s com botão de atualização. As demais páginas ainda leem os arquivos
diretamente — migração gradual.

## ADR-014 — Testabilidade sem o modelo
O serviço recebe o "carregador" por injeção; os testes usam um pipeline falso (nada é baixado). Assim a lógica de erros, timeout, fila e validação é testada em qualquer máquina.
O que **não** é coberto por teste automático: a inferência real com o modelo (use `Code/llm/verificar_modelo.py`).

## ADR-015 — Remoção de arquivos legados
`App/dashboard/README_app.md` e `Code/genai_reporting/README.md` descreviam uma estrutura que não existe mais. Já não constam do projeto entregue, mas extrair um zip
por cima de uma pasta antiga não apaga arquivos: `Scripts/remover_legados.py` lista (e, com `--executar`, remove) esses resíduos. `Code/genai_reporting` foi unificada em `Code/llm` + `Code/esg_core/llm`.

## Lições aprendidas
1. **Schema drift** entre scraper e app derrubou o dashboard → loaders defensivos + teste de regressão.
2. **Duas versões do mesmo arquivo** com caminhos diferentes causaram "dados não encontrados" → uma só versão e raiz detectada automaticamente.
3. **Testar só a lógica "feliz" não basta**: o teste do corpus revelou que preencher data de publicação com data de coleta enganaria citações futuras.
4. **Extrair um zip por cima de um projeto não remove o que foi apagado** → resíduos contraditórios; criamos `remover_legados.py` e passamos a listar remoções no CHANGELOG.
5. **Não afirmar o que não foi medido:** requisitos de hardware e latência do modelo estão marcados como estimativa até rodar `verificar_modelo.py`.
6. **Dependência opcional pesada = isolar:** `requirements-llm.txt` + carga preguiçosa mantêm o restante do projeto leve e utilizável.
