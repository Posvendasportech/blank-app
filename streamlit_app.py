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
@st.cache_data(ttl=300)  # Cache de 5 minutos
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Especificar o spreadsheet ID da sua planilha
    df = conn.read(
        spreadsheet="1JEoG2HsPyrMAQ6NrNpOSmFrkiRseY1gsxEWnf-zDuu8",
        worksheet="Total",
        ttl=300
    )
    return df

# Carregar dados
try:
    df_total = load_data()
    st.success(f"✅ Dados carregados: {len(df_total)} clientes encontrados")
    
    # Preview dos dados
    with st.expander("👀 Visualizar Dados"):
        st.dataframe(df_total, use_container_width=True)
        
except Exception as e:
    st.error(f"❌ Erro ao conectar com Google Sheets: {e}")
    st.info("Verifique se o secrets.toml está configurado corretamente")

# Sidebar com informações
with st.sidebar:
    st.header("📋 Navegação")
    st.info("Use o menu acima para navegar entre as páginas")
    st.markdown("---")
    st.markdown("**Páginas disponíveis:**")
    st.markdown("- 📊 Dashboard")
    st.markdown("- ✅ Check-in")
    st.markdown("- 📞 Em Atendimento")
    st.markdown("- 🆘 Suporte")
    st.markdown("- 📜 Histórico")
