# streamlit_app.py 
import streamlit as st
import pandas as pd
from urllib.parse import quote
import re

st.set_page_config(page_title="Dashboard de Vendas", page_icon="📊", layout="wide")

SHEET2_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
DEFAULT_SHEET2_SHEETNAME = "Total"

@st.cache_data
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        return pd.DataFrame()

df_leads = load_sheet(SHEET2_ID, DEFAULT_SHEET2_SHEETNAME)

st.title("📅 Tarefas do Dia – CRM Sportech")

if df_leads.empty:
    st.warning("⚠️ A planilha de leads não pôde ser carregada.")
else:
    st.subheader("Lista de tarefas – usando TELEFONE como identificador")

    # --------------------------
    # 🛠️ PROCESSAR COLUNA DE VALOR + TELEFONE
    # --------------------------

    def extract_value(s):
        match = re.search(r'R\$\s*(\d+[\.,]?\d*)', str(s))
        return float(match.group(1).replace(",", ".")) if match else None

    def extract_phone(s):
        match = re.search(r'\+?\d{10,15}', str(s))
        return match.group(0) if match else None

    df_leads["Valor_num"] = df_leads["Valor"].apply(extract_value)
    df_leads["Telefone_clean"] = df_leads["Valor"].apply(extract_phone)

    # Garantir que não existam vazios
    df_leads = df_leads.dropna(subset=["Telefone_clean"])

    # Pegamos só 10 para demonstrar
    df_example = df_leads.head(10)

    df_tasks = pd.DataFrame({
        "Cliente": df_example["Nome"],
        "Telefone": df_example["Telefone_clean"],  # **IDENTIFICADOR**
        "Compras": df_example["Compras"],
        "Total gasto": df_example["Valor_num"],
        "Classificação": df_example["Classificação"],
        "Tarefa": ["Check-in Inicial"] * len(df_example),
        "Prioridade": ["Alta"] * len(df_example),
        "Status": ["Pendente"] * len(df_example)
    })

    # --------------------------
    # 📌 EXIBIR TAREFAS
    # --------------------------
    for idx, row in df_tasks.iterrows():
        cols = st.columns([2, 2, 1, 1, 2, 1, 1])

        cols[0].write(row["Cliente"])
        cols[1].write(row["Telefone"])
        cols[2].write(row["Compras"])
        cols[3].write(f"R$ {row['Total gasto']}")
        cols[4].write(row["Tarefa"])
        cols[5].write(row["Prioridade"])
        cols[6].write(row["Status"])

        if cols[6].button("Concluir", key=f"done_{idx}"):
            st.success(f"Tarefa concluída para: {row['Cliente']} ({row['Telefone']})")
