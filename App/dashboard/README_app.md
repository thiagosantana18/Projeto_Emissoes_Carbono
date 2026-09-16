# Demo (Etapa 2) — Monitoramento e Previsão de Emissões de Carbono Corporativas

Aplicação Streamlit evoluída, com interface em abas, cache, estado de
sessão, dados coletados via web scraping (BeautifulSoup), nuvem de palavras
e serviço de upload/download de CSV.

## Estrutura relevante

```
.
├── app.py                                  # Aplicação Streamlit (interface)
├── requirements.txt
├── Code/
│   └── data_acquisition/
│       ├── scrape_ods_ecycle.py            # Coleta conteúdo sobre ODS 12/13
│       └── scrape_noticias_esg.py          # Coleta manchetes de notícias ESG
└── Data/
    ├── raw/
    │   ├── ods_conteudo.csv / .txt         # Saída do scrape_ods_ecycle.py
    │   ├── noticias_esg.csv / .txt         # Saída do scrape_noticias_esg.py
    │   └── NOTA_COLETA.md                  # Como e por que os dados foram obtidos
    └── processed/
        └── amostra_emissoes.csv            # Dataset de atividade/emissão (amostra)
```

## Como executar

```bash
# 1. (opcional) crie um ambiente virtual
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. instale as dependências
pip install -r requirements.txt

# 3. (opcional) rode a coleta de dados — requer acesso à internet
python Code/data_acquisition/scrape_ods_ecycle.py
python Code/data_acquisition/scrape_noticias_esg.py

# 4. rode a aplicação
streamlit run app.py
```

A aplicação abrirá em `http://localhost:8501`.

## O que mudou nesta etapa

- **Interface em abas**: Visão Geral · Notícias & Nuvem de Palavras · Dados
  do Projeto · Upload & Download.
- **Cache (`st.cache_data`)**: os dados carregados de disco (emissões,
  notícias, conteúdo dos ODS) e o cálculo de frequência de palavras são
  cacheados, evitando reprocessamento a cada interação.
- **Estado de sessão (`st.session_state`)**: filtros selecionados,
  contador de gerações da nuvem de palavras, histórico de uploads e o
  dataset combinado (amostra + uploads do usuário) persistem enquanto o
  usuário navega entre as abas.
- **Web scraping com BeautifulSoup**: dois scripts independentes, com
  verificação de `robots.txt` embutida (`urllib.robotparser`) antes de
  qualquer coleta.
- **Nuvem de palavras e estatísticas básicas**: geradas a partir do
  conteúdo coletado (manchetes de notícias ou trechos sobre os ODS 12/13),
  com fallback para um gráfico de frequência caso o pacote `wordcloud` não
  esteja instalado.
- **Upload e download de CSV**: o usuário pode enviar um CSV no mesmo
  formato da amostra para complementar os dados exibidos, e baixar o
  dataset consolidado a qualquer momento.

## Observação sobre os dados coletados

Ver `Data/raw/NOTA_COLETA.md` para o detalhamento de como os arquivos de
`Data/raw/` foram obtidos e como reproduzir a coleta com os scripts.
