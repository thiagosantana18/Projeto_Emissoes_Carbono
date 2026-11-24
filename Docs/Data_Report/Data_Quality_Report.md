# Data Quality Report

_Gerado automaticamente em 2026-11-23 16:20:17 por `Scripts/gerar_relatorio_qualidade.py` sobre os arquivos presentes em `Data/`. Reexecute após cada coleta para atualizar._

## 1. Resumo

**12 de 13 verificações aprovadas.**

| Verificação | Resultado | Detalhe |
|---|---|---|
| Emissões: sem valores nulos | ✅ | 0 nulos |
| Emissões: sem lacunas mensais | ✅ | 0 meses faltantes |
| Emissões: sem duplicados | ✅ | 0 duplicados |
| Emissões: emissão = quantidade × fator | ✅ | 0 inconsistentes |
| Emissões: unidade de medida única por atividade | ✅ |  |
| Emissões: sem outliers extremos (z-score absoluto > 3, em log) | ✅ | 0 outliers |
| Notícias: sem títulos duplicados | ✅ | 0 duplicados |
| Notícias: URLs de matéria (não da listagem) | ❌ | 18 apontam para listagem |
| Notícias: ≥ 80% com data de publicação | ✅ | 0.0% sem data |
| ODS: sem trechos duplicados | ✅ | 0 duplicados |
| Corpus: doc_id único | ✅ |  |
| Corpus: sem textos vazios | ✅ |  |
| Corpus: todos com fonte e URL | ✅ | 0 sem fonte/URL |

## 2. Emissões (atividade e emissão)

- Registros: **216** · período 2024-10 a 2026-09 · origens: {'base': 216}
- Nulos por coluna: 0 no total · duplicados: 0 · meses faltantes: 0 · emissões inconsistentes: 0
- Pares unidade×atividade com meses faltando: 0 · outliers (z-score absoluto > 3, em log): 0
- Fatores de emissão estáveis por atividade: sim · unidade de medida única por atividade: sim
- Emissão por registro (kgCO2e): {'min': 524.15, 'mediana': 1599.71, 'max': 8241.89}

> ⚠️ A amostra é **sintética**: ausência de problemas aqui reflete o gerador, não a qualidade de dados reais de uma empresa.

## 3. Notícias coletadas (scraping)

- Manchetes: **18** · fontes: 1 · período de publicação: ['2023-06-23', '2026-05-30'] · última coleta: 2026-09-15 10:05:00
- Títulos duplicados: 0 · URLs duplicadas: 17 · URLs que apontam para a listagem: 18
- Sem data de publicação: 0.0% · sem linha fina: 100.0% · sem tags: 16.7%
- Tamanho do título (caracteres): {'min': 63.0, 'mediana': 76.5, 'max': 94.0}

## 4. Conteúdo dos ODS (scraping)

- Trechos: **10** {'ODS 12': 5, 'ODS 13': 5} · duplicados: 0 · sem seção: 0.0% · tamanho (caracteres): {'min': 87.0, 'mediana': 128.5, 'max': 161.0}

## 5. Corpus para IA

- Documentos: **28** {'noticia': 18, 'ods_trecho': 10} · `doc_id` duplicados: 0 · textos vazios: 0 · sem fonte/URL: 0
- Palavras: 409 no total; por documento {'min': 9.0, 'mediana': 13.5, 'max': 25.0} · notícias sem data de publicação: 0.0%

## 6. Previsões de sentimento (modelo local)

_Ainda não geradas (`python Code/llm/avaliar_sentimento.py prever`)._

## 7. Achados e ações

- **Notícias: URLs de matéria (não da listagem)** — 18 apontam para listagem

_Limitação do relatório: mede consistência interna e completude; não mede se os dados são *verdadeiros* (isso exige comparar com a fonte original)._