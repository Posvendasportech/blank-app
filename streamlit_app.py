import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="CRM Pós-Vendas",
    page_icon="📊",
    layout="wide"
)

# Função para carregar dados
@st.cache_data(ttl=300)
def load_data(worksheet):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet=worksheet, ttl=300)
    return df

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/customer-support.png", width=100)
    st.title("📋 Menu")
    
    page = st.radio(
        "Navegação:",
        ["🏠 Dashboard", "✅ Check-in", "📞 Em Atendimento", "🆘 Suporte", "📜 Histórico"]
    )
    
    st.markdown("---")
    st.caption("CRM Pós-Vendas v1.0")

# ===== DASHBOARD =====
if page == "🏠 Dashboard":
    st.title("🏠 Dashboard - Visão Geral")
    
    # Carregar dados
    df_total = load_data("Total")
    df_agendamentos = load_data("AGENDAMENTOS_ATIVOS")
    df_suporte = load_data("SUPORTE")
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Total de Clientes", len(df_total))
    with col2:
        agendamentos_count = len(df_agendamentos) if not df_agendamentos.empty else 0
        st.metric("📅 Agendamentos Ativos", agendamentos_count)
    with col3:
        suporte_count = len(df_suporte) if not df_suporte.empty else 0
        st.metric("🆘 Casos de Suporte", suporte_count)
    with col4:
        if 'Classificação ' in df_total.columns:
            em_risco = len(df_total[df_total['Classificação '].str.contains('risco', case=False, na=False)])
            st.metric("⚠️ Clientes em Risco", em_risco)
    
    # Gráfico de classificação
    st.markdown("### 📊 Clientes por Classificação")
    if 'Classificação ' in df_total.columns:
        classificacao_counts = df_total['Classificação '].value_counts()
        st.bar_chart(classificacao_counts)
    
    # Tabela dos últimos clientes
    st.markdown("### 🔍 Últimos Clientes Cadastrados")
    if 'Data' in df_total.columns:
        df_display = df_total.sort_values('Data', ascending=False).head(10)
        st.dataframe(df_display, use_container_width=True)

# ===== CHECK-IN =====
elif page == "✅ Check-in":
    st.title("✅ Check-in - Iniciar Atendimento")
    
    df_total = load_data("Total")
    df_agendamentos = load_data("AGENDAMENTOS_ATIVOS")
    
    st.info("💡 Selecione clientes para iniciar o processo de agendamento")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        if 'Classificação ' in df_total.columns:
            classificacoes = ['Todos'] + list(df_total['Classificação '].unique())
            filtro_class = st.selectbox("Filtrar por Classificação:", classificacoes)
    
    with col2:
        if 'Dias desde a compra' in df_total.columns:
            filtro_dias = st.slider("Dias desde a última compra:", 0, 365, (30, 365))
    
    # Aplicar filtros
    df_filtrado = df_total.copy()
    
    if filtro_class != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['Classificação '] == filtro_class]
    
    if 'Dias desde a compra' in df_filtrado.columns:
        df_filtrado = df_filtrado[
            (df_filtrado['Dias desde a compra'] >= filtro_dias[0]) &
            (df_filtrado['Dias desde a compra'] <= filtro_dias[1])
        ]
    
    st.dataframe(df_filtrado, use_container_width=True)
    st.caption(f"Total: {len(df_filtrado)} clientes")

# ===== EM ATENDIMENTO =====
elif page == "📞 Em Atendimento":
    st.title("📞 Em Atendimento - Agendamentos Ativos")
    
    df_agendamentos = load_data("AGENDAMENTOS_ATIVOS")
    
    if not df_agendamentos.empty:
        st.dataframe(df_agendamentos, use_container_width=True)
        st.metric("Total de Agendamentos", len(df_agendamentos))
    else:
        st.info("✅ Nenhum agendamento ativo no momento")

# ===== SUPORTE =====
elif page == "🆘 Suporte":
    st.title("🆘 Suporte - Casos Problemáticos")
    
    df_suporte = load_data("SUPORTE")
    
    if not df_suporte.empty:
        st.dataframe(df_suporte, use_container_width=True)
        st.metric("Total de Casos", len(df_suporte))
    else:
        st.info("✅ Nenhum caso de suporte ativo")

# ===== HISTÓRICO =====
elif page == "📜 Histórico":
    st.title("📜 Histórico de Contatos")
    
    df_historico = load_data("HISTORICO")
    
    if not df_historico.empty:
        # Barra de busca
        busca = st.text_input("🔍 Buscar por nome:", "")
        
        if busca:
            if 'Nome' in df_historico.columns:
                df_filtrado = df_historico[df_historico['Nome'].str.contains(busca, case=False, na=False)]
                st.dataframe(df_filtrado, use_container_width=True)
        else:
            st.dataframe(df_historico, use_container_width=True)
        
        st.metric("Total de Interações", len(df_historico))
    else:
        st.info("Nenhum histórico registrado ainda")
