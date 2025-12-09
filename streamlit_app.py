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
# 📌 Aba 1 — Tarefas do Dia
# ------------------------------

st.title("📅 Tarefas do Dia – CRM Sportech")

# Carrega os leads
df_leads = load_sheet(SHEET2_ID, DEFAULT_SHEET2_SHEETNAME)

st.subheader("Lista de tarefas (exemplo usando apenas leads por enquanto)")

# Exemplo provisório: criando tarefas falsas apenas a partir dos leads
# Depois isso será substituído pela planilha de agendamentos de verdade
df_tasks = pd.DataFrame({
    "Cliente": df_leads["Nome"].head(10),  # usa primeiros 10 só para demonstrar
    "Pedido": df_leads["Pedido"].head(10),
    "Classificação": ["Novo"] * 10,
    "Tarefa": ["Check-in Inicial"] * 10,
    "Prioridade": ["Alta", "Média", "Baixa", "Alta", "Média", "Alta", "Baixa", "Média", "Alta", "Baixa"],
    "Status": ["Pendente"] * 10
})

# Função para exibir botões de concluir
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
        st.success(f"Tarefa concluída: {row['Cliente']} — {row['Tarefa']}")
        # Aqui depois vamos remover a tarefa e atualizar a planilha
