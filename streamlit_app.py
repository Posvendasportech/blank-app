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

# Função para carregar todas as abas
@st.cache_data(ttl=300)
def load_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    data = {}
    abas = ["AGENDAMENTOS_ATIVOS", "EM_ATENDIMENTO", "HISTORICO"]
    
    for aba in abas:
        try:
            df = conn.read(worksheet=aba, ttl=300)
            data[aba] = df
            st.success(f"✅ Aba '{aba}' carregada: {len(df)} registros")
        except Exception as e:
            st.warning(f"⚠️ Erro ao carregar '{aba}': {e}")
            data[aba] = pd.DataFrame()
    
    return data

# Carregar dados
try:
    all_data = load_all_data()
    
    # Sidebar para seleção de aba
    with st.sidebar:
        st.header("📋 Selecione a Aba")
        aba_selecionada = st.selectbox(
            "Visualizar:",
            ["AGENDAMENTOS_ATIVOS", "EM_ATENDIMENTO", "HISTORICO"]
        )
    
    # Exibir dados da aba selecionada
    st.header(f"📊 {aba_selecionada.replace('_', ' ').title()}")
    
    df_atual = all_data[aba_selecionada]
    
    if not df_atual.empty:
        st.dataframe(df_atual, use_container_width=True)
        
        # Métricas
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total de Registros", len(df_atual))
        with col2:
            st.metric("Colunas", len(df_atual.columns))
    else:
        st.info("Nenhum registro encontrado nesta aba")
        
except Exception as e:
    st.error(f"❌ Erro: {e}")
