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

## Etapa 5 — IA online, sumarização, dashboard final

## ADR-016 — LLM online por HTTP puro, com provedores intercambiáveis
OpenAI (Chat Completions; padrão `gpt-5-mini`) e Anthropic (Messages; padrão `claude-haiku-5-5`) por `requests`, sem SDKs: menos dependências e comportamento explícito e testável.
Modelos de raciocínio recusam `max_tokens` e `temperature` customizado → enviamos `max_completion_tokens` e só enviamos `temperature` se configurada; se o modelo recusar (400), o parâmetro é ajustado e a chamada refeita.
`ESG_OPENAI_BASE_URL` permite servidores compatíveis (Ollama, LM Studio) — cobre o uso de **modelo local** pela mesma interface. Nomes de modelo são configuráveis (mudam com o tempo; confirmar na página do provedor).

## ADR-017 — Chaves só no servidor
O dashboard nunca vê a chave: fala com a API, que fala com o provedor. Chaves vêm de `.env` (fora do Git) ou do ambiente; `repr`/logs/erros nunca as exibem (redação de padrões `sk-…`/`Bearer …`); `/ia/status` informa só "configurado: sim/não".

## ADR-018 — Prompts versionados, saída JSON validada, um reparo
Prompts em `esg_core/ia/prompts.py` com versão (`sumario_v2`, `qa_v1`, `insights_v1`); `sumario_v1` (texto livre) fica como linha de base para comparação. Saída em JSON com esquema no prompt, validada por código; JSON inválido → **uma** nova tentativa; truncada → erro claro (não repete).

## ADR-019 — Verificação de fidelidade em toda saída
Todo número do texto gerado precisa existir na fonte (normalizando pt-BR/en-US/%); toda citação precisa ser de um documento enviado. Falha vira alerta visível (`fidelidade.ok = false`) e a saída **não é cacheada**. Conservador: números derivados também são sinalizados.
Limite: não detecta afirmações qualitativas erradas.

## ADR-020 — Map-reduce para grandes volumes e relatórios em PDF
Texto > 24.000 caracteres (ou muitos documentos) → resumos parciais por lote + resumo final citando os ids originais; máximo de 8 lotes. Upload aceita TXT/MD/PDF (`pypdf`, opcional; PDF escaneado é detectado e avisado).

## ADR-021 — Perguntas e respostas: BM25 lexical + abstenção
Recuperação BM25 (sem acentos, radical simples do português) sobre corpus + texto de contexto das emissões. **Sem trecho relevante, o LLM não é chamado.** Embeddings ficam para quando o corpus crescer (custo e complexidade não se justificam com 28 documentos).

## ADR-022 — Custo e governança
Cache em disco por hash (mesma análise não é cobrada duas vezes), limite local de chamadas/hora (429 `IA_LIMITE_LOCAL`), limites de tamanho e de documentos, e **auditoria JSONL** (tipo, modelo, versão do prompt, tokens, fidelidade, trecho da saída) **sem gravar a entrada**.

## ADR-023 — Previsão: baseline estatístico com backtest
Três métodos transparentes (ingênuo, sazonal ingênuo, tendência + sazonalidade) comparados por backtest com origem móvel; faixa aproximada pela dispersão dos erros. Prophet/SARIMA descartados por ora: 24 pontos não justificam a complexidade; reavaliar com ≥ 36 meses reais.

## ADR-024 — Documentos que se geram a partir dos dados
`Scripts/gerar_relatorio_qualidade.py` (Data Quality Report) e `Scripts/gerar_evidencias_ia.py` (Evidencias_IA.md com saídas reais) mantêm os documentos alinhados aos dados e ao provedor reais, em vez de texto escrito à mão.

## ADR-025 — Dashboard final organizado pelo ciclo de dados
Página **Ciclo de dados** (6 etapas com números reais) e quatro páginas de IA (Resumos, Perguntas, Insights e previsão, Sentimento local). A página "Preparação dos dados para LLM" foi absorvida pelo Ciclo de dados (removida). Páginas de IA consomem a API; erros do provedor aparecem com a ação sugerida.

## Lições aprendidas
1. **Schema drift** entre scraper e app derrubou o dashboard → loaders defensivos + teste de regressão.
2. **Duas versões do mesmo arquivo** com caminhos diferentes causaram "dados não encontrados" → uma só versão e raiz detectada automaticamente.
3. **Testar só a lógica "feliz" não basta**: o teste do corpus revelou que preencher data de publicação com data de coleta enganaria citações futuras.
4. **Extrair um zip por cima de um projeto não remove o que foi apagado** → resíduos contraditórios; criamos `remover_legados.py` e passamos a listar remoções no CHANGELOG.
5. **Não afirmar o que não foi medido:** requisitos de hardware e latência do modelo estão marcados como estimativa até rodar `verificar_modelo.py`.
6. **Dependência opcional pesada = isolar:** `requirements-llm.txt` + carga preguiçosa mantêm o restante do projeto leve e utilizável.
7. **A verificação de fidelidade pegou um erro no próprio teste** (um sumário-modelo citava um número que não estava nos documentos): confirma o valor do controle automático.
8. **Compatibilidade entre modelos de um mesmo provedor muda com o tempo** (parâmetros recusados): o cliente se adapta e as mensagens orientam a configuração.
9. **Quem desenvolve sem acesso ao provedor deve entregar o roteiro de verificação** (`verificar_api_online.py`, `gerar_evidencias_ia.py`), não apenas código.
