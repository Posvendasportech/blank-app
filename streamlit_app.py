# streamlit_app.py 
import streamlit as st
import pandas as pd
import time
import plotly.express as px
from datetime import datetime, timedelta
from urllib.parse import quote
import re

# ------------------------------
# ⚙️ Configuração da página
# ------------------------------
st.set_page_config(page_title="Dashboard de Vendas", page_icon="📊", layout="wide")

# ------------------------------
# 🔗 IDs / padrões das planilhas
# ------------------------------
SHEET2_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
DEFAULT_SHEET2_SHEETNAME = "Total"

# ------------------------------
# 📌 Função para carregar planilhas do Google Sheets
# ------------------------------
@st.cache_data
def load_sheet(sheet_id, sheet_name):
    """
    Carrega uma planilha do Google Sheets usando CSV export.
    """
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar a planilha '{sheet_name}': {e}")
        return pd.DataFrame()

# ------------------------------
# 📌 Carrega planilha de leads
# ------------------------------
df_leads = load_sheet(SHEET2_ID, DEFAULT_SHEET2_SHEETNAME)

st.title("📅 Tarefas do Dia – CRM Sportech")

if df_leads.empty:
    st.warning("⚠️ Não foi possível carregar a planilha de leads.")
else:
    st.subheader("Lista de tarefas (exemplo usando apenas leads por enquanto)")

    # Exemplo provisório: criando tarefas fictícias com base nos leads
    df_tasks = pd.DataFrame({
        "Cliente": df_leads["Nome"].head(10),  # usa os primeiros 10 apenas para demonstração
        "Pedido": df_leads["Pedido"].head(10),
        "Classificação": ["Novo"] * 10,
        "Tarefa": ["Check-in Inicial"] * 10,
        "Prioridade": ["Alta", "Média", "Baixa", "Alta", "Média", "Alta", "Baixa", "Média", "Alta", "Baixa"],
        "Status": ["Pendente"] * 10
    })

    # Exibir tarefas com botão de concluir
    for index, row in df_tasks.iterrows():
        cols = st.columns([2, 1, 2, 2, 1, 2, 1])

        cols[0].write(row["Cliente"])
        cols[1].write(row["Pedido"])
        cols[2].write(row["Classificação"])
        cols[3].write(row["Tarefa"])
        cols[4].write(row["Prioridade"])
        cols[5].write(row["Status"])

        # Botão individual para cada tarefa
        if cols[6].button("Concluir", key=f"done_{index}"):
            st.success(f"✔️ Tarefa concluída: {row['Cliente']} — {row['Tarefa']}")
            # Aqui depois vamos remover a tarefa e atualizar a planilha
