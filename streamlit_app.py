# streamlit_app.py 
import streamlit as st
import pandas as pd
from urllib.parse import quote
from datetime import datetime  # 👈 IMPORTANTE para usar datetime.today()

# ----------------------------------------
# ⚙️ Configuração da página
# ----------------------------------------
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

# ----------------------------------------
# 🔗 IDs / padrões das planilhas
# ----------------------------------------
SHEET2_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
DEFAULT_SHEET2_SHEETNAME = "Total"

# ----------------------------------------
# 📌 Função para carregar planilhas
# ----------------------------------------
@st.cache_data
def load_sheet(sheet_id, sheet_name):
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?"
        f"tqx=out:csv&sheet={quote(sheet_name)}"
    )
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        return pd.DataFrame()

# ----------------------------------------
# 📌 Carregar planilha de leads
# ----------------------------------------
df_leads = load_sheet(SHEET2_ID, DEFAULT_SHEET2_SHEETNAME)

# ----------------------------------------
# 📌 Título da página
# ----------------------------------------
st.title("📅 Tarefas do Dia – CRM Sportech")
st.subheader("Selecione a classificação dos clientes que deseja visualizar")

if df_leads.empty:
    st.warning("⚠️ A planilha de leads não pôde ser carregada.")
else:
    # ------------------------------
    # 🔘 Filtro de classificação
    # ------------------------------
    class_filter = st.radio(
        "Filtrar por classificação:",
        ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
        horizontal=True
    )

    # ------------------------
