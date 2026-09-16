# Projeto ESG — Monitoramento e Previsão de Emissões de Carbono Corporativas

Estrutura de pastas baseada no **TDSP (Team Data Science Process)**, adaptada para um projeto
de ciência de dados com IA generativa aplicado ao pilar **Ambiental (E)** do ESG,
alinhado aos ODS 12 e 13 da Agenda 2030.

## Estrutura de pastas

```
projeto-esg-emissoes-carbono/
│
├── Docs/                        # Documentação do projeto (fases do TDSP)
│   ├── Project/                 # Project Charter, Exit Report
│   ├── Data_Report/             # Data Summary Report, Data Quality Report
│   ├── Model_Report/            # Documentação técnica do(s) modelo(s)
│   └── Presentations/           # Apresentações e materiais de comunicação
│
├── Code/                        # Código-fonte do pipeline analítico
│   ├── data_acquisition/        # Scripts de coleta via API (Climatiq, EPA, SEEG)
│   ├── data_exploration/        # Análise exploratória (EDA)
│   ├── feature_engineering/     # Criação de variáveis para o modelo
│   ├── modeling/
│   │   ├── model_building/      # Treinamento dos modelos (ex.: Prophet, SARIMA)
│   │   └── model_evaluation/    # Avaliação e métricas (MAPE, RMSE)
│   ├── scoring/                 # Geração de previsões/scoring em novos dados
│   └── genai_reporting/         # Integração com LLM para geração do relatório narrativo
│
├── Data/                        # Dados do projeto (NUNCA versionar dados sensíveis)
│   ├── raw/                     # Dados brutos, como extraídos das fontes/APIs
│   ├── interim/                 # Dados intermediários (limpeza parcial)
│   └── processed/                # Dados finais, prontos para modelagem/dashboard
│
├── App/                         # Aplicação final (dashboard)
│   ├── dashboard/                # Código do dashboard Streamlit
│   └── assets/                   # Imagens, ícones, CSS/estilos do dashboard
│
├── Scripts/                     # Scripts utilitários (setup de ambiente, agendamento, etc.)
│
├── requirements.txt             # Dependências Python do projeto
└── README.md                    # Este arquivo
```

## Metodologia

- **CRISP-DM**: guia o ciclo analítico (Business Understanding → Data Understanding →
  Data Preparation → Modeling → Evaluation → Deployment).
- **TDSP**: guia a organização do repositório, papéis da equipe e os documentos de
  governança do projeto (Project Charter, Data Summary Report, Model Report, Exit Report).

## Status atual do projeto

- [x] Business Understanding — Project Charter (v2)
- [x] Data Acquisition and Understanding — Data Summary Report (v2), incluindo
      dados coletados via web scraping (BeautifulSoup)
- [x] Aplicação demo (Streamlit) — Etapa 2: interface em abas, cache, estado
      de sessão, nuvem de palavras e upload/download de CSV
- [ ] Data Preparation completa (limpeza, EDA, Data Quality Report)
- [ ] Modeling (previsão de emissões, explicabilidade das fontes)
- [ ] Evaluation
- [ ] Deployment final (relatório automático via IA generativa)

## Etapa 2 — o que foi adicionado

- **Web scraping (BeautifulSoup)**: dois scripts em `Code/data_acquisition/`,
  cada um verificando o `robots.txt` do domínio-alvo antes de coletar,
  salvando o resultado em `Data/raw/*.csv` e `*.txt`.
- **Nuvem de palavras e estatísticas básicas**: geradas a partir dos dados
  coletados, exibidas na aplicação.
- **Cache e estado de sessão em Streamlit**: `st.cache_data` para os
  carregamentos de dados; `st.session_state` para filtros, histórico de
  uploads e o dataset combinado entre interações.
- **Upload e download de CSV**: o usuário pode complementar o dataset da
  aplicação enviando seus próprios dados, e baixar o resultado consolidado.
