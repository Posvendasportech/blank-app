import json
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

credenciais_json = os.getenv("PLANILHA_CRM_POSVENDAS")
credenciais_dict = json.loads(credenciais_json)

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(credenciais_dict, scopes=scope)
client = gspread.authorize(creds)

try:
    sheet = client.open("Controle de Vendas").worksheet("Base")
    dados = sheet.get_all_records()
    st.success(f"✅ Planilha carregada com sucesso! Total de linhas: {len(dados)}")
except Exception as e:
    st.error(f"⚠️ Erro ao conectar à planilha: {e}")
