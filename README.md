# Projeto ESG — Monitoramento e Previsão de Emissões de Carbono Corporativas

Contexto do problema: muitas empresas, especialmente PMEs, não têm visibilidade contínua sobre sua pegada de carbono (Escopo 1, 2 e 3). Os relatórios costumam ser anuais, manuais e reativos, dificultando decisões de redução em tempo hábil.

ODS relacionados: ODS 13 (Ação contra a mudança global do clima) e ODS 12 (Consumo e produção responsáveis).

Solução tecnológica proposta:

  . Coleta de dados: APIs de fatores de emissão (ex.: Climatiq API, EPA, ou bases nacionais como o SEEG/Observatório do Clima no Brasil), integradas a dados internos simulados de consumo energético, frota e insumos.

  . Modelagem: um modelo de séries temporais (ex.: Prophet ou SARIMA) para prever a trajetória de emissões, combinado com um modelo de ML supervisionado para identificar quais atividades mais contribuem para o total (feature importance).

  . IA generativa: uso de um LLM para gerar automaticamente relatórios narrativos (estilo GRI/CDP) a partir dos dados quantitativos, reduzindo o esforço manual de compliance.

  . Dashboard Streamlit: painel com evolução histórica, projeção futura, simulação de cenários ("e se reduzirmos X% no consumo de diesel da frota?") e exportação automática de relatório em PDF/Word.

## Estrutura de pastas

Estrutura de pastas baseada no **TDSP (Team Data Science Process)**, adaptada para um projeto
de ciência de dados com IA generativa aplicado ao pilar **Ambiental (E)** do ESG,
alinhado aos ODS 12 e 13 da Agenda 2030.

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

- [x] Business Understanding — Project Charter (v1)
- [x] Data Acquisition and Understanding — Data Summary Report (rascunho 1)
- [ ] Data Preparation
- [ ] Modeling
- [ ] Evaluation
- [ ] Deployment (Dashboard Streamlit + Relatório automático via IA generativa)
