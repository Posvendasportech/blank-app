import streamlit as st
import pandas as pd
from urllib.parse import quote
from datetime import datetime

# ------------------------------
# Função para carregar planilha
# ------------------------------
@st.cache_data
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)

# ------------------------------
# Ler a planilha
# ------------------------------
SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"

df = load_sheet(SHEET_ID, SHEET_NAME)

# ------------------------------
# DEBUG — Ver colunas importadas
# ------------------------------
st.subheader("DEBUG — Verificando colunas da planilha")
st.write("Quantidade de colunas:", len(df.columns))
st.write("Nomes das colunas:", df.columns.tolist())
st.write(df.head())
