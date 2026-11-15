# Escolha do modelo de linguagem local

**Decisão:** `lxyuan/distilbert-base-multilingual-cased-sentiments-student` (Hugging Face Hub), executado localmente com
`transformers` + `torch` em CPU, para **classificação de sentimento** (positivo / neutro / negativo) de textos em português.

> Pesquisa nos cartões dos modelos no Hugging Face Hub em nov/2026. Onde um número foi **estimado** (e não lido de um cartão
> ou medido), isso está dito. **Nada foi medido na máquina de desenvolvimento deste projeto** — os requisitos de hardware abaixo
> são estimativas; `python Code/llm/verificar_modelo.py` mede memória e latência reais na sua máquina.

## 1. Requisitos que guiaram a escolha
- Máquina **modesta** (sem GPU assumida) e projeto **protótipo** → "o mais simples possível".
- Rodar **localmente**, sem nuvem, com Transformers e PyTorch.
- Português do Brasil; dados disponíveis hoje: **manchetes** de notícias ESG (ver `LLM_Readiness.md`).

## 2. Por que a tarefa é sentimento (e não resumo ou geração)
| Tarefa | Dados que temos | Peso do modelo | Conclusão |
|---|---|---|---|
| **Sentimento** | 18+ manchetes (curtas), gabarito pronto para rotular | encoder pequeno (~0,1 B parâmetros) | ✅ viável agora, em CPU |
| Resumo | não há textos longos (só títulos e trechos ≤ 600 caracteres) | modelo seq2seq de ≥ 2 GB | ❌ falta dado e sobra peso |
| Perguntas e respostas / relatórios | corpus pequeno e contexto numérico | LLM generativo (≥ 0,5 B parâmetros, lento em CPU) | ⏭️ etapa futura |

## 3. Candidatos avaliados
| Modelo | Tarefa | Tamanho | Licença | Português | Observações (fonte: cartão do modelo, salvo indicação) |
|---|---|---|---|---|---|
| **lxyuan/distilbert-base-multilingual-cased-sentiments-student** | sentimento 3 classes | ≈135 M parâmetros (pesos em F32 ≈ **0,5 GB**, estimado: 135 M × 4 bytes) | Apache-2.0 | sim (12 idiomas) | Aluno destilado do `distilbert-base-multilingual-cased`, com professor `mDeBERTa-v3-base-mnli-xnli`; concordância aluno–professor de **88,29 %** reportada |
| cardiffnlp/twitter-xlm-roberta-base-sentiment | sentimento 3 classes | família XLM-R base ≈ 278 M parâmetros (≈ 1,1 GB em F32, estimado) | não verificada | sim (8 idiomas) | **Treinado em tweets** (domínio diferente de manchetes); ~2× maior |
| csebuetnlp/mT5_multilingual_XLSum | resumo abstrativo | arquivo de pesos de **2,33 GB** (2.329.707.353 bytes) | CC BY-NC-SA 4.0 (**não comercial**) | sim (ROUGE-1/2/L em pt: 37,17 / 15,90 / 28,56) | Pesado para a máquina; sem textos longos para usar |
| Qwen/Qwen2.5-0.5B-Instruct | geração geral (resumo, Q&A, relatórios) | ≈ 0,5 B parâmetros (≈ 1 GB em 16 bits, estimado) | Apache-2.0 | listado | Dados lidos de um espelho do cartão — confirme no cartão oficial. Geração em CPU é lenta; qualidade em português modesta (julgamento, não medido). **Candidato futuro** para relatórios |

## 4. Matriz de decisão
Pesos: desempenho 35 %, custo computacional local 35 %, acessibilidade local 30 %. Notas de 1 a 5 são **julgamento da equipe**
com base nos cartões, não um benchmark próprio.

| Modelo | Desempenho | Custo local | Acessibilidade | **Total** |
|---|---|---|---|---|
| **DistilBERT multilíngue (sentimento)** | 3 | 5 | 5 | **4,30** |
| XLM-R base (tweets) | 3 | 3 | 4 | 3,30 |
| Qwen2.5-0.5B-Instruct | 2 | 3 | 4 | 2,95 |
| mT5 XLSum | 4 (para resumo) | 1 | 3 | 2,65 |

