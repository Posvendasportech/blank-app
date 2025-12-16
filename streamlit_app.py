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


def adicionar_agendamento(dados_cliente, classificacao_origem):
    """
    Adiciona um cliente na aba AGENDAMENTOS_ATIVOS
    
    Args:
        dados_cliente: Series do pandas com dados do cliente
        classificacao_origem: Classificação de onde veio o cliente
    
    Returns:
        bool: True se sucesso, False se erro
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Carregar dados atuais de AGENDAMENTOS_ATIVOS
        df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
        
        # Preparar nova linha com os dados do cliente
        nova_linha = {
            'Data de contato': datetime.now().strftime('%d/%m/%Y'),
            'Nome': dados_cliente.get('Nome', ''),
            'Classificação': dados_cliente.get('Classificação ', classificacao_origem),
            'Valor': dados_cliente.get('Valor', ''),
            'Telefone': dados_cliente.get('Telefone', ''),
            'Relato da conversa': '',
            'Follow up': 'Pendente',
            'Data de chamada': '',
            'Observação': 'Check-in realizado via CRM'
        }
        
        # Criar DataFrame com a nova linha
        df_nova_linha = pd.DataFrame([nova_linha])
        
        # Adicionar ao DataFrame existente
        df_atualizado = pd.concat([df_agendamentos, df_nova_linha], ignore_index=True)
        
        # Atualizar a planilha
        conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_atualizado)
        
        return True
        
    except Exception as e:
        st.error(f"Erro ao adicionar agendamento: {e}")
        return False


def atualizar_agendamento(index, dados_atualizados):
    """
    Atualiza um registro específico na aba AGENDAMENTOS_ATIVOS
    
    Args:
        index: Índice da linha a ser atualizada
        dados_atualizados: Dicionário com os novos dados
    
    Returns:
        bool: True se sucesso, False se erro
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Carregar dados atuais
        df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
        
        # Atualizar campos específicos
        for campo, valor in dados_atualizados.items():
            if campo in df_agendamentos.columns:
                df_agendamentos.at[index, campo] = valor
        
        # Salvar de volta na planilha
        conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_agendamentos)
        
        return True
        
    except Exception as e:
        st.error(f"Erro ao atualizar agendamento: {e}")
        return False


