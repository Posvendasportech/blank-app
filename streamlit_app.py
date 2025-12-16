import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="CRM Pós-Vendas", page_icon="📊", layout="wide")

# Função para carregar dados
@st.cache_data(ttl=60)
def load_data(worksheet):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet=worksheet, ttl=60)
    return df

# Função para adicionar linha em uma aba
def add_to_worksheet(worksheet_name, data_row):
    """Adiciona uma linha na planilha especificada"""
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Carrega dados atuais
    df_atual = conn.read(worksheet=worksheet_name)
    
    # Adiciona nova linha
    df_novo = pd.concat([df_atual, pd.DataFrame([data_row])], ignore_index=True)
    
    # Atualiza a planilha
    conn.update(worksheet=worksheet_name, data=df_novo)
    st.cache_data.clear()
    return True

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/customer-support.png", width=100)
    st.title("📋 Menu")
    page = st.radio("Navegação:", ["✅ Check-in", "📞 Em Atendimento", "🆘 Suporte", "📜 Histórico"])

# ===== CHECK-IN =====
if page == "✅ Check-in":
    st.title("✅ Check-in de Clientes")
    st.markdown("Selecione clientes para iniciar o fluxo de atendimento personalizado")
    
    # Seleção de classificação
    col1, col2 = st.columns([1, 3])
    
    with col1:
        classificacao_selecionada = st.selectbox(
            "📂 Selecione a Classificação:",
            ["Total", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
            help="Escolha qual grupo de clientes deseja visualizar"
        )
    
    with col2:
        st.info(f"💡 Visualizando clientes: **{classificacao_selecionada}**")
    
    # Carregar dados da aba selecionada
    try:
        df_clientes = load_data(classificacao_selecionada)
        
        if df_clientes.empty:
            st.warning(f"Nenhum cliente encontrado na categoria '{classificacao_selecionada}'")
        else:
            # Filtros adicionais
            st.markdown("### 🔍 Filtros")
            col_f1, col_f2, col_f3 = st.columns(3)
            
            with col_f1:
                busca_nome = st.text_input("🔎 Buscar por nome:", "")
            
            with col_f2:
                if 'Dias desde a compra' in df_clientes.columns:
                    max_dias = int(df_clientes['Dias desde a compra'].max()) if df_clientes['Dias desde a compra'].max() > 0 else 365
                    filtro_dias = st.slider("Dias desde última compra:", 0, max_dias, (0, max_dias))
            
            with col_f3:
                if 'Valor' in df_clientes.columns:
                    ordenar = st.selectbox("Ordenar por:", ["Nome", "Valor (maior)", "Dias (maior)"])
            
            # Aplicar filtros
            df_filtrado = df_clientes.copy()
            
            if busca_nome:
                if 'Nome' in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado['Nome'].str.contains(busca_nome, case=False, na=False)]
            
            if 'Dias desde a compra' in df_filtrado.columns:
                df_filtrado = df_filtrado[
                    (df_filtrado['Dias desde a compra'] >= filtro_dias[0]) &
                    (df_filtrado['Dias desde a compra'] <= filtro_dias[1])
                ]
            
            # Ordenação
            if ordenar == "Valor (maior)" and 'Valor' in df_filtrado.columns:
                df_filtrado = df_filtrado.sort_values('Valor', ascending=False)
            elif ordenar == "Dias (maior)" and 'Dias desde a compra' in df_filtrado.columns:
                df_filtrado = df_filtrado.sort_values('Dias desde a compra', ascending=False)
            
            st.markdown(f"### 📋 Clientes Disponíveis ({len(df_filtrado)})")
            
            # Exibir cards de clientes
            for idx, cliente in df_filtrado.iterrows():
                with st.container():
                    col_info, col_metrics, col_action = st.columns([2, 3, 1])
                    
                    with col_info:
                        st.markdown(f"**👤 {cliente.get('Nome', 'N/A')}**")
                        st.caption(f"📧 {cliente.get('Email', 'N/A')}")
                        st.caption(f"📱 {cliente.get('Telefone', 'N/A')}")
                    
                    with col_metrics:
                        met1, met2, met3 = st.columns(3)
                        with met1:
                            valor = cliente.get('Valor', 0)
                            st.metric("💰 Gasto Total", f"R$ {valor:,.2f}" if pd.notna(valor) else "R$ 0,00")
                        with met2:
                            compras = cliente.get('Compras', 0)
                            st.metric("🛒 Compras", int(compras) if pd.notna(compras) else 0)
                        with met3:
                            dias = cliente.get('Dias desde a compra', 0)
                            st.metric("📅 Dias", int(dias) if pd.notna(dias) else 0)
                    
                    with col_action:
                        if st.button(f"✅ Check-in", key=f"checkin_{idx}", type="primary"):
                            # Preparar dados para agendamento
                            data_agendamento = {
                                'Data de contato': datetime.now().strftime('%d/%m/%Y'),
                                'Nome': cliente.get('Nome', ''),
                                'Classificação': cliente.get('Classificação ', classificacao_selecionada),
                                'Valor': cliente.get('Valor', 0),
                                'Telefone': cliente.get('Telefone', ''),
                                'Relato da conversa': '',
                                'Follow up': 'Pendente',
                                'Data de chamada': '',
                                'Observação': 'Check-in realizado'
                            }
                            
                            try:
                                add_to_worksheet('AGENDAMENTOS_ATIVOS', data_agendamento)
                                st.success(f"✅ Check-in realizado para {cliente.get('Nome', 'cliente')}!")
                                st.balloons()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao realizar check-in: {e}")
                    
                    st.markdown("---")
            
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")

# ===== EM ATENDIMENTO =====
elif page == "📞 Em Atendimento":
    st.title("📞 Em Atendimento - Agendamentos Ativos")
    st.info("Aqui ficam os clientes que já fizeram check-in e aguardam contato")
    
    df_agendamentos = load_data("AGENDAMENTOS_ATIVOS")
    
    if not df_agendamentos.empty:
        st.dataframe(df_agendamentos, use_container_width=True)
        st.metric("Total de Agendamentos", len(df_agendamentos))
    else:
        st.info("✅ Nenhum agendamento ativo no momento")
