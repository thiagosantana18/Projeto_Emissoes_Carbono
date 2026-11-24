"""
esg_core — camada de dados compartilhada do projeto.

Usado pelo dashboard (Streamlit), pela API (FastAPI) e pelos scripts de
preparação de dados. Nenhum módulo daqui depende de Streamlit ou FastAPI,
o que permite testá-los isoladamente (ver tests/).
"""
