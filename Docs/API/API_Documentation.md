# Documentação da API (FastAPI)

API REST do projeto: permite **consultar** (GET) e **enviar** (POST) dados de atividade/emissão e **consultar** os
textos coletados por scraping. Serve de ponto de integração (ERP, BI, planilhas) e de porta de entrada de dados
para as tarefas de LLM da próxima etapa.

- **Subir:** `uvicorn App.api.main:app --reload` (a partir da raiz do projeto)
- **Swagger UI (interativo):** http://127.0.0.1:8000/docs · **ReDoc:** http://127.0.0.1:8000/redoc
- **Autenticação:** nenhuma — protótipo acadêmico, **não exponha publicamente** (ver riscos no Project Charter).
- **Persistência:** `POST` grava em `Data/raw/emissoes_enviadas_api.csv` (append). A amostra `Data/processed/amostra_emissoes.csv` nunca é alterada.
- **Código:** `App/api/` (rotas e schemas) sobre `Code/esg_core/` (lógica de dados, compartilhada com o dashboard).

## Resumo das rotas

| Método | Rota | Função |
|---|---|---|
| GET | `/health` | Verifica se a API está no ar e quais arquivos de dados existem |
| **GET** | **`/emissoes`** | **Consulta registros de atividade/emissão (filtros + paginação)** |
| GET | `/emissoes/resumo` | Total de kgCO2e e agregações por unidade, atividade e mês |
| **POST** | **`/emissoes`** | **Envia um novo registro (validado)** |
| POST | `/emissoes/lote` | Envia até 500 registros (validação tudo-ou-nada) |
| GET | `/noticias` | Manchetes ESG coletadas (busca `q`, filtro `tag`) |
| GET | `/ods` | Trechos sobre os ODS 12 e 13 |
| GET | `/corpus` | Corpus unificado preparado para LLM |
| GET | `/corpus/contexto-relatorio` | Agregados numéricos para geração de relatórios (grounding) |
| **POST** | **`/processar_texto`** | **Sentimento de um texto com modelo Hugging Face local** |
| POST | `/processar_texto/lote` | Sentimento de até 32 textos |
| GET | `/modelo/status` | Estado do modelo local (carregado, dependências, cache, último erro) |
| POST | `/modelo/carregar` | Carrega (aquece) o modelo na memória |

## GET /emissoes — consultar dados

Parâmetros (todos opcionais): `unidade`, `setor`, `tipo_atividade` (texto, sem diferenciar maiúsculas),
`mes_inicio`, `mes_fim` (`AAAA-MM`, inclusivos), `origem` (`base` | `api`), `limit` (1–1000, padrão 100), `offset` (≥ 0).

```bash
curl "http://127.0.0.1:8000/emissoes?unidade=Filial%20-%20RJ&limit=2"
```
```powershell
Invoke-RestMethod "http://127.0.0.1:8000/emissoes?unidade=Filial%20-%20RJ&limit=2"
```
Resposta `200` (dados reais da amostra do projeto; `total` ignora a paginação):
```json
{
  "total": 48, "limit": 2, "offset": 0,
  "itens": [
    {"mes_referencia": "2024-10", "unidade": "Filial - RJ", "setor": "Logística",
     "tipo_atividade": "Eletricidade (rede)", "quantidade": 7531.6, "unidade_medida": "kWh",
     "fator_emissao_kgco2e": 0.0817, "emissao_kgco2e": 615.33, "fonte_fator": "Climatiq API", "origem": "base"},
    {"mes_referencia": "2024-10", "unidade": "Filial - RJ", "setor": "Logística",
     "tipo_atividade": "Diesel (frota)", "quantidade": 1523.6, "unidade_medida": "litro",
     "fator_emissao_kgco2e": 2.6712, "emissao_kgco2e": 4069.84, "fonte_fator": "EPA", "origem": "base"}
  ]
}
```
Erros: `422` se `limit` fora de 1–1000 ou `mes_inicio`/`mes_fim` fora do formato `AAAA-MM`.

