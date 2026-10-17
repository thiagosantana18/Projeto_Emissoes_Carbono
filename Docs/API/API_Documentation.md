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

Erro `422 Unprocessable Entity` (formato resumido — o Pydantic detalha `type`, `loc`, `msg`, `input`):
```json
{"detail": [{"loc": ["body", "mes_referencia"], "msg": "String should match pattern '^\\d{4}-(0[1-9]|1[0-2])$'"}]}
```
Outras causas de 422: `quantidade` ≤ 0; campo obrigatório ausente; `emissao_kgco2e` inconsistente.

## POST /emissoes/lote
Corpo: lista de 1 a 500 objetos iguais ao de `POST /emissoes`. Se **algum** item for inválido, nada é gravado (422).
Resposta `201`: `{"inseridos": 2}`.

## Rotas de texto e de preparação para LLM
- `GET /noticias?q=carbono&tag=emissoes&limit=10` — da mais recente para a mais antiga.
- `GET /ods?ods=13&q=clima` — `ods` aceita `12` ou `13`.
- `GET /corpus?tipo=noticia&limit=20` — retorna `404` com instrução se o corpus ainda não foi gerado (`python Code/data_preparation/build_corpus.py`).
- `GET /corpus/contexto-relatorio` — totais por unidade/atividade/mês, maiores fontes, variação do último mês e fatores usados.

## Testes
`tests/test_api.py` (TestClient do FastAPI) cobre health, filtros/paginação, POST válido e inválido, lote e 404 do corpus.
Requer `pip install -r requirements-dev.txt`; sem FastAPI instalado os testes são pulados.
Execução: `python -m unittest discover -s tests -v` ou `pytest`.
