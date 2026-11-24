# Code/llm — scripts do LLM local

| Script | Função |
|---|---|
| `baixar_modelo.py` | baixa o modelo para `Models/hf_cache` (uma vez, com internet, ~0,5 GB) |
| `verificar_modelo.py` | diagnóstico: dependências, cache, carga, memória, latência e 3 frases de teste (código de saída 1 se falhar) |
| `avaliar_sentimento.py prever` | classifica as notícias do corpus → `Data/processed/sentimento_noticias.csv` |
| `avaliar_sentimento.py avaliar` | compara com o gabarito humano (`avaliacao/sentimento_gold_template.csv`): acurácia, F1, matriz de confusão |

A lógica (serviço, configuração, erros, métricas) está em `Code/esg_core/llm/` — compartilhada com a API.
Escolha do modelo: `Docs/Project/LLM_Model_Selection.md`. Pré-requisito: `pip install -r requirements-llm.txt`.

Resumo, perguntas e respostas e insights usam IA online (ver abaixo).

| `verificar_api_online.py` | uma chamada mínima ao provedor de IA online configurado (chave no `.env`): confere conexão, modelo e JSON válido |

A **IA online** (sumarização, perguntas, insights) está em `Code/esg_core/ia/`; documentação em `Docs/Project/Prompt_Engineering.md`.
Evidências com saídas reais: `python Scripts/gerar_evidencias_ia.py --comparar-prompts`.
