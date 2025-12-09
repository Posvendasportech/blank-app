# streamlit_app.py 
import streamlit as st
import pandas as pd
from urllib.parse import quote
from datetime import datetime

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
st.subheader("Selecione a classificação dos clientes")

# ----------------------------------------
# ⚠️ Caso a planilha esteja vazia
# ----------------------------------------
if df_leads.empty:
    st.warning("⚠️ A planilha de leads não pôde ser carregada.")
    st.stop()

# ----------------------------------------
# 🔘 Filtro de classificação
# ----------------------------------------
class_filter = st.radio(
    "Filtrar por:",
    ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
    horizontal=True
)

# ----------------------------------------
# 🧠 Mapeamento das colunas por índice A–G
# ----------------------------------------
col_data          = df_leads.iloc[:, 0]  # A - Data da compra
col_nome          = df_leads.iloc[:, 1]  # B - Nome
col_email         = df_leads.iloc[:, 2]  # C - Email
col_valor         = df_leads.iloc[:, 3]  # D - Valor gasto total
col_telefone      = df_leads.iloc[:, 4]  # E - Telefone
col_compras       = df_leads.iloc[:, 5]  # F - Nº de compras
col_classificacao = df_leads.iloc[:, 6]  # G - Classificação

# ----------------------------------------
# 🔢 Processando datas
# ----------------------------------------
df_leads["data_dt"] = pd.to_datetime(col_data, errors="coerce")
df_leads["dias_desde_compra"] = (datetime.today() - df_leads["data_dt"]).dt.days

# ----------------------------------------
# 📌 Criar dataframe base de tarefas
# ----------------------------------------
df_tasks = pd.DataFrame({
    "Cliente": col_nome,
    "Telefone": col_telefone,
    "Compras": col_compras,
    "Valor gasto": col_valor,
    "Classificação": col_classificacao,
    "Dias desde compra": df_leads["dias_desde_compra"],
    "Tarefa": "Check-in",
    "Prioridade": "Alta"
})

# ----------------------------------------
# 🔍 Aplicar filtro por classificação
# ----------------------------------------
if class_filter != "Todos":
    df_tasks = df_tasks[df_tasks["Classificação"] == class_filter]

# Regra dos 15 dias para clientes NOVOS
if class_filter == "Novo":
    df_tasks = df_tasks[df_tasks["Dias desde compra"] >= 15]

# ----------------------------------------
# 🖥️ Exibir tabela otimizada
# ----------------------------------------
st.markdown("---")
st.subheader("📌 Lista de clientes que precisam ser chamados hoje")

st.dataframe(df_tasks, use_container_width=True, hide_index=True)

st.info(f"Total de clientes exibidos: {len(df_tasks)}")
