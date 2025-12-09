import streamlit as st
import pandas as pd
from urllib.parse import quote

# =============== TESTE DE CARREGAMENTO REAL DA PLANILHA ===============

st.title("🔍 Teste de Atualização da Planilha — CRM Sportech")

# FORÇAR NENHUM CACHE
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)

SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"

# Carrega a planilha
df = load_sheet(SHEET_ID, SHEET_NAME)

# ---------- TESTE 1: Mostrar última linha recebida ----------
st.subheader("📄 Última linha da planilha (CSV real importado)")
st.write(df.tail(1))

# ---------- TESTE 2: Mostrar colunas reais importadas ----------
st.subheader("📌 Colunas recebidas pelo Streamlit")
st.write(df.columns.tolist())

# ---------- TESTE 3: Mostrar 5 primeiras linhas ----------
st.subheader("🔎 Primeiras linhas da planilha")
st.write(df.head())

# ---------- TESTE 4: Mostrar quantidade de colunas ----------
st.subheader("🔢 Quantidade de colunas")
st.write(len(df.columns))

# ---------- TESTE 5: Timestamp para confirmar atualização ----------
import time
st.subheader("⏱ Timestamp da execução")
st.write(time.time())

st.success("Pronto! Agora altere a planilha e clique em *Reload* no Streamlit.")
