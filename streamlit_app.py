import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

st.title("🔍 Teste de Conexão — Google Sheets API")

# ------------------------------
# 1) Criar cliente Google Sheets
# ------------------------------
st.write("### 1️⃣ Carregando credenciais...")
try:
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    st.success("Credenciais carregadas com sucesso!")
except Exception as e:
    st.error("❌ ERRO ao carregar credenciais:")
    st.error(str(e))
    st.stop()

# ------------------------------
# 2) Autorizando gspread
# ------------------------------
st.write("### 2️⃣ Autorizando gspread...")
try:
    client = gspread.authorize(creds)
    st.success("gspread autorizado!")
except Exception as e:
    st.error("❌ ERRO ao autorizar gspread:")
    st.error(str(e))
    st.stop()

# ------------------------------
# 3) Listar planilhas acessíveis pelo serviço
# ------------------------------
st.write("### 3️⃣ Listando todas as planilhas acessíveis pelo serviço...")
try:
    arquivos = client.list_spreadsheet_files()
    st.write("##### 📄 Planilhas encontradas:")
    st.json(arquivos)

    nomes = [a["name"] for a in arquivos]
    st.write("##### 🔍 Nomes detectados:", nomes)
except Exception as e:
    st.error("❌ ERRO ao listar planilhas:")
    st.error(str(e))
    st.stop()

# ------------------------------
# 4) Tentar abrir planilha "Agendamentos"
# ------------------------------
st.write("### 4️⃣ Tentando abrir a planilha **Agendamentos**...")
try:
    sh = client.open("Agendamentos")
    st.success("✅ A planilha 'Agendamentos' foi aberta com sucesso!")
    st.write("ID:", sh.id)
except Exception as e:
    st.error("❌ ERRO ao abrir a planilha 'Agendamentos':")
    st.error(str(e))
    st.stop()

# ------------------------------
# 5) Ler abas internas
# ------------------------------
st.write("### 5️⃣ Tentando ler abas internas da planilha...")

try:
    ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
    st.success("Aba AGENDAMENTOS_ATIVOS encontrada!")
except Exception as e:
    st.error("❌ ERRO: não encontrou aba AGENDAMENTOS_ATIVOS:")
    st.error(str(e))

try:
    ws_hist = sh.worksheet("HISTORICO")
    st.success("Aba HISTORICO encontrada!")
except Exception as e:
    st.error("❌ ERRO: não encontrou aba HISTORICO:")
    st.error(str(e))
