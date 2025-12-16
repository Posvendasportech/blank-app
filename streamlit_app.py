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

# Conexão com Google Sheets
@st.cache_data(ttl=300)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Total", ttl=300)
    return df

# Carregar dados
try:
    df_total = load_data()
    
    # Debug: mostrar tipo e conteúdo
    st.write("Tipo do retorno:", type(df_total))
    st.write("Conteúdo:", df_total)
    
    if isinstance(df_total, pd.DataFrame):
        st.success(f"✅ Dados carregados: {len(df_total)} clientes encontrados")
        
        # Preview dos dados
        with st.expander("👀 Visualizar Dados"):
            st.dataframe(df_total, use_container_width=True)
    else:
        st.warning("⚠️ Dados retornados não são um DataFrame")
        
except Exception as e:
    st.error(f"❌ Erro ao conectar com Google Sheets: {e}")
    st.info("Verifique se a aba 'Total' existe na planilha")