## 5. Justificativa por critério
**Desempenho.** É um classificador de **3 classes (positive/neutral/negative) com português entre os idiomas de treino**, o que casa
exatamente com a tarefa e com o gabarito do projeto. Ressalva importante: o cartão reporta **concordância com o professor (88,29 %)**,
não acurácia contra rótulos humanos — o modelo foi destilado sem usar as anotações originais. Por isso a qualidade **para manchetes ESG
precisa ser medida**: rotule `Data/processed/avaliacao/sentimento_gold_template.csv` e rode `python Code/llm/avaliar_sentimento.py avaliar`.
Manchetes jornalísticas tendem a ser neutras; espere muitas previsões "neutro".

**Custo computacional local.** Menor entre os candidatos: encoder pequeno, sem geração token a token. Estimativas (a confirmar com
`verificar_modelo.py`): disco ≈ 0,5 GB do modelo + ≈ 0,2 GB do `torch` CPU no Windows; RAM do processo na faixa de **1 a 1,5 GB**;
CPU comum é suficiente (frases curtas na ordem de dezenas a poucas centenas de ms); **GPU não é necessária**.
Limites configuráveis protegem a máquina: 2000 caracteres/texto, 256 tokens, 1 inferência por vez, fila de 4, timeout de 30 s.

**Acessibilidade local.** Carrega com `AutoTokenizer` / `AutoModelForSequenceClassification` (Transformers), licença **Apache-2.0**
(uso livre), pesos em safetensors, download único e depois **100 % offline** (`local_files_only`). Troca de modelo por variável de
ambiente (`ESG_LLM_MODEL`), desde que use os rótulos positive/neutral/negative.

## 6. Como a integração local funciona
```
Dashboard (Streamlit) ──HTTP──► FastAPI: POST /processar_texto ──► ServicoSentimento ──► pipeline("text-classification")
   Análise de texto            validação (Pydantic) + erros         carga preguiçosa,        tokenizador + DistilBERT
                               padronizados (envelope)              thread única, timeout     lendo Models/hf_cache (offline)
```
Passo a passo (a partir da raiz do projeto):
```bash
pip install -r requirements.txt -r requirements-llm.txt
python Code/llm/baixar_modelo.py      # uma vez, com internet (~0,5 GB) → Models/hf_cache
python Code/llm/verificar_modelo.py   # carga, memória, latência e 3 frases de teste
uvicorn App.api.main:app --reload     # API;  Swagger em http://127.0.0.1:8000/docs
streamlit run App/dashboard/app.py    # página "Análise de texto (LLM local)"
```
Código: `Code/esg_core/llm/` (config, erros, serviço, métricas), rotas em `App/api/routers/llm.py`, modelos de resposta em `App/api/schemas_llm.py`.

## 7. Limitações e riscos
- Qualidade em manchetes ESG **não medida**; depende do gabarito humano (pendente).
- Português é 1 de 12 idiomas do modelo; ironia e jargão financeiro/ambiental podem errar.
- Textos > 256 tokens são truncados (a resposta informa `truncado`).
- Uma inferência por vez: adequado a protótipo, não a produção.
- Fixe `ESG_LLM_REVISION` (commit do Hub) para reprodutibilidade; sem isso, o cache reflete a versão baixada no dia.

## 8. Evolução
Gerar relatórios/Q&A → LLM generativo pequeno (ex.: Qwen2.5-0.5B-Instruct), avaliando latência em CPU; resumir → coletar textos longos
primeiro e reavaliar modelos (atenção a licença não comercial e ao tamanho do mT5 XLSum).

## 9. Fontes consultadas
- https://huggingface.co/lxyuan/distilbert-base-multilingual-cased-sentiments-student
- https://huggingface.co/csebuetnlp/mT5_multilingual_XLSum
- https://huggingface.co/cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual e https://arxiv.org/pdf/2104.12250v2.pdf (família XLM-R tweets)
- Cartões do Qwen2.5-0.5B-Instruct (espelhos consultados; confirmar no oficial)