## GET /emissoes/resumo — agregações

Aceita os mesmos filtros (exceto paginação). Resposta (trecho; amostra completa de 216 registros):
```json
{"n_registros": 216, "total_kgco2e": 685997.19, "periodo_inicio": "2024-10", "periodo_fim": "2026-09",
 "por_unidade": {"CD - PR": 151154.65, "Filial - MG": 364658.95, "Filial - RJ": 112837.74, "Matriz - SP": 57345.85},
 "por_tipo_atividade": {"Diesel (frota)": 394940.64, "Eletricidade (rede)": 79550.58,
                        "Gasolina (frota leve)": 38720.83, "Gás natural (caldeira)": 172785.14},
 "por_mes": {"2024-10": 27041.97, "2024-11": 28290.83, "...": "..."}}
```

## POST /emissoes — enviar dados

Corpo (JSON). `emissao_kgco2e` é **opcional**: se omitida, a API calcula `quantidade × fator_emissao_kgco2e`
(2 casas); se enviada, precisa ser consistente com o produto (tolerância de 1 % ou 0,05 kgCO2e).

| Campo | Tipo | Regra |
|---|---|---|
| `mes_referencia` | string | formato `AAAA-MM` (mês 01–12) |
| `unidade`, `setor`, `tipo_atividade`, `unidade_medida`, `fonte_fator` | string | 1 a 80 caracteres (20 para `unidade_medida`) |
| `quantidade` | número | > 0 |
| `fator_emissao_kgco2e` | número | ≥ 0 |
| `emissao_kgco2e` | número (opcional) | ≥ 0 e consistente com quantidade × fator |

```bash
curl -X POST http://127.0.0.1:8000/emissoes -H "Content-Type: application/json" -d '{
  "mes_referencia": "2026-10", "unidade": "Matriz - SP", "setor": "Administrativo",
  "tipo_atividade": "Eletricidade (rede)", "quantidade": 8500, "unidade_medida": "kWh",
  "fator_emissao_kgco2e": 0.0817, "fonte_fator": "Climatiq API"}'
```
```powershell
$corpo = @{ mes_referencia="2026-10"; unidade="Matriz - SP"; setor="Administrativo"; tipo_atividade="Eletricidade (rede)";
            quantidade=8500; unidade_medida="kWh"; fator_emissao_kgco2e=0.0817; fonte_fator="Climatiq API" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/emissoes -ContentType "application/json" -Body $corpo
```
Resposta `201 Created` (emissão calculada: 8500 × 0,0817 = 694,45):
```json
{"mes_referencia": "2026-10", "unidade": "Matriz - SP", "setor": "Administrativo", "tipo_atividade": "Eletricidade (rede)",
 "quantidade": 8500.0, "unidade_medida": "kWh", "fator_emissao_kgco2e": 0.0817, "emissao_kgco2e": 694.45,
 "fonte_fator": "Climatiq API", "origem": "api"}
```
O registro passa a aparecer em `GET /emissoes?origem=api` e no dashboard (o cache é invalidado pela data de modificação do arquivo).

Erro `422 Unprocessable Entity` — todas as rotas usam o **envelope de erro padrão** (ver seção abaixo):
```json
{"codigo": "DADOS_INVALIDOS", "mensagem": "Os dados enviados são inválidos.",
 "detalhes": [{"campo": "mes_referencia", "problema": "formato inválido (esperado: ^\\d{4}-(0[1-9]|1[0-2])$)"}],
 "sugestao": "Corrija os campos indicados em 'detalhes' e envie novamente.", "request_id": "3f9c1a7b2e4d"}
```
Outras causas de 422: `quantidade` ≤ 0; campo obrigatório ausente; `emissao_kgco2e` inconsistente.

