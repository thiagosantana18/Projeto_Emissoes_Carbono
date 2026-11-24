# Model Report (TDSP)

Modelos e métodos usados no projeto, como foram avaliados e o que ainda não foi medido.
Resumo: **3 componentes de modelagem** + 1 componente de recuperação, cada um escolhido pelo menor custo que resolve a tarefa.

| Componente | Tarefa | Tipo | Roda | Avaliação | Situação |
|---|---|---|---|---|---|
| Previsão de emissões (tendência + sazonalidade) | prever os próximos meses | estatístico, transparente | local | backtest com origem móvel: **MAPE 3,53%** | ✅ medido (dados sintéticos) |
| DistilBERT multilíngue de sentimento | classificar manchetes | encoder pequeno (Hugging Face) | local, CPU, offline | gabarito humano (≥ 50 itens) | ⏳ implementado; qualidade **não medida** |
| LLM online (OpenAI/Anthropic) | resumir, responder, recomendar | LLM generativo via API | provedor | fidelidade automática + leitura humana + linha de base | ⏳ implementado e testado com LLM simulado; **não medido com provedor real** |
| Recuperação BM25 | achar os trechos relevantes para uma pergunta | lexical, sem embeddings | local | testes unitários (relevância, abstenção) | ✅ testado; sem conjunto de perguntas de referência |

## 1. Previsão de emissões
**Dados:** série mensal do total de emissões (24 meses, 2024-10 a 2026-09), a partir de 216 registros **sintéticos**.
**Métodos comparados** (`Code/esg_core/previsao.py`, só NumPy/pandas): *ingênuo* (repete o último mês); *sazonal ingênuo* (repete o mesmo mês do ano anterior);
*tendência + sazonalidade* (regressão linear + índice sazonal multiplicativo por mês, ajustados em 3 iterações).
**Validação:** *backtest* com origem móvel — treina com os primeiros k meses (k ≥ 12) e prevê 3 meses; 10 origens × 3 meses = 30 previsões por método.

| Método | MAPE | RMSE (kgCO2e) | Previsões avaliadas |
|---|---|---|---|
| tendencia_sazonal | 3,53% | 1.585,53 | 30 |
| sazonal_ingenuo | 3,94% | 1.340,68 | 30 |
| ingenuo | 4,69% | 1.660,99 | 30 |

**Melhor método:** `tendencia_sazonal` — meta do projeto (MAPE < 15%) **atingida**.
**Previsão final (próximos 6 meses)** e faixa aproximada (faixa aproximada (±6.4%) a partir da dispersão dos erros do backtest):

| Mês | Previsto (kgCO2e) | Faixa |
|---|---|---|
| 2026-10 | 29.400,91 | 27.509,53 a 31.292,29 |
| 2026-11 | 31.395,18 | 29.375,51 a 33.414,86 |
| 2026-12 | 31.322,31 | 29.307,32 a 33.337,29 |
| 2027-01 | 32.937,41 | 30.818,53 a 35.056,29 |
| 2027-02 | 31.947,41 | 29.892,21 a 34.002,60 |
| 2027-03 | 31.380,87 | 29.362,12 a 33.399,62 |

**Como interpretar (honestidade):** a série é sintética, gerada com tendência + sazonalidade + ruído — exatamente a estrutura que o método modela. O MAPE baixo **demonstra que o método e o código funcionam**,
não que o projeto preveja bem uma empresa real. Com 24 meses há só 2 ciclos sazonais. A faixa é aproximada (assume erros com dispersão estável). Substitua a amostra por dados reais (POST /emissoes, upload) e rode de novo.
**Não foram usados** Prophet/SARIMA: com 24 pontos eles acrescentam parâmetros sem ganho demonstrável, e a linha de base transparente é mais fácil de auditar. Reavaliar com ≥ 36 meses de dados reais.

## 2. Sentimento (modelo local)
`lxyuan/distilbert-base-multilingual-cased-sentiments-student` (ver `Docs/Project/LLM_Model_Selection.md`). Rótulos positivo/neutro/negativo; ≈135 M de parâmetros; Apache-2.0.
O cartão do modelo reporta 88,29% de concordância com o modelo "professor" — **não** acurácia contra humanos. Avaliação prevista: rotular `Data/processed/avaliacao/sentimento_gold_template.csv` (≥ 50 manchetes reais)
e rodar `python Code/llm/avaliar_sentimento.py avaliar` (acurácia, F1 por classe, matriz de confusão; código testado). Resultado: **pendente**.

## 3. LLM online: sumarização, perguntas e respostas, insights
**Provedores:** OpenAI (padrão `gpt-5-mini`, configurável) e Anthropic (padrão `claude-haiku-5-5`, configurável) por HTTP direto; qualquer servidor compatível com a API da OpenAI (Ollama, LM Studio) via `ESG_OPENAI_BASE_URL`.
**"Modelo" = prompt + validação:** o comportamento depende dos prompts versionados (`Docs/Project/Prompt_Engineering.md`), da validação do JSON e da verificação de fidelidade.
**Avaliação definida (a executar com chave):** JSON válido; fidelidade (números e citações); linha de base extrativa; leitura humana 1–5 (fidelidade, completude, utilidade); tokens e latência; comparação `sumario_v1` × `sumario_v2`.
**Linha de base sem IA** (resumo extrativo das manchetes coletadas — saída real, sem LLM):
> - Bradesco Seguros adapta portfólio a partir do clima extremo e vê ESG virar resultado.
> - Gerdau reduz pela metade pegada de carbono do aço e amplia aposta em energia limpa.
> - Orizon transforma lixo em biometano e reduz emissões em até 90%.

**Verificado até aqui:** 111 testes automatizados passam, incluindo clientes HTTP com respostas simuladas (OpenAI e Anthropic: sucesso, 401, cota, 429, 5xx, timeout, saída truncada/vazia/recusa, adaptação de parâmetros),
JSON malformado e reparo, map-reduce, número inventado, citação falsa, injeção de prompt, cache, limite de custo e auditoria. **Não verificado:** chamadas a provedores reais.

## 4. Recuperação (BM25)
Índice lexical sobre título + texto, sem acentos, com radicalização simples do português (emissões/emissão). Documentos: corpus coletado (28 documentos) + texto de contexto das emissões.
Sem trechos relevantes, o LLM não é chamado. Limitações: busca por palavras (não por significado) — sinônimos podem falhar; evolução natural: *embeddings* quando o corpus crescer.

## 5. IA responsável
- **Transparência:** toda saída de IA mostra provedor, modelo, versão do prompt, tokens, fontes e resultado da verificação.
- **Humano no circuito:** a IA recomenda; quem decide é o gestor. Alertas de dados (ex.: "dados sintéticos") são obrigatórios nos insights.
- **Privacidade:** textos vão ao provedor escolhido; o histórico de auditoria não guarda a entrada.
- **Viés e cobertura:** corpus pequeno e de **uma única fonte de notícias**; resultados de sentimento e de resumo refletem essa fonte.
- **Reprodutibilidade:** seed fixa no gerador sintético; versão de prompt e modelo registradas; cache por hash.

## 6. Reprodução
```bash
python Code/data_acquisition/generate_sample_emissions.py   # amostra sintética (seed 42)
python -c "import sys; sys.path.insert(0,'Code'); from esg_core import data_access as d; from esg_core.previsao import prever_emissoes; print(prever_emissoes(d.carregar_emissoes())['metodos'])"
python Code/llm/avaliar_sentimento.py avaliar              # após rotular o gabarito
python Scripts/gerar_evidencias_ia.py --comparar-prompts   # IA online (requer chave)
```
