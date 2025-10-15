import streamlit as st
import pandas as pd

st.title("Conectando Google Sheets ao Streamlit")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"

try:
    df = pd.read_csv(SHEET_URL)
    st.success("Planilha carregada com sucesso! 🎉")
    st.dataframe(df)
except Exception as e:
    st.error(f"Erro ao carregar a planilha: {e}")