## POST /emissoes/lote
Corpo: lista de 1 a 500 objetos iguais ao de `POST /emissoes`. Se **algum** item for inválido, nada é gravado (422).
Resposta `201`: `{"inseridos": 2}`.

## Rotas de texto e de preparação para LLM
- `GET /noticias?q=carbono&tag=emissoes&limit=10` — da mais recente para a mais antiga.
- `GET /ods?ods=13&q=clima` — `ods` aceita `12` ou `13`.
- `GET /corpus?tipo=noticia&limit=20` — retorna `404` (envelope `NAO_ENCONTRADO`) com instrução se o corpus ainda não foi gerado (`python Code/data_preparation/build_corpus.py`).
- `GET /corpus/contexto-relatorio` — totais por unidade/atividade/mês, maiores fontes, variação do último mês e fatores usados.

## Testes
`tests/test_api.py` (TestClient do FastAPI) cobre health, filtros/paginação, POST válido e inválido, lote e 404 do corpus.
Requer `pip install -r requirements-dev.txt`; sem FastAPI instalado os testes são pulados.
Execução: `python -m unittest discover -s tests -v` ou `pytest`.


---

# Envelope de erro padrão (todas as rotas)

Todo erro — validação, rota inexistente, falha do modelo, erro inesperado — sai no **mesmo formato** e com o header `X-Request-ID`
(enviado por você ou gerado pela API; use-o para rastrear a requisição nos logs):

| Campo | Significado |
|---|---|
| `codigo` | identificador estável para o cliente tratar por programa |
| `mensagem` | explicação em português |
| `detalhes` | lista de `{campo, problema}` (validação) — vazia nos demais casos |
| `sugestao` | o que fazer para resolver |
| `request_id` | mesmo valor do header `X-Request-ID` |

| HTTP | `codigo` | Quando acontece | Header extra |
|---|---|---|---|
| 422 | `DADOS_INVALIDOS` | JSON malformado, campo ausente/tipo errado/formato inválido (Pydantic) | — |
| 422 | `TEXTO_INVALIDO` | texto vazio, sem letras, maior que o limite, lote vazio ou grande demais | — |
| 404 / 405 | `NAO_ENCONTRADO` / `METODO_NAO_PERMITIDO` | rota ou método inexistente; dado ainda não gerado (corpus) | — |
| 429 | `MODELO_OCUPADO` | fila de processamento cheia (padrão: 4 pendentes) | `Retry-After` |
| 500 | `FALHA_INFERENCIA` | o modelo falhou (ex.: falta de memória) ou devolveu saída inválida | — |
| 500 | `RESPOSTA_INVALIDA` | a resposta gerada não cumpre o contrato (bug) — registrada no log | — |
| 500 | `ERRO_INTERNO` | exceção inesperada; **sem traceback** para o cliente | — |
| 503 | `MODELO_INDISPONIVEL` | `torch`/`transformers` ausentes, modelo não baixado ou falha ao carregar | `Retry-After` (durante a espera após falha) |
| 504 | `TEMPO_LIMITE_EXCEDIDO` | a inferência passou de `ESG_LLM_TIMEOUT` (padrão: 30 s) | `Retry-After` |

Exemplo — modelo ainda não baixado (`503`):
```json
{"codigo": "MODELO_INDISPONIVEL",
 "mensagem": "Falha ao carregar o modelo 'lxyuan/distilbert-base-multilingual-cased-sentiments-student': OSError: ...",
 "detalhes": [],
 "sugestao": "O modelo ainda não foi baixado. Execute uma vez: python Code/llm/baixar_modelo.py (ou defina ESG_LLM_OFFLINE=0 para permitir o download automático).",
 "request_id": "a81d0c3e5b7f"}
```

# LLM local — rotas

Detalhes da escolha do modelo e da instalação: `Docs/Project/LLM_Model_Selection.md`.

