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

# Conexão com Google Sheets - SEM CACHE para debug
def load_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        st.write("✅ Conexão criada")
        
        df = conn.read(worksheet="Total", usecols=list(range(10)))
        st.write("✅ Leitura executada")
        st.write("Tipo:", type(df))
        
        return df
    except Exception as e:
        st.error(f"Erro interno: {str(e)}")
        st.write("Tipo do erro:", type(e))
        import traceback
        st.code(traceback.format_exc())
        return None

# Carregar dados
df_total = load_data()

if df_total is not None:
    st.success(f"✅ Dados carregados: {len(df_total)} clientes")
    st.dataframe(df_total, use_container_width=True)
