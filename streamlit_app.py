import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

# ============================
# Configuração da página
# ============================
st.set_page_config(page_title="Dashboard de Vendas", layout="wide")

# ============================
# Ler a variável secreta do GitHub
# ============================
credenciais_json = os.getenv("PLANILHA_CRM_POSVENDAS")

if not credenciais_json:
    st.error("⚠️ A variável PLANILHA_CRM_POSVENDAS não está definida! Verifique secrets no GitHub.")
    st.stop()  # para o app aqui, pois não tem credenciais

try:
    credenciais_dict = json.loads(credenciais_json)
except Exception as e:
    st.error(f"⚠️ Erro ao ler o JSON da variável: {e}")
    st.stop()

# ============================
# Conectar ao Google Sheets
# ============================
try:
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(credenciais_dict, scopes=scope)
    client = gspread.authorize(creds)

    # Abrir planilha e aba
    sheet = client.open("Controle de Vendas").worksheet("Base")
    dados = sheet.get_all_records()
    df = pd.DataFrame(dados)

    # Selecionar colunas A, B e I
    df = df.iloc[:, [0, 1, 8]]
    df.columns = ["Data", "Classificacao", "Valor"]

    # Converter tipos
    df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    st.success("✅ Planilha carregada com sucesso!")

except Exception as e:
    st.error(f"⚠️ Erro ao conectar à planilha: {e}")
    st.stop()

# ============================
# Mostrar dados e gráficos simples
# ============================
st.header("📋 Vendas Recentes")
st.dataframe(df, use_container_width=True)

st.header("📊 Receita por Classificação")
receita_por_classificacao = df.groupby("Classificacao")["Valor"].sum().reset_index()
st.bar_chart(data=receita_por_classificacao.set_index("Classificacao"))
