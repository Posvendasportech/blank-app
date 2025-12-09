# streamlit_app.py 
import streamlit as st
import pandas as pd
from urllib.parse import quote

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

st.title("📅 Tarefas do Dia – CRM Sportech")
st.subheader("Selecione a classificação dos clientes que deseja visualizar")

# ------------------------------
# 🔘 Filtro de classificação
# ------------------------------
class_filter = st.radio(
    "Filtrar por classificação:",
    ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
    horizontal=True
)

# ------------------------------
# 🧠 Processar colunas pelo índice (A-G)
# ------------------------------
col_data = df_leads.iloc[:, 0]          # A - Data do último pedido
col_nome = df_leads.iloc[:, 1]          # B
col_email = df_leads.iloc[:, 2]         # C
col_valor = df_leads.iloc[:, 3]         # D
col_telefone = df_leads.iloc[:, 4]      # E
col_compras = df_leads.iloc[:, 5]       # F
col_classificacao = df_leads.iloc[:, 6] # G

# transformar data para datetime
df_leads["data_dt"] = pd.to_datetime(col_data, errors="coerce")

# calcular dias desde a última compra
df_leads["dias_desde_compra"] = (datetime.today() - df_leads["data_dt"]).dt.days

# aplicar filtro por classificação
if class_filter != "Todos":
    df_leads_filtered = df_leads[df_leads.iloc[:, 6] == class_filter]
else:
    df_leads_filtered = df_leads.copy()

# regra especial para NOVOS → só aparecem se passaram 15 dias desde a compra
if class_filter == "Novo":
    df_leads_filtered = df_leads_filtered[df_leads_filtered["dias_desde_compra"] >= 15]

# criar df_tasks com base no filtrado
df_tasks = pd.DataFrame({
    "Cliente": df_leads_filtered.iloc[:, 1],
    "Telefone": df_leads_filtered.iloc[:, 4],
    "Compras": df_leads_filtered.iloc[:, 5],
    "Valor": df_leads_filtered.iloc[:, 3],
    "Classificação": df_leads_filtered.iloc[:, 6],
    "Dias desde compra": df_leads_filtered["dias_desde_compra"],
    "Tarefa": ["Check-in"] * len(df_leads_filtered),
    "Prioridade": ["Alta"] * len(df_leads_filtered),
    "Status": ["Pendente"] * len(df_leads_filtered)
})

st.markdown("---")
st.subheader("📌 Tarefas pendentes")

# ------------------------------
# Renderização das tarefas
# ------------------------------
for idx, row in df_tasks.iterrows():
    with st.container():
        cols = st.columns([2, 2, 1, 1, 2, 1, 1])

        cols[0].markdown(f"**👤 {row['Cliente']}**")
        cols[1].markdown(f"📱 {row['Telefone']}")
        cols[2].write(f"🛒 {row['Compras']}")
        cols[3].write(f"💰 R$ {row['Valor']}")
        cols[4].write(f"📝 {row['Tarefa']}")
        cols[5].write("🔴 Alta")
        cols[6].write(row["Status"])

        if cols[6].button("✔ Concluir", key=f"done_{idx}"):
            st.success(f"Tarefa concluída para {row['Cliente']}!")
