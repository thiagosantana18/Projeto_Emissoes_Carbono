# App/dashboard

Aplicação Streamlit do projeto (`app.py`).

## Funcionalidades (Etapa 2)

- Interface organizada em 4 abas: Visão Geral, Notícias & Nuvem de Palavras,
  Dados do Projeto, Upload & Download.
- Cache (`st.cache_data`) no carregamento dos dados e no cálculo de
  frequência de palavras.
- Estado de sessão (`st.session_state`) para persistir filtros, histórico
  de uploads e o dataset combinado (amostra + dados enviados pelo usuário)
  ao longo da navegação.
- Nuvem de palavras (pacote `wordcloud`) e estatísticas básicas geradas a
  partir dos dados coletados em `Data/raw/` (ver `Code/data_acquisition/`).
- Upload de CSV pelo usuário, com validação de schema e mesclagem ao
  dataset já exibido, além de botão de download do resultado consolidado.

## Como rodar

A partir da raiz do projeto:

```bash
pip install -r requirements.txt
streamlit run App/dashboard/app.py
```

Ver `README_app.md` nesta pasta para mais detalhes.
