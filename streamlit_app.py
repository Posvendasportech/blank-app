import streamlit as st
import pandas as pd
from urllib.parse import quote

st.title("🔍 Teste de Secrets no Streamlit Cloud")

# Mostrar todos os secrets carregados
st.subheader("🔐 Secrets carregados:")
st.write(st.secrets)

# Testar se a chave 'nome' existe
st.subheader("📝 Teste de leitura da chave 'nome'")

try:
    sheet_id = st.secrets["nome"]
    st.success(f"Chave 'nome' encontrada: {sheet_id}")
except KeyError:
    st.error("❌ ERRO: A chave 'nome' NÃO foi encontrada no st.secrets")
    st.stop()

# Testar carregar a planilha via CSV
st.subheader("📄 Teste de carregamento da planilha")

try:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    df = pd.read_csv(url)
    st.success("Planilha carregada com sucesso!")
    st.dataframe(df.head())
except Exception as e:
    st.error("❌ ERRO ao carregar a planilha:")
    st.write(str(e))
