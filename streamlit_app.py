import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="CRM Pós-Vendas", page_icon="📊", layout="wide")

st.title("🎯 CRM de Pós-Vendas")

# Botão para limpar cache
if st.button("🔄 Limpar Cache"):
    st.cache_data.clear()
    st.rerun()

# Mostrar qual URL está configurada
st.write("**URL configurada nos secrets:**")
st.code(st.secrets["connections"]["gsheets"]["spreadsheet"])

def list_worksheets():
    conn = st.connection("gsheets", type=GSheetsConnection)
    url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    
    st.write(f"Tentando conectar em: {url}")
    
    spreadsheet = conn._instance._client.open_by_url(url)
    worksheets = spreadsheet.worksheets()
    
    st.success(f"✅ Planilha '{spreadsheet.title}' conectada!")
    for ws in worksheets:
        st.write(f"- {ws.title}")

list_worksheets()