def finalizar_atendimento(index, dados_completos):
    """
    Move um atendimento de AGENDAMENTOS_ATIVOS para HISTORICO e remove do ativo
    
    Args:
        index: Índice da linha em AGENDAMENTOS_ATIVOS
        dados_completos: Series com todos os dados do atendimento
    
    Returns:
        bool: True se sucesso, False se erro
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # 1. Carregar HISTORICO
        df_historico = conn.read(worksheet="HISTORICO", ttl=0)
        
        # 2. Preparar linha para o histórico (adicionar data de finalização)
        nova_linha_historico = dados_completos.to_dict()
        nova_linha_historico['Data de finalização'] = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        # 3. Adicionar ao histórico
        df_historico_atualizado = pd.concat([df_historico, pd.DataFrame([nova_linha_historico])], ignore_index=True)
        conn.update(worksheet="HISTORICO", data=df_historico_atualizado)
        
        # 4. Remover de AGENDAMENTOS_ATIVOS
        df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
        df_agendamentos_atualizado = df_agendamentos.drop(index).reset_index(drop=True)
        conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_agendamentos_atualizado)
        
        return True
        
    except Exception as e:
        st.error(f"Erro ao finalizar atendimento: {e}")
        return False

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
            dias_min = 0
            dias_max = int(df_clientes['Dias desde a compra'].max()) if df_clientes['Dias desde a compra'].max() > 0 else 365
            
            filtro_dias = st.slider(
                "Dias desde última compra:",
                min_value=dias_min,
                max_value=dias_max,
                value=(dias_min, dias_max)
            )
        else:
            st.info("⏭️ Filtro de dias não disponível para esta classificação")
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
                        # Verificar se a coluna Compras existe
                        if 'Compras' in df_filtrado.columns:
                            compras = cliente.get('Compras', 0)
                            if pd.notna(compras) and compras != '':
                                try:
                                    st.metric("🛒 Compras", int(float(compras)))
                                except:
                                    st.metric("🛒 Compras", "0")
                            else:
                                st.metric("🛒 Compras", "0")
                        else:
                            st.metric("🛒 Compras", "N/D")
                    
                    with met3:
                        # Verificar se a coluna existe
                        if 'Dias desde a compra' in df_filtrado.columns:
                            dias = cliente.get('Dias desde a compra', 0)
                            if pd.notna(dias) and dias != '':
                                try:
                                    st.metric("📅 Dias", int(round(float(dias))))
                                except:
                                    st.metric("📅 Dias", "0")
                            else:
                                st.metric("📅 Dias", "0")
                        else:
                            st.metric("📅 Dias", "N/D")
                
                # --- COLUNA 3: BOTÃO DE AÇÃO ---
                with col_acao:
                    st.write("")  # Espaçamento
                    st.write("")  # Espaçamento
                    
                    # Botão de check-in
                    if st.button(
                        "✅ Check-in",
                        key=f"btn_checkin_{index}",
                        type="primary",
                        use_container_width=True
                    ):
                        # Mostrar loading
                        with st.spinner('Processando check-in...'):
                            
                            # Adicionar cliente aos agendamentos
                            sucesso = adicionar_agendamento(cliente, classificacao_selecionada)
                            
                            if sucesso:
                                # Limpar cache para atualizar dados
                                st.cache_data.clear()
                                
                                # Mensagem de sucesso
                                st.success(f"✅ Check-in realizado para **{cliente.get('Nome', 'cliente')}**!")
                                st.balloons()
                                
                                # Aguardar 2 segundos e recarregar
                                import time
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Erro ao realizar check-in. Tente novamente.")
                
                # Linha separadora entre cards
                st.markdown("---")

# ============================================================================
# PÁGINA: EM ATENDIMENTO
# ============================================================================

elif pagina == "📞 Em Atendimento":
    st.title("📞 Em Atendimento - Agendamentos Ativos")
    st.markdown("Registre suas conversas e agende próximos contatos")
    st.markdown("---")
    
    # Carregar agendamentos
    with st.spinner("Carregando agendamentos..."):
        df_agendamentos = carregar_dados("AGENDAMENTOS_ATIVOS")
    
    if df_agendamentos.empty:
        st.info("✅ Nenhum agendamento ativo no momento")
        st.write("👉 Faça check-in de clientes na página **Check-in** para começar!")
    else:
        # --- MÉTRICAS GERAIS ---
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 Total", len(df_agendamentos))
        
        with col2:
            if 'Follow up' in df_agendamentos.columns:
                pendentes = len(df_agendamentos[df_agendamentos['Follow up'] == 'Pendente'])
                st.metric("⏳ Pendentes", pendentes)
            else:
                st.metric("⏳ Pendentes", "N/D")
        
        with col3:
            hoje = datetime.now().strftime('%d/%m/%Y')
            if 'Data de contato' in df_agendamentos.columns:
                hoje_count = len(df_agendamentos[df_agendamentos['Data de contato'] == hoje])
                st.metric("📅 Hoje", hoje_count)
            else:
                st.metric("📅 Hoje", "N/D")
        
        with col4:
            if 'Relato da conversa' in df_agendamentos.columns:
                com_relato = len(df_agendamentos[df_agendamentos['Relato da conversa'].notna() & (df_agendamentos['Relato da conversa'] != '')])
                st.metric("✅ Com Relato", com_relato)
            else:
                st.metric("✅ Com Relato", "N/D")
        
        st.markdown("---")
        
        # --- FILTROS ---
        st.subheader("🔍 Filtros")
        
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            busca_agendamento = st.text_input("Buscar por nome:", "", key="busca_em_atendimento")
        
        with col_f2:
            if 'Follow up' in df_agendamentos.columns:
                status_options = ['Todos'] + list(df_agendamentos['Follow up'].unique())
                filtro_status = st.selectbox("Status:", status_options)
            else:
                filtro_status = 'Todos'
        
        with col_f3:
            if 'Classificação' in df_agendamentos.columns:
                class_options = ['Todos'] + list(df_agendamentos['Classificação'].unique())
                filtro_class_atend = st.selectbox("Classificação:", class_options)
            else:
                filtro_class_atend = 'Todos'
        
        # Aplicar filtros
        df_agend_filtrado = df_agendamentos.copy()
        
        if busca_agendamento and 'Nome' in df_agend_filtrado.columns:
            df_agend_filtrado = df_agend_filtrado[
                df_agend_filtrado['Nome'].str.contains(busca_agendamento, case=False, na=False)
            ]
        
        if filtro_status != 'Todos' and 'Follow up' in df_agend_filtrado.columns:
            df_agend_filtrado = df_agend_filtrado[df_agend_filtrado['Follow up'] == filtro_status]
        
        if filtro_class_atend != 'Todos' and 'Classificação' in df_agend_filtrado.columns:
            df_agend_filtrado = df_agend_filtrado[df_agend_filtrado['Classificação'] == filtro_class_atend]
        
        st.markdown("---")
        
        # --- CARDS DE AGENDAMENTOS ---
        st.subheader(f"📋 Agendamentos ({len(df_agend_filtrado)})")
        
        if df_agend_filtrado.empty:
            st.info("Nenhum agendamento encontrado com os filtros aplicados")
        else:
            # Loop para cada agendamento
            for index, agendamento in df_agend_filtrado.iterrows():
                
                # Card expansível para cada cliente
                with st.expander(
                    f"👤 {agendamento.get('Nome', 'Nome não disponível')} - {agendamento.get('Classificação', 'N/D')}",
                    expanded=False
                ):
                    # Dividir em 2 colunas principais
                    col_esq, col_dir = st.columns([1, 1])
                    
                    # --- COLUNA ESQUERDA: INFORMAÇÕES DO CLIENTE ---
                    with col_esq:
                        st.markdown("### 📊 Informações do Cliente")
                        
                        st.write(f"**👤 Nome:** {agendamento.get('Nome', 'N/D')}")
                        st.write(f"**📱 Telefone:** {agendamento.get('Telefone', 'N/D')}")
                        st.write(f"**🏷️ Classificação:** {agendamento.get('Classificação', 'N/D')}")
                        
                        valor = agendamento.get('Valor', 0)
                        if pd.notna(valor) and valor != '':
                            try:
                                st.write(f"**💰 Valor Total:** R$ {float(valor):,.2f}")
                            except:
                                st.write(f"**💰 Valor Total:** {valor}")
                        else:
                            st.write(f"**💰 Valor Total:** R$ 0,00")
                        
                        st.write(f"**📅 Data Check-in:** {agendamento.get('Data de contato', 'N/D')}")
                        
                        st.markdown("---")
                        
                        # Exibir dados já salvos (somente leitura)
                        st.markdown("### 📝 Histórico Atual")
                        
                        relato_atual = agendamento.get('Relato da conversa', '')
                        if relato_atual and relato_atual != '':
                            st.info(f"**Relato:** {relato_atual}")
                        else:
                            st.caption("_Sem relato registrado_")
                        
                        follow_atual = agendamento.get('Follow up', '')
                        if follow_atual and follow_atual != '':
                            st.info(f"**Follow-up:** {follow_atual}")
                        else:
                            st.caption("_Sem follow-up registrado_")
                        
                        data_chamada_atual = agendamento.get('Data de chamada', '')
                        if data_chamada_atual and data_chamada_atual != '':
                            st.info(f"**Data Agendada:** {data_chamada_atual}")
                        else:
                            st.caption("_Sem data agendada_")
                        
                        obs_atual = agendamento.get('Observação', '')
                        if obs_atual and obs_atual != '':
                            st.info(f"**Observação:** {obs_atual}")
                    
                    # --- COLUNA DIREITA: FORMULÁRIO DE ATENDIMENTO ---
                    with col_dir:
                        st.markdown("### ✏️ Atualizar Atendimento")
                        
                        # Formulário com key única para cada cliente
                        with st.form(key=f"form_atendimento_{index}"):
                            
                            # Campo: Relato da conversa
                            novo_relato = st.text_area(
                                "📝 Relato da Conversa:",
                                value=relato_atual if relato_atual else "",
                                height=100,
                                help="Descreva como foi a conversa com o cliente",
                                placeholder="Ex: Cliente satisfeito, pediu informações sobre novos produtos..."
                            )
                            
                            # Campo: Follow up
                            novo_followup = st.text_input(
                                "🎯 Motivo do Próximo Contato (Follow-up):",
                                value=follow_atual if follow_atual else "",
                                help="Qual o motivo do próximo contato?",
                                placeholder="Ex: Enviar catálogo, Confirmar entrega..."
                            )
                            
                            # Campo: Data de chamada
                            nova_data_chamada = st.date_input(
                                "📅 Data do Próximo Contato:",
                                value=None,
                                help="Quando será o próximo contato?"
                            )
                            
                            # Campo: Observação
                            nova_observacao = st.text_area(
                                "💬 Observações Adicionais:",
                                value=obs_atual if obs_atual else "",
                                height=80,
                                placeholder="Informações extras relevantes..."
                            )
                            
                            st.markdown("---")
                            
                            # Botões de ação
                            col_btn1, col_btn2 = st.columns(2)
                            
                            with col_btn1:
                                btn_salvar = st.form_submit_button(
                                    "💾 Salvar Alterações",
                                    type="primary",
                                    use_container_width=True
                                )
                            
                            with col_btn2:
                                btn_finalizar = st.form_submit_button(
                                    "✅ Finalizar Atendimento",
                                    use_container_width=True
                                )
                            
                            # ========================================
                            # AÇÕES DOS BOTÕES
                            # ========================================
                            
                            if btn_salvar:
                                # Validar se há alterações
                                if not novo_relato and not novo_followup:
                                    st.warning("⚠️ Preencha ao menos o Relato ou Follow-up antes de salvar")
                                else:
                                    with st.spinner("Salvando alterações..."):
                                        # Preparar dados para atualização
                                        dados_atualizacao = {
                                            'Relato da conversa': novo_relato,
                                            'Follow up': novo_followup,
                                            'Data de chamada': nova_data_chamada.strftime('%d/%m/%Y') if nova_data_chamada else '',
                                            'Observação': nova_observacao
                                        }
                                        
                                        # Atualizar na planilha
                                        sucesso = atualizar_agendamento(index, dados_atualizacao)
                                        
                                        if sucesso:
                                            st.cache_data.clear()
                                            st.success("✅ Alterações salvas com sucesso!")
                                            st.balloons()
                                            
                                            import time
                                            time.sleep(1.5)
                                            st.rerun()
                                        else:
                                            st.error("❌ Erro ao salvar. Tente novamente.")
                            
                            if btn_finalizar:
                                # Validar se o atendimento está completo
                                if not novo_relato:
                                    st.error("❌ Preencha o Relato da Conversa antes de finalizar!")
                                else:
                                    with st.spinner("Finalizando atendimento..."):
                                        # Preparar dados completos
                                        dados_finalizacao = agendamento.copy()
                                        dados_finalizacao['Relato da conversa'] = novo_relato
                                        dados_finalizacao['Follow up'] = novo_followup
                                        dados_finalizacao['Data de chamada'] = nova_data_chamada.strftime('%d/%m/%Y') if nova_data_chamada else ''
                                        dados_finalizacao['Observação'] = nova_observacao
                                        
                                        # Finalizar (mover para histórico)
                                        sucesso = finalizar_atendimento(index, dados_finalizacao)
                                        
                                        if sucesso:
                                            st.cache_data.clear()
                                            st.success("✅ Atendimento finalizado e movido para o histórico!")
                                            st.balloons()
                                            
                                            import time
                                            time.sleep(2)
                                            st.rerun()
                                        else:
                                            st.error("❌ Erro ao finalizar. Tente novamente.")
                
                # Separador entre cards
                st.markdown("---")

# ============================================================================
# PÁGINA: SUPORTE
# ============================================================================

elif pagina == "🆘 Suporte":
    st.title("🆘 Suporte")
    st.info("Esta página será implementada em breve")

# ============================================================================
# PÁGINA: HISTÓRICO
# ============================================================================

elif pagina == "📜 Histórico":
    st.title("📜 Histórico")
    st.info("Esta página será implementada em breve")
