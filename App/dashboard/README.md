# App/dashboard — Streamlit multipágina

```bash
streamlit run App/dashboard/app.py       # a partir da raiz do projeto
```
`app.py` registra as páginas de `views/` com `st.navigation`. `ui_helpers.py` concentra cache
(`st.cache_data` com chave = data de modificação dos CSV), estado de sessão e widgets persistentes entre páginas.
