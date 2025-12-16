# ============================================================================
# CRM PÓS-VENDAS - STREAMLIT APP
# Versão: 1.0
# Descrição: Sistema de gestão de relacionamento com clientes
# ============================================================================

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# ============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================================
st.set_page_config(
    page_title="CRM Pós-Vendas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

@st.cache_data(ttl=60)  # Cache por 60 segundos
def carregar_dados(nome_aba):
    """
    Carrega dados de uma aba específica do Google Sheets
    
    Args:
        nome_aba (str): Nome da aba a ser carregada
    
    Returns:
        DataFrame: Dados da aba
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=nome_aba, ttl=60)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar aba '{nome_aba}': {e}")
        return pd.DataFrame()

# ============================================================================
# SIDEBAR - MENU DE NAVEGAÇÃO
# ============================================================================

with st.sidebar:
    st.title("📋 Menu Principal")
    st.markdown("---")
    
    # Seleção de página
    pagina = st.radio(
        "Navegação:",
        ["✅ Check-in", "📞 Em Atendimento", "🆘 Suporte", "📜 Histórico"],
        index=0
    )
    
    st.markdown("---")
    st.caption("CRM Pós-Vendas v1.0")
    st.caption("Desenvolvido com Streamlit")

# ============================================================================
# PÁGINA: CHECK-IN
# ============================================================================

if pagina == "✅ Check-in":
    
    # --- CABEÇALHO ---
    st.title("✅ Check-in de Clientes")
    st.markdown("Selecione clientes para iniciar o fluxo de atendimento")
    st.markdown("---")
    
    # --- SELETOR DE CLASSIFICAÇÃO ---
    st.subheader("📂 Selecione a Classificação")
    
    classificacoes_disponiveis = [
        "Total", 
        "Novo", 
        "Promissor", 
        "Leal", 
        "Campeão", 
        "Em risco", 
        "Dormente"
    ]
    
    classificacao_selecionada = st.selectbox(
        "Escolha qual grupo de clientes visualizar:",
        classificacoes_disponiveis,
        index=0,
        help="Cada classificação representa um perfil de cliente diferente"
    )
    
    st.info(f"📊 Visualizando: **{classificacao_selecionada}**")
    st.markdown("---")
    
    # --- CARREGAR DADOS DA ABA SELECIONADA ---
    st.subheader("👥 Lista de Clientes")
    
    with st.spinner(f"Carregando clientes de '{classificacao_selecionada}'..."):
        df_clientes = carregar_dados(classificacao_selecionada)
    
    # --- VERIFICAR SE HÁ DADOS ---
    if df_clientes.empty:
        st.warning(f"⚠️ Nenhum cliente encontrado na categoria '{classificacao_selecionada}'")
        st.stop()
    
    # --- MOSTRAR INFORMAÇÕES BÁSICAS ---
    st.success(f"✅ {len(df_clientes)} clientes encontrados")
    
    # --- EXIBIR PREVIEW DOS DADOS (para debug) ---
    with st.expander("🔍 Preview dos dados (Debug)"):
        st.write("**Colunas disponíveis:**")
        st.write(df_clientes.columns.tolist())
        st.write("**Primeiras 5 linhas:**")
        st.dataframe(df_clientes.head(), use_container_width=True)
    
    st.markdown("---")
    
    # --- FILTROS ---
    st.subheader("🔍 Filtros")
    
    col_filtro1, col_filtro2 = st.columns(2)
    
    with col_filtro1:
        busca_nome = st.text_input(
            "Buscar por nome:",
            "",
            placeholder="Digite o nome do cliente..."
        )
    
    with col_filtro2:
        # Verificar se a coluna existe antes de criar o filtro
        if 'Dias desde a compra' in df_clientes.columns:
            # Pegar valores mínimo e máximo
            dias_min = 0
            dias_max = int(df_clientes['Dias desde a compra'].max()) if df_clientes['Dias desde a compra'].max() > 0 else 365
            
            filtro_dias = st.slider(
                "Dias desde última compra:",
                min_value=dias_min,
                max_value=dias_max,
                value=(dias_min, dias_max)
            )
        else:
            st.warning("⚠️ Coluna 'Dias desde a compra' não encontrada")
            filtro_dias = None
    
    # --- APLICAR FILTROS ---
    df_filtrado = df_clientes.copy()
    
    # Filtro por nome
    if busca_nome:
        if 'Nome' in df_filtrado.columns:
            df_filtrado = df_filtrado[
                df_filtrado['Nome'].str.contains(busca_nome, case=False, na=False)
            ]
    
    # Filtro por dias
    if filtro_dias and 'Dias desde a compra' in df_filtrado.columns:
        df_filtrado = df_filtrado[
            (df_filtrado['Dias desde a compra'] >= filtro_dias[0]) &
            (df_filtrado['Dias desde a compra'] <= filtro_dias[1])
        ]
    
    st.markdown("---")
    
    # --- EXIBIR CARDS DOS CLIENTES ---
    st.subheader(f"📋 Clientes ({len(df_filtrado)} encontrados)")
    
    if df_filtrado.empty:
        st.info("Nenhum cliente encontrado com os filtros aplicados")
    else:
        # Loop para criar um card para cada cliente
        for index, cliente in df_filtrado.iterrows():
            
            # Container para cada card
            with st.container():
                
                # Criar 3 colunas: Informações | Métricas | Ação
                col_info, col_metricas, col_acao = st.columns([2, 3, 1])
                
                # --- COLUNA 1: INFORMAÇÕES BÁSICAS ---
                with col_info:
                    nome = cliente.get('Nome', 'Nome não disponível')
                    email = cliente.get('Email', 'Email não disponível')
                    telefone = cliente.get('Telefone', 'Telefone não disponível')
                    
                    st.markdown(f"### 👤 {nome}")
                    st.caption(f"📧 {email}")
                    st.caption(f"📱 {telefone}")
                
                              # --- COLUNA 2: MÉTRICAS ---
                with col_metricas:
                    met1, met2, met3 = st.columns(3)
                    
                    with met1:
                        valor = cliente.get('Valor', 0)
                        if pd.notna(valor) and valor != '':
                            try:
                                st.metric("💰 Gasto Total", f"R$ {float(valor):,.2f}")
                            except:
                                st.metric("💰 Gasto Total", "R$ 0,00")
                        else:
                            st.metric("💰 Gasto Total", "R$ 0,00")
                    
                    with met2:
                        compras = cliente.get('Compras', 0)
                        if pd.notna(compras) and compras != '':
                            try:
                                st.metric("🛒 Compras", int(float(compras)))
                            except:
                                st.metric("🛒 Compras", "0")
                        else:
                            st.metric("🛒 Compras", "0")
                    
                    with met3:
                        dias = cliente.get('Dias desde a compra', 0)
                        if pd.notna(dias) and dias != '':
                            try:
                                # Arredondar para número inteiro
                                st.metric("📅 Dias", int(round(float(dias))))
                            except:
                                st.metric("📅 Dias", "0")
                        else:
                            st.metric("📅 Dias", "0")

                
                # --- COLUNA 3: BOTÃO DE AÇÃO ---
                with col_acao:
                    st.write("")  # Espaçamento
                    st.write("")  # Espaçamento
                    
                    # Botão de check-in (por enquanto só visual)
                    if st.button(
                        "✅ Check-in",
                        key=f"btn_checkin_{index}",
                        type="primary",
                        use_container_width=True
                    ):
                        st.success(f"Check-in de {nome} será implementado!")
                        # Aqui vamos adicionar a lógica depois
                
                # Linha separadora entre cards
                st.markdown("---")

# ============================================================================
# OUTRAS PÁGINAS (placeholder por enquanto)
# ============================================================================

elif pagina == "📞 Em Atendimento":
    st.title("📞 Em Atendimento")
    st.info("Esta página será implementada em breve")

elif pagina == "🆘 Suporte":
    st.title("🆘 Suporte")
    st.info("Esta página será implementada em breve")

elif pagina == "📜 Histórico":
    st.title("📜 Histórico")
    st.info("Esta página será implementada em breve")
