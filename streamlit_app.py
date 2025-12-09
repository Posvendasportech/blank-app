import streamlit as st
import pandas as pd
from urllib.parse import quote

# ------------------------------
# Função para carregar planilha (precisa vir ANTES do df = load_sheet)
# ------------------------------
@st.cache_data
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)

# ------------------------------
# Ler planilha
# ------------------------------
SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"

df = load_sheet(SHEET_ID, SHEET_NAME)

# ------------------------------
# DEBUG – ver origem real dos dados
# ------------------------------
st.subheader("DEBUG — Dados importados da planilha")

st.write("🔢 Quantidade de colunas:", len(df.columns))
st.write("📌 Nomes das colunas:", df.columns.tolist())
st.write("👀 Prévia dos dados:")
st.write(df.head())