## POST /processar_texto
Corpo: `{"texto": "...", "tarefa": "sentimento"}` (`tarefa` é opcional; hoje só existe `sentimento`).
O texto passa por normalização de espaços; limite de 2000 caracteres (configurável) e 256 tokens (excedentes são truncados e a resposta indica).

```bash
curl -X POST http://127.0.0.1:8000/processar_texto -H "Content-Type: application/json" \
     -d '{"texto": "Vivo reduz emissões em 91% e antecipa neutralidade climática para 2035"}'
```
```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/processar_texto -ContentType "application/json; charset=utf-8" `
  -Body ([Text.Encoding]::UTF8.GetBytes('{"texto": "Vivo reduz emissões em 91%"}'))
```
Resposta `200` (**exemplo ilustrativo** — a estrutura é garantida pelo Response Model; os valores dependem do modelo):
```json
{
  "texto_original": "Vivo reduz emissões em 91% e antecipa neutralidade climática para 2035",
  "texto_processado": "Vivo reduz emissões em 91% e antecipa neutralidade climática para 2035",
  "tipo_analise": "classificacao_sentimento",
  "resultado": {"rotulo": "positivo", "confianca": 0.93,
                "probabilidades": {"positivo": 0.93, "neutro": 0.05, "negativo": 0.02}},
  "modelo": {"id": "lxyuan/distilbert-base-multilingual-cased-sentiments-student", "dispositivo": "cpu", "revisao": null},
  "metadados": {"tempo_inferencia_ms": 41.7, "n_caracteres": 70, "n_tokens": 24, "truncado": false,
                "processado_em": "2026-11-13T10:20:31"}
}
```
Validação das respostas: o serviço só devolve a saída do modelo se os rótulos forem os três esperados, cada probabilidade estiver em [0, 1]
e a soma for ≈ 1; caso contrário responde `500 FALHA_INFERENCIA`. O FastAPI valida de novo contra o Response Model (`RESPOSTA_INVALIDA`).

## POST /processar_texto/lote
Corpo: `{"textos": ["...", "..."]}` (até 32). Resposta: `{tipo_analise, total, resultados: [{indice, texto_processado, resultado, truncado}], modelo, tempo_total_ms, processado_em}`.
Se **qualquer** texto for inválido, nada é processado: `422 TEXTO_INVALIDO` com `detalhes[].campo = "textos[i]"`.

## GET /modelo/status e POST /modelo/carregar
`status` informa `carregado`, `dependencias_instaladas`, `cache_presente`, `offline`, `dispositivo`, `tempo_carga_s`, `ultimo_erro`, contadores e `limites` —
é a primeira coisa a consultar diante de um 503. `carregar` (`?forcar=true` ignora a espera após falha) aquece o modelo; se falhar, devolve `503`.

## Comportamentos de robustez
- **Carga preguiçosa:** a API sobe mesmo sem `torch`; só as rotas de LLM respondem 503. `ESG_LLM_PRELOAD=1` carrega o modelo na subida (se falhar, a API segue no ar).
- **Offline por padrão:** nenhuma requisição dispara download (evita travar a máquina e a requisição).
- **Espera após falha de carga** (30 s): evita martelar o disco/rede; `POST /modelo/carregar?forcar=true` ignora.
- **Uma inferência por vez + fila limitada:** protege a máquina; excesso recebe `429`. Uma inferência que estoura o tempo devolve `504` e continua ocupando sua vaga até terminar (o Python não consegue abortar uma thread).

## Testes
`tests/test_llm_service.py` (21 testes, sem FastAPI/torch: pipeline falso injetado) cobre sucesso, formatos de saída, validação, saída inválida do modelo,
carga (dependências ausentes, cache ausente, espera, concorrência), timeout, fila cheia e erro de inferência.
`tests/test_api_llm.py` (14 testes; exigem `pip install -r requirements-dev.txt`) cobre o mesmo pela API: 200, 422, 429, 500, 503, 504, 404/405, `X-Request-ID`.
