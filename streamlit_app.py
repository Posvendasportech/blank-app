import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Configuração da página
st.set_page_config(
    page_title="CRM Pós-Vendas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título principal
st.title("🎯 CRM de Pós-Vendas")
st.markdown("### Sistema de Gestão de Relacionamento com Clientes")

# Listar abas disponíveis
def list_worksheets():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # Pegar o spreadsheet diretamente
        spreadsheet = conn._instance._client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1JEoG2HsPyrMAQ6NrNpOSmFrkiRseY1gsxEWnf-zDuu8/edit?usp=sharing"
        )
        worksheets = spreadsheet.worksheets()
        
        st.success("✅ Planilha conectada!")
        st.write("**Abas disponíveis:**")
        for ws in worksheets:
            st.write(f"- {ws.title}")
        
        return [ws.title for ws in worksheets]
    except Exception as e:
        st.error(f"Erro: {e}")
        import traceback
        st.code(traceback.format_exc())
        return []

# Executar
abas = list_worksheets()
