"""
Entrypoint do dashboard (Streamlit multipágina).

Executar a partir da raiz do projeto:
    streamlit run App/dashboard/app.py

As páginas ficam em App/dashboard/views/ e são registradas com st.navigation
(menu lateral agrupado por seção). Toda a lógica de dados vem de Code/esg_core.
"""
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
for _cand in [_AQUI, *_AQUI.parents]:                       # localiza <raiz>/Code/esg_core
    if (_cand / "Code" / "esg_core").is_dir():
        sys.path.insert(0, str(_cand / "Code"))
        break
else:
    raise RuntimeError("Pasta Code/esg_core não encontrada acima de App/dashboard/.")
sys.path.insert(0, str(_AQUI))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Emissões de Carbono | ESG", page_icon="🌱", layout="wide")

from ui_helpers import COR, inicializar_estado, manter_estado  # noqa: E402

inicializar_estado()
manter_estado()

paginas = {
    "Projeto": [
        st.Page("views/visao_geral.py", title="Visão geral", icon="🏠", default=True),
    ],
    "Dados e análises": [
        st.Page("views/dados_graficos.py", title="Dados e gráficos", icon="📊"),
        st.Page("views/noticias.py", title="Notícias e nuvem de palavras", icon="📰"),
        st.Page("views/estatisticas.py", title="Estatísticas e qualidade", icon="📈"),
    ],
    "Serviços": [
        st.Page("views/upload_download.py", title="Upload e download", icon="📤"),
        st.Page("views/api_explorer.py", title="API (FastAPI)", icon="🔌"),
    ],
    "IA e LLM": [
        st.Page("views/analise_texto.py", title="Análise de texto (LLM local)", icon="🤖"),
        st.Page("views/preparacao_llm.py", title="Preparação dos dados", icon="🧪"),
    ],
}

with st.sidebar:
    st.markdown(f"<h3 style='color:{COR};margin-bottom:0'>🌱 Emissões de Carbono</h3>"
                "<small>ESG · Ambiental · ODS 12 e 13</small>", unsafe_allow_html=True)

st.navigation(paginas).run()
