
# ============================================================================
# CRM PÓS-VENDAS - STREAMLIT APP
# Versão: 1.0 - Arquitetura Modular
# Descrição: Sistema de gestão de relacionamento com clientes
# ============================================================================

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

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
# CONEXÃO CENTRALIZADA
# ============================================================================

@st.cache_resource
def get_gsheets_connection():
    """Retorna conexão única reutilizável com Google Sheets"""
    return st.connection("gsheets", type=GSheetsConnection)

# ============================================================================
# FUNÇÕES AUXILIARES - UTILITÁRIOS
# ============================================================================

def limpar_telefone(telefone):
    """Remove caracteres especiais do telefone para comparação"""
    if not telefone or pd.isna(telefone):
        return ''
    return re.sub(r'[^\d]', '', str(telefone))

@st.cache_data(ttl=60)
def carregar_dados(nome_aba, _force_refresh=False):
    """Carrega dados de uma aba específica do Google Sheets"""
    try:
        conn = get_gsheets_connection()
        df = conn.read(worksheet=nome_aba, ttl=60)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar aba '{nome_aba}': {e}")
        return pd.DataFrame()


def adicionar_agendamento(dados_cliente, classificacao_origem):
    """Adiciona um cliente na aba AGENDAMENTOS_ATIVOS"""
    try:
        conn = get_gsheets_connection()
        df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
        
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
        
        df_nova_linha = pd.DataFrame([nova_linha])
        df_atualizado = pd.concat([df_agendamentos, df_nova_linha], ignore_index=True)
        conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_atualizado)
        
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar agendamento: {e}")
        return False


def atualizar_agendamento(index, dados_atualizados):
    """Atualiza um registro na aba AGENDAMENTOS_ATIVOS"""
    try:
        conn = get_gsheets_connection()
        df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
        
        for campo, valor in dados_atualizados.items():
            if campo in df_agendamentos.columns:
                df_agendamentos.at[index, campo] = valor
        
        conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_agendamentos)
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")
        return False


def finalizar_atendimento(index, dados_completos):
    """Move atendimento para HISTORICO e remove de AGENDAMENTOS_ATIVOS"""
    try:
        conn = get_gsheets_connection()
        
        # Carregar histórico
        df_historico = conn.read(worksheet="HISTORICO", ttl=0)
        
        # Preparar linha para histórico
        nova_linha_historico = dados_completos.to_dict()
        nova_linha_historico['Data de finalização'] = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        # Adicionar ao histórico
        df_historico_novo = pd.concat([df_historico, pd.DataFrame([nova_linha_historico])], ignore_index=True)
        conn.update(worksheet="HISTORICO", data=df_historico_novo)
        
        # Remover de agendamentos ativos
        df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
        df_agendamentos_novo = df_agendamentos.drop(index).reset_index(drop=True)
        conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_agendamentos_novo)
        
        return True
    except Exception as e:
        st.error(f"Erro ao finalizar: {e}")
        return False
        
def gerar_id_ticket():
    """Gera um ID único para o ticket no formato TKT-YYYY-NNNNN"""
    try:
        conn = st.connection("gsheets", type="GSheetsConnection")
        df_suporte = conn.read(worksheet="SUPORTE", ttl=0)
        
        ano_atual = datetime.now().year
        
        # Contar tickets do ano atual
        if not df_suporte.empty and 'ID_Ticket' in df_suporte.columns:
            tickets_ano = df_suporte[df_suporte['ID_Ticket'].str.contains(f'TKT-{ano_atual}', na=False)]
            numero = len(tickets_ano) + 1
        else:
            numero = 1
        
        return f"TKT-{ano_atual}-{numero:05d}"
    
    except:
        # Fallback caso haja erro
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"TKT-{datetime.now().year}-{timestamp[-5:]}"


def registrar_ticket_log_aberto(id_ticket, dados_ticket, aberto_por):
    """Registra a abertura do ticket em LOG_TICKETS_ABERTOS"""
    try:
        conn = st.connection("gsheets", type="GSheetsConnection")
        df_log = conn.read(worksheet="LOG_TICKETS_ABERTOS", ttl=0)
        
        novo_log = {
            'Data_Registro': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'ID_Ticket': id_ticket,
            'Nome_Cliente': dados_ticket.get('Nome', ''),
            'Telefone': dados_ticket.get('Telefone', ''),
            'Classificacao': dados_ticket.get('Classificacao', ''),
            'Tipo_Problema': dados_ticket.get('TipoProblema', ''),
            'Prioridade': dados_ticket.get('Prioridade', ''),
            'Descricao': dados_ticket.get('Descricao', ''),
            'Aberto_Por': aberto_por
        }
        
        df_log_novo = pd.concat([df_log, pd.DataFrame([novo_log])], ignore_index=True)
        conn.update(worksheet="LOG_TICKETS_ABERTOS", data=df_log_novo)
        
    except Exception as e:
        st.warning(f"⚠️ Log não registrado: {e}")


def registrar_ticket_log_resolvido(id_ticket, dados_resolucao, resolvido_por):
    """Registra a resolução do ticket em LOG_TICKETS_RESOLVIDOS"""
    try:
        conn = st.connection("gsheets", type="GSheetsConnection")
        df_log = conn.read(worksheet="LOG_TICKETS_RESOLVIDOS", ttl=0)
        
        novo_log = {
            'Data_Resolucao': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'ID_Ticket': id_ticket,
            'Solucao_Aplicada': dados_resolucao.get('Solucao', ''),
            'Resultado_Final': dados_resolucao.get('Resultado', ''),
            'Gerou_Conversao': dados_resolucao.get('Conversao', 'Não'),
            'Resolvido_Por': resolvido_por
        }
        
        df_log_novo = pd.concat([df_log, pd.DataFrame([novo_log])], ignore_index=True)
        conn.update(worksheet="LOG_TICKETS_RESOLVIDOS", data=df_log_novo)
        
    except Exception as e:
        st.warning(f"⚠️ Log de resolução não registrado: {e}")

@st.cache_data(ttl=60)
def carregar_dados_suporte():
    """Carrega dados da planilha SUPORTE com cache"""
    try:
        conn = st.connection("gsheets", type="GSheetsConnection")
        return conn.read(worksheet="SUPORTE", ttl=0)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()



# ============================================================================
# RENDER - PÁGINA CHECK-IN (VERSÃO OTIMIZADA)
# ============================================================================

def render_checkin():
    """Renderiza a página de Check-in de clientes - Versão otimizada"""
# Primeira vez que a página carrega? Criar valores padrão
    if 'metas_checkin' not in st.session_state:
        st.session_state.metas_checkin = {
            'novo': 5,
            'promissor': 5,
            'leal': 5,
            'campeao': 3,
            'risco': 5,
            'dormente': 5
        }

    # Variável para rastrear se metas foram alteradas nesta sessão
    if 'metas_alteradas' not in st.session_state:
        st.session_state.metas_alteradas = False

    
    st.title("✅ Check-in de Clientes")
    st.markdown("Selecione clientes para iniciar o fluxo de atendimento")
    st.markdown("---")
    
    # ========== PAINEL DE PLANEJAMENTO DIÁRIO ==========
    st.subheader("📊 Planejamento de Check-ins do Dia")
    
    # Carregar agendamentos para contar check-ins de hoje
    df_agendamentos_hoje = carregar_dados("AGENDAMENTOS_ATIVOS")
    hoje = datetime.now().strftime('%d/%m/%Y')
    
    # Contar check-ins de hoje
    if not df_agendamentos_hoje.empty and 'Data de contato' in df_agendamentos_hoje.columns:
        checkins_hoje = len(df_agendamentos_hoje[df_agendamentos_hoje['Data de contato'] == hoje])
    else:
        checkins_hoje = 0
    
    # Painel de metas diárias
    with st.expander("🎯 Definir Metas de Check-in por Classificação", expanded=True):
        st.write("**Defina quantos clientes de cada grupo você quer contatar hoje:**")
        
        col_meta1, col_meta2, col_meta3 = st.columns(3)
        
        with col_meta1:
            meta_novo = st.number_input(
                "🆕 Novo", 
                min_value=0, 
                max_value=50, 
                value=st.session_state.metas_checkin['novo'],
                step=1,
                key='input_meta_novo',
                help="Meta de clientes novos para contatar hoje"
            )
            if meta_novo != st.session_state.metas_checkin['novo']:
                st.session_state.metas_checkin['novo'] = meta_novo
                st.session_state.metas_alteradas = True
            
            meta_promissor = st.number_input(
                "⭐ Promissor", 
                min_value=0, 
                max_value=50, 
                value=st.session_state.metas_checkin['promissor'],
                step=1,
                key='input_meta_promissor',
                help="Meta de clientes promissores para contatar hoje"
            )
            if meta_promissor != st.session_state.metas_checkin['promissor']:
                st.session_state.metas_checkin['promissor'] = meta_promissor
                st.session_state.metas_alteradas = True
        
        with col_meta2:
            meta_leal = st.number_input(
                "💙 Leal", 
                min_value=0, 
                max_value=50, 
                value=st.session_state.metas_checkin['leal'],
                step=1,
                key='input_meta_leal',
                help="Meta de clientes leais para contatar hoje"
            )
            if meta_leal != st.session_state.metas_checkin['leal']:
                st.session_state.metas_checkin['leal'] = meta_leal
                st.session_state.metas_alteradas = True
            
            meta_campeao = st.number_input(
                "🏆 Campeão", 
                min_value=0, 
                max_value=50, 
                value=st.session_state.metas_checkin['campeao'],
                step=1,
                key='input_meta_campeao',
                help="Meta de clientes campeões para contatar hoje"
            )
            if meta_campeao != st.session_state.metas_checkin['campeao']:
                st.session_state.metas_checkin['campeao'] = meta_campeao
                st.session_state.metas_alteradas = True
        
        with col_meta3:
            meta_risco = st.number_input(
                "⚠️ Em risco", 
                min_value=0, 
                max_value=50, 
                value=st.session_state.metas_checkin['risco'],
                step=1,
                key='input_meta_risco',
                help="Meta de clientes em risco para contatar hoje"
            )
            if meta_risco != st.session_state.metas_checkin['risco']:
                st.session_state.metas_checkin['risco'] = meta_risco
                st.session_state.metas_alteradas = True
            
            meta_dormente = st.number_input(
                "😴 Dormente", 
                min_value=0, 
                max_value=50, 
                value=st.session_state.metas_checkin['dormente'],
                step=1,
                key='input_meta_dormente',
                help="Meta de clientes dormentes para contatar hoje"
            )
            if meta_dormente != st.session_state.metas_checkin['dormente']:
                st.session_state.metas_checkin['dormente'] = meta_dormente
                st.session_state.metas_alteradas = True
        
        # Calcular meta total
        meta_total = meta_novo + meta_promissor + meta_leal + meta_campeao + meta_risco + meta_dormente

        st.markdown("---")

        col_info1, col_info2 = st.columns([2, 1])

        with col_info1:
            st.info(f"🎯 **Meta Total do Dia:** {meta_total} check-ins")

        with col_info2:
            if st.session_state.metas_alteradas:
                st.success("✅ Metas salvas!")
            else:
                st.caption("💾 Metas carregadas")
    
    st.markdown("---")

    
    # ========== BARRA DE PROGRESSO E MOTIVAÇÃO ==========
    st.subheader("📈 Progresso do Dia")
    
    # Calcular progresso
    if meta_total > 0:
        progresso = min(checkins_hoje / meta_total, 1.0)
        percentual = int(progresso * 100)
    else:
        progresso = 0
        percentual = 0
    
    # Frases motivacionais baseadas no progresso
    frases_motivacao = {
        0: "🚀 Vamos começar! Todo grande resultado começa com o primeiro passo!",
        25: "💪 Ótimo começo! Continue assim e você vai longe!",
        50: "🔥 Você está no meio do caminho! Não pare agora!",
        75: "⭐ Incrível! Você está quase lá, finalize com chave de ouro!",
        100: "🎉 PARABÉNS! Meta do dia alcançada! Você é CAMPEÃO! 🏆"
    }
    
    # Selecionar frase baseada no percentual
    if percentual >= 100:
        frase = frases_motivacao[100]
    elif percentual >= 75:
        frase = frases_motivacao[75]
    elif percentual >= 50:
        frase = frases_motivacao[50]
    elif percentual >= 25:
        frase = frases_motivacao[25]
    else:
        frase = frases_motivacao[0]
    
    # Exibir métricas e progresso
    col_prog1, col_prog2, col_prog3 = st.columns([1, 2, 1])
    
    with col_prog1:
        st.metric(
            label="✅ Check-ins Hoje",
            value=checkins_hoje,
            delta=f"{checkins_hoje - meta_total} da meta" if meta_total > 0 else None
        )
    
    with col_prog2:
        st.progress(progresso)
        st.markdown(f"**{percentual}% da meta alcançada**")
        
        # Frase motivacional
        if percentual >= 100:
            st.success(frase)
        elif percentual >= 50:
            st.info(frase)
        else:
            st.warning(frase)
    
    with col_prog3:
        st.metric(
            label="🎯 Meta do Dia",
            value=meta_total,
            delta=f"Faltam {max(0, meta_total - checkins_hoje)}"
        )
    
    st.markdown("---")
    
    # Configurações de filtros
    col_config1, col_config2 = st.columns([2, 1])
    
    with col_config1:
        # Seletor de classificação (SEM "Total")
        classificacoes = ["Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"]
        classificacao_selecionada = st.selectbox(
            "📂 Escolha a classificação:",
            classificacoes,
            index=0,
            help="Selecione o grupo de clientes que deseja visualizar"
        )
    
    with col_config2:
        # Vincular com o planejamento de metas
        metas_por_classificacao = {
    "Novo": st.session_state.metas_checkin['novo'],
    "Promissor": st.session_state.metas_checkin['promissor'],
    "Leal": st.session_state.metas_checkin['leal'],
    "Campeão": st.session_state.metas_checkin['campeao'],
    "Em risco": st.session_state.metas_checkin['risco'],
    "Dormente": st.session_state.metas_checkin['dormente']
}
        
        # Pegar limite baseado na meta definida
        limite_clientes = metas_por_classificacao.get(classificacao_selecionada, 10)
        
        # Mostrar info de quantos serão carregados
        st.info(f"📊 **{limite_clientes}** clientes da meta do dia")
    
    st.markdown("---")
    
    # Carregar dados
    with st.spinner(f"Carregando clientes de '{classificacao_selecionada}'..."):
        df_clientes = carregar_dados(classificacao_selecionada)
        df_agendamentos_ativos = carregar_dados("AGENDAMENTOS_ATIVOS")
    
    if df_clientes.empty:
        st.warning(f"⚠️ Nenhum cliente encontrado na classificação '{classificacao_selecionada}'")
        return
    
    # Remover clientes que já estão em agendamentos ativos
    if not df_agendamentos_ativos.empty and 'Nome' in df_agendamentos_ativos.columns:
        clientes_em_atendimento = df_agendamentos_ativos['Nome'].tolist()
        df_clientes_original = df_clientes.copy()
        df_clientes = df_clientes[~df_clientes['Nome'].isin(clientes_em_atendimento)]
        
        clientes_removidos = len(df_clientes_original) - len(df_clientes)
        if clientes_removidos > 0:
            st.warning(f"⚠️ {clientes_removidos} cliente(s) já estão em atendimento ativo e foram removidos da lista")
    
    if df_clientes.empty:
        st.info("✅ Todos os clientes desta classificação já estão em atendimento!")
        return
    
    # Aplicar limite baseado na meta definida
    df_clientes = df_clientes.head(limite_clientes)
    
    # Informações compactas + Filtros em uma linha
    col_info, col_busca, col_dias = st.columns([1, 2, 2])
    
    with col_info:
        st.metric("✅ Disponíveis", len(df_clientes), help="Clientes disponíveis para check-in")
    
    with col_busca:
        busca_nome = st.text_input(
            "🔍 Buscar cliente:",
            "",
            placeholder="Digite o nome...",
            label_visibility="collapsed"
        )
    
    with col_dias:
        if 'Dias desde a compra' in df_clientes.columns:
            dias_min = 0
            dias_max = int(df_clientes['Dias desde a compra'].max()) if df_clientes['Dias desde a compra'].max() > 0 else 365
            filtro_dias = st.slider(
                "📅 Dias desde última compra:",
                dias_min,
                dias_max,
                (dias_min, dias_max),
                label_visibility="collapsed"
            )
        else:
            filtro_dias = None
    
    # Aplicar filtros
    df_filtrado = df_clientes.copy()
    if busca_nome and 'Nome' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['Nome'].str.contains(busca_nome, case=False, na=False)]
    if filtro_dias and 'Dias desde a compra' in df_filtrado.columns:
        df_filtrado = df_filtrado[(df_filtrado['Dias desde a compra'] >= filtro_dias[0]) & (df_filtrado['Dias desde a compra'] <= filtro_dias[1])]
    
    st.markdown("---")
    st.subheader(f"📋 Clientes para Check-in ({len(df_filtrado)})")
    
    if df_filtrado.empty:
        st.info("Nenhum cliente encontrado com os filtros aplicados")
        return
    
    # Cards de clientes - Estilo otimizado com expander
    for index, cliente in df_filtrado.iterrows():
        
        # Título do card com informações principais
        nome_cliente = cliente.get('Nome', 'Nome não disponível')
        valor_cliente = cliente.get('Valor', 0)
        
        # Formatação do valor
        if pd.notna(valor_cliente) and valor_cliente != '':
            try:
                valor_formatado = f"R$ {float(valor_cliente):,.2f}"
            except:
                valor_formatado = "R$ 0,00"
        else:
            valor_formatado = "R$ 0,00"
        
        # Card expansível com tema azul
        with st.expander(
            f"👤 {nome_cliente} | 💰 {valor_formatado} | 🏷️ {classificacao_selecionada}",
            expanded=False
        ):
            # Dividir em 2 colunas
            col_info_card, col_form = st.columns([1, 1])
            
            # ========== COLUNA ESQUERDA: INFORMAÇÕES DO CLIENTE ==========
            with col_info_card:
                st.markdown("### 📊 Informações do Cliente")
                
                # Dados principais
                st.write(f"**👤 Nome Completo:** {nome_cliente}")
                st.write(f"**📧 E-mail:** {cliente.get('Email', 'N/D')}")
                st.write(f"**📱 Telefone:** {cliente.get('Telefone', 'N/D')}")
                st.write(f"**🏷️ Classificação:** {classificacao_selecionada}")
                
                st.markdown("---")
                
                # Métricas em mini cards
                st.markdown("### 📈 Histórico de Compras")
                
                met1, met2, met3 = st.columns(3)
                
                with met1:
                    st.metric(
                        label="💰 Gasto Total",
                        value=valor_formatado,
                        help="Valor total gasto pelo cliente"
                    )
                
                with met2:
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
                    if 'Dias desde a compra' in df_filtrado.columns:
                        dias = cliente.get('Dias desde a compra', 0)
                        if pd.notna(dias) and dias != '':
                            try:
                                dias_int = int(round(float(dias)))
                                st.metric("📅 Dias", dias_int, help="Dias desde a última compra")
                            except:
                                st.metric("📅 Dias", "0")
                        else:
                            st.metric("📅 Dias", "0")
                    else:
                        st.metric("📅 Dias", "N/D")
            
            # ========== COLUNA DIREITA: FORMULÁRIO DE CHECK-IN ==========
            with col_form:
                st.markdown("### ✏️ Registrar Check-in")
                
                # Formulário de check-in
                with st.form(key=f"form_checkin_{index}"):
                    
                    st.info("💡 Preencha as informações do primeiro contato com o cliente")
                    
                    # Campo: Primeira conversa
                    primeira_conversa = st.text_area(
                        "📝 Como foi a primeira conversa?",
                        height=120,
                        help="Registre os principais pontos da conversa inicial",
                        placeholder="Ex: Cliente demonstrou interesse em produtos premium. Mencionou necessidade de entrega rápida..."
                    )
                    
                    # Campo: Motivo do próximo contato
                    proximo_contato = st.text_input(
                        "🎯 Qual o motivo do próximo contato?",
                        help="Defina o objetivo do próximo follow-up",
                        placeholder="Ex: Enviar catálogo de produtos, Confirmar orçamento..."
                    )
                    
                    # Campo: Data do próximo contato
                    data_proximo = st.date_input(
                        "📅 Data do próximo contato:",
                        value=None,
                        help="Quando será o próximo follow-up?"
                    )
                    
                    # Campo: Observações adicionais
                    observacoes = st.text_area(
                        "💬 Observações adicionais:",
                        height=80,
                        placeholder="Informações extras relevantes sobre o cliente..."
                    )
                    
                    st.markdown("---")
                    
                    # Botão de check-in
                    btn_checkin = st.form_submit_button(
                        "✅ Realizar Check-in",
                        type="primary",
                        use_container_width=True
                    )
                    
                    # Ação do botão
                    if btn_checkin:
                        # Validação
                        if not primeira_conversa:
                            st.error("❌ Preencha como foi a primeira conversa antes de continuar!")
                        elif not proximo_contato:
                            st.error("❌ Defina o motivo do próximo contato!")
                        else:
                            with st.spinner('Processando check-in...'):
                                # Preparar dados para agendamento
                                try:
                                    conn = get_gsheets_connection()
                                    df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
                                    
                                    nova_linha = {
                                        'Data de contato': datetime.now().strftime('%d/%m/%Y'),
                                        'Nome': cliente.get('Nome', ''),
                                        'Classificação': classificacao_selecionada,
                                        'Valor': cliente.get('Valor', ''),
                                        'Telefone': cliente.get('Telefone', ''),
                                        'Relato da conversa': primeira_conversa,
                                        'Follow up': proximo_contato,
                                        'Data de chamada': data_proximo.strftime('%d/%m/%Y') if data_proximo else '',
                                        'Observação': observacoes if observacoes else 'Check-in realizado via CRM'
                                    }
                                    
                                    df_nova_linha = pd.DataFrame([nova_linha])
                                    df_atualizado = pd.concat([df_agendamentos, df_nova_linha], ignore_index=True)
                                    conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_atualizado)
                                    
                                    carregar_dados.clear()
                                    st.success(f"✅ Check-in realizado com sucesso para **{nome_cliente}**!")
                                    st.balloons()
                                    time.sleep(2)
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Erro ao realizar check-in: {e}")
        
        # Separador entre cards
        st.markdown("---")



# ============================================================================
# RENDER - PÁGINA EM ATENDIMENTO
# ============================================================================

def render_em_atendimento():
    """Renderiza a página de Em Atendimento - Versão Otimizada"""
    
    st.title("📞 Em Atendimento")
    st.markdown("Gerencie os atendimentos agendados para hoje")
    st.markdown("---")
    
    # Carregar dados
    with st.spinner("Carregando agendamentos..."):
        df_agendamentos = carregar_dados("AGENDAMENTOS_ATIVOS")
    
    if df_agendamentos.empty:
        st.info("✅ Nenhum agendamento ativo no momento")
        st.write("👉 Faça check-in de clientes na página **Check-in** para começar!")
        return
    
    # ========== FILTRAR APENAS ATENDIMENTOS DO DIA ==========
    hoje_dt = datetime.now()
    hoje_str_br = hoje_dt.strftime('%d/%m/%Y')  # Formato brasileiro
    hoje_str_iso = hoje_dt.strftime('%Y/%m/%d')  # Formato ISO
    hoje_str_iso2 = hoje_dt.strftime('%Y-%m-%d')  # Formato ISO com hífen

    # Filtrar apenas agendamentos para hoje (aceita múltiplos formatos)
    df_hoje = pd.DataFrame()
    if 'Data de chamada' in df_agendamentos.columns:
        df_hoje = df_agendamentos[
            (df_agendamentos['Data de chamada'] == hoje_str_br) |
            (df_agendamentos['Data de chamada'] == hoje_str_iso) |
            (df_agendamentos['Data de chamada'] == hoje_str_iso2)
        ].copy()

    # Calcular vencidos (datas anteriores a hoje)
    df_vencidos = pd.DataFrame()
    if 'Data de chamada' in df_agendamentos.columns:
        vencidos_lista = []
        for idx, row in df_agendamentos.iterrows():
            data_chamada_str = row.get('Data de chamada', '')
            if data_chamada_str and data_chamada_str != '':
                try:
                    # Tentar múltiplos formatos
                    data_chamada_dt = None
                    
                    # Tentar formato brasileiro DD/MM/YYYY
                    try:
                        data_chamada_dt = datetime.strptime(data_chamada_str, '%d/%m/%Y')
                    except:
                        pass
                    
                    # Tentar formato ISO YYYY/MM/DD
                    if not data_chamada_dt:
                        try:
                            data_chamada_dt = datetime.strptime(data_chamada_str, '%Y/%m/%d')
                        except:
                            pass
                    
                    # Tentar formato ISO com hífen YYYY-MM-DD
                    if not data_chamada_dt:
                        try:
                            data_chamada_dt = datetime.strptime(data_chamada_str, '%Y-%m-%d')
                        except:
                            pass
                    
                    # Se conseguiu converter e está vencida
                    if data_chamada_dt and data_chamada_dt.date() < hoje_dt.date():
                        vencidos_lista.append(idx)
                except:
                    pass
        
        if vencidos_lista:
            df_vencidos = df_agendamentos.loc[vencidos_lista].copy()
    
    # ========== DASHBOARD DE MÉTRICAS ==========
    st.subheader("📊 Resumo do Dia")
    
    total_hoje = len(df_hoje)
    total_vencidos = len(df_vencidos)
    pendentes_hoje = total_hoje  # Todos os de hoje são pendentes até serem finalizados
    
    # Exibir métricas
    col_m1, col_m2, col_m3 = st.columns(3)
    
    with col_m1:
        st.metric("📊 Total do Dia", total_hoje, help="Total de atendimentos agendados para hoje")
    
    with col_m2:
        st.metric("⏳ Pendentes", pendentes_hoje, help="Atendimentos que faltam finalizar hoje")
    
    with col_m3:
        st.metric("🔥 Vencidos", total_vencidos, 
                  delta=f"-{total_vencidos}" if total_vencidos > 0 else "0",
                  delta_color="inverse", 
                  help="Atendimentos de dias anteriores não concluídos")
    
    # Alerta de vencidos
    if total_vencidos > 0:
        st.error(f"⚠️ **ATENÇÃO:** Você tem {total_vencidos} atendimento(s) vencido(s) de dias anteriores! Priorize-os.")
    
    st.markdown("---")
    
    # ========== FILTROS ==========
    st.subheader("🔍 Filtros")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        # Escolher se quer ver hoje ou vencidos
        visualizar = st.selectbox(
            "Visualizar:",
            ["Hoje", "Vencidos", "Todos"],
            help="Escolha qual grupo de atendimentos deseja ver"
        )
    
    with col_f2:
        busca = st.text_input(
            "Buscar cliente:",
            "",
            placeholder="Digite o nome...",
            key="busca_atend"
        )
    
    with col_f3:
        # Selecionar dataset baseado na visualização
        if visualizar == "Hoje":
            df_trabalho = df_hoje.copy()
        elif visualizar == "Vencidos":
            df_trabalho = df_vencidos.copy()
        else:  # Todos
            df_trabalho = pd.concat([df_hoje, df_vencidos]).drop_duplicates()
        
        if 'Classificação' in df_trabalho.columns and not df_trabalho.empty:
            class_opts = ['Todos'] + sorted(list(df_trabalho['Classificação'].dropna().unique()))
            filtro_class = st.selectbox("Classificação:", class_opts)
        else:
            filtro_class = 'Todos'
    
    # Aplicar filtros
    df_filt = df_trabalho.copy()
    
    if busca and 'Nome' in df_filt.columns:
        df_filt = df_filt[df_filt['Nome'].str.contains(busca, case=False, na=False)]
    
    if filtro_class != 'Todos' and 'Classificação' in df_filt.columns:
        df_filt = df_filt[df_filt['Classificação'] == filtro_class]
    
    st.markdown("---")
    
    # ========== LISTA DE AGENDAMENTOS ==========
    st.subheader(f"📋 Atendamentos ({len(df_filt)})")
    
    if df_filt.empty:
        if visualizar == "Hoje":
            st.info("✅ Nenhum atendimento agendado para hoje!")
        elif visualizar == "Vencidos":
            st.success("✅ Você não tem atendimentos vencidos! Parabéns!")
        else:
            st.info("Nenhum agendamento encontrado")
        return
    
    # Cards de agendamentos
    for idx, agend in df_filt.iterrows():
        
        # Verificar se está vencido
        esta_vencido = False
        data_chamada_str = agend.get('Data de chamada', '')
        
        if data_chamada_str and data_chamada_str != '':
            try:
                # Tentar múltiplos formatos de data
                data_chamada_dt = None
                
                # Formato brasileiro DD/MM/YYYY
                try:
                    data_chamada_dt = datetime.strptime(data_chamada_str, '%d/%m/%Y')
                except:
                    pass
                
                # Formato ISO YYYY/MM/DD
                if not data_chamada_dt:
                    try:
                        data_chamada_dt = datetime.strptime(data_chamada_str, '%Y/%m/%d')
                    except:
                        pass
                
                # Formato ISO com hífen YYYY-MM-DD
                if not data_chamada_dt:
                    try:
                        data_chamada_dt = datetime.strptime(data_chamada_str, '%Y-%m-%d')
                    except:
                        pass
                
                # Verificar se está vencido
                if data_chamada_dt and data_chamada_dt.date() < hoje_dt.date():
                    esta_vencido = True
            except:
                pass
        
        # Badge de status
        nome_cliente = agend.get('Nome', 'N/D')
        classificacao = agend.get('Classificação', 'N/D')
        status_badge = "🔥 VENCIDO" if esta_vencido else "📅 HOJE"
        
        # Título do expander com status visual
        titulo_card = f"{status_badge} | 👤 {nome_cliente} | 🏷️ {classificacao}"
        
        with st.expander(titulo_card, expanded=False):
            col_esq, col_dir = st.columns([1, 1])
            
            # ========== COLUNA ESQUERDA: INFORMAÇÕES ==========
            with col_esq:
                st.markdown("### 📊 Dados do Cliente")
                
                # Informações básicas
                st.write(f"**👤 Nome:** {nome_cliente}")
                st.write(f"**📱 Telefone:** {agend.get('Telefone', 'N/D')}")
                st.write(f"**🏷️ Classificação:** {classificacao}")
                
                # Valor com formatação
                val = agend.get('Valor', 0)
                if pd.notna(val) and val != '':
                    try:
                        st.write(f"**💰 Valor Total:** R$ {float(val):,.2f}")
                    except:
                        st.write(f"**💰 Valor Total:** {val}")
                else:
                    st.write("**💰 Valor Total:** R$ 0,00")
                
                st.markdown("---")
                
                # Histórico do último atendimento
                st.markdown("### 📝 Último Atendimento")
                
                data_contato = agend.get('Data de contato', 'N/D')
                st.write(f"**📅 Data:** {data_contato}")
                
                rel_at = agend.get('Relato da conversa', '')
                if rel_at and rel_at != '':
                    st.info(f"**Relato anterior:**\n\n{rel_at}")
                else:
                    st.caption("_Sem relato anterior_")
                
                fol_at = agend.get('Follow up', '')
                if fol_at and fol_at != '':
                    st.info(f"**Motivo deste contato:** {fol_at}")
                else:
                    st.caption("_Sem motivo registrado_")
                
                if data_chamada_str and data_chamada_str != '':
                    if esta_vencido:
                        st.error(f"**Agendado para:** {data_chamada_str} ⚠️ VENCIDA")
                    else:
                        st.success(f"**Agendado para:** {data_chamada_str} ✅ HOJE")
                
                obs_at = agend.get('Observação', '')
                if obs_at and obs_at != '':
                    st.info(f"**Obs anterior:** {obs_at}")
            
            # ========== COLUNA DIREITA: NOVO AGENDAMENTO ==========
            with col_dir:
                st.markdown("### ✏️ Registrar Novo Atendimento")
                
                with st.form(key=f"form_atend_{idx}"):
                    
                    st.info("💡 Preencha como foi a conversa de hoje e agende o próximo contato")
                    
                    # Campos do formulário
                    novo_relato = st.text_area(
                        "📝 Como foi a conversa de hoje?",
                        height=120,
                        placeholder="Descreva os principais pontos da conversa...",
                        help="Registre o que foi conversado neste atendimento"
                    )
                    
                    novo_follow = st.text_input(
                        "🎯 Motivo do Próximo Contato:",
                        placeholder="Ex: Enviar proposta, Confirmar interesse...",
                        help="Defina o próximo passo"
                    )
                    
                    nova_data = st.date_input(
                        "📅 Data do Próximo Contato:",
                        value=None,
                        help="Quando será o próximo follow-up?"
                    )
                    
                    nova_obs = st.text_area(
                        "💬 Observações Adicionais:",
                        height=80,
                        placeholder="Informações extras relevantes..."
                    )
                    
                    st.markdown("---")
                    
                    # Botão único: Realizar Novo Agendamento
                    btn_novo_agendamento = st.form_submit_button(
                        "✅ Realizar Novo Agendamento",
                        type="primary",
                        use_container_width=True
                    )
                    
                    # ========== AÇÃO DO BOTÃO ==========
                    if btn_novo_agendamento:
                        # Validação
                        if not novo_relato:
                            st.error("❌ Preencha como foi a conversa de hoje!")
                        elif not novo_follow:
                            st.error("❌ Defina o motivo do próximo contato!")
                        elif not nova_data:
                            st.error("❌ Selecione a data do próximo contato!")
                        else:
                            with st.spinner("Processando novo agendamento..."):
                                try:
                                    conn = get_gsheets_connection()
                                    
                                    # 1. Mover agendamento atual para HISTORICO
                                    df_historico = conn.read(worksheet="HISTORICO", ttl=0)
                                    
                                    # Preparar linha para histórico com data de conclusão
                                    linha_historico = agend.to_dict()
                                    linha_historico['Data de conclusão'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                                    
                                    # Adicionar ao histórico
                                    df_historico_novo = pd.concat([df_historico, pd.DataFrame([linha_historico])], ignore_index=True)
                                    conn.update(worksheet="HISTORICO", data=df_historico_novo)
                                    
                                    # 2. Criar NOVO agendamento em AGENDAMENTOS_ATIVOS
                                    df_agendamentos_atual = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
                                    
                                    novo_agendamento = {
                                        'Data de contato': datetime.now().strftime('%d/%m/%Y'),
                                        'Nome': agend.get('Nome', ''),
                                        'Classificação': agend.get('Classificação', ''),
                                        'Valor': agend.get('Valor', ''),
                                        'Telefone': agend.get('Telefone', ''),
                                        'Relato da conversa': novo_relato,
                                        'Follow up': novo_follow,
                                        'Data de chamada': nova_data.strftime('%d/%m/%Y'),
                                        'Observação': nova_obs
                                    }
                                    
                                    # 3. Remover o agendamento antigo
                                    df_agendamentos_atualizado = df_agendamentos_atual.drop(idx).reset_index(drop=True)
                                    
                                    # 4. Adicionar o novo agendamento
                                    df_agendamentos_final = pd.concat([df_agendamentos_atualizado, pd.DataFrame([novo_agendamento])], ignore_index=True)
                                    
                                    # 5. Salvar em AGENDAMENTOS_ATIVOS
                                    conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_agendamentos_final)
                                    
                                    # Limpar cache e recarregar
                                    carregar_dados.clear()
                                    st.toast("✅ Agendamento atualizado!", icon="✅")
                                    time.sleep(0.5)
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Erro ao processar agendamento: {e}")
        
        st.markdown("---")




# ============================================================================
# RENDER - PÁGINA SUPORTE (VERSÃO COMPLETA COM BUSCA E LOGS)
# ============================================================================

# ============================================================================
# RENDER - PÁGINA SUPORTE (VERSÃO COMPLETA COM BUSCA E LOGS)
# ============================================================================

def render_suporte():
    """Renderiza a página de Suporte - Gestão de Tickets"""
    
    st.title("🆘 Suporte ao Cliente")
    st.markdown("Gerencie tickets de suporte com acompanhamento personalizado")
    st.markdown("---")
    
    # ========== INICIALIZAR SESSION STATE ==========
    if 'ticket_encontrado' not in st.session_state:
        st.session_state.ticket_encontrado = None
    
    if 'mostrar_form_novo' not in st.session_state:
        st.session_state.mostrar_form_novo = False
    
    if 'cliente_selecionado_ticket' not in st.session_state:
        st.session_state.cliente_selecionado_ticket = None
    
    # ========== BARRA DE BUSCA E CRIAÇÃO ==========
    st.subheader("🔍 Buscar Ticket ou Criar Novo")
    
    col_busca1, col_busca2, col_busca3 = st.columns([3, 1, 1])
    
    with col_busca1:
        termo_busca = st.text_input(
            "Digite o ID do Ticket, Nome ou Telefone do cliente",
            placeholder="Ex: TKT-2026-00001 ou João Silva ou 11 99999-9999",
            key="busca_ticket"
        )
    
    with col_busca2:
        btn_buscar = st.button("🔍 Buscar", type="primary", use_container_width=True)
    
    with col_busca3:
        btn_novo_ticket = st.button("➕ Novo Ticket", type="secondary", use_container_width=True)
    
    st.markdown("---")
    
    # ========== ABRIR FORMULÁRIO NOVO TICKET ==========
    if btn_novo_ticket:
        st.session_state.mostrar_form_novo = True
        st.session_state.ticket_encontrado = None
        st.session_state.cliente_selecionado_ticket = None
    
    # ========== FORMULÁRIO: CRIAR NOVO TICKET ==========
    if st.session_state.mostrar_form_novo:
        st.subheader("🎫 Abrir Novo Ticket de Suporte")
        
        # ETAPA 1: BUSCAR E SELECIONAR CLIENTE
        if st.session_state.cliente_selecionado_ticket is None:
            st.info("📋 **Passo 1:** Busque o cliente na base de dados")
            
            col_bc1, col_bc2 = st.columns([3, 1])
            
            with col_bc1:
                termo_busca_cliente = st.text_input(
                    "🔍 Buscar Cliente (Nome ou Telefone)",
                    placeholder="Digite o nome ou telefone",
                    key="busca_cliente_novo"
                )
            
            with col_bc2:
                btn_buscar_cliente = st.button(
                    "🔍 Buscar",
                    type="primary",
                    use_container_width=True,
                    key="btn_buscar_cli"
                )
            
            if btn_buscar_cliente and termo_busca_cliente:
                with st.spinner("Buscando cliente..."):
                    try:
                        conn = st.connection("gsheets", type="GSheetsConnection")
                        df_total = conn.read(worksheet="Total", ttl=0)
                        
                        if df_total.empty:
                            st.warning("⚠️ Nenhum cliente na base de dados")
                        else:
                            termo_limpo = termo_busca_cliente.strip()
                            resultados = []
                            
                            # Buscar por telefone
                            if 'Telefone' in df_total.columns:
                                telefone_busca = limpar_telefone(termo_limpo)
                                df_total['Tel_Limpo'] = df_total['Telefone'].apply(limpar_telefone)
                                mask_tel = df_total['Tel_Limpo'].str.contains(telefone_busca, case=False, na=False, regex=False)
                                resultados = df_total[mask_tel].head(10).to_dict('records')
                            
                            # Se não encontrou, buscar por nome
                            if not resultados and 'Nome' in df_total.columns:
                                mask_nome = df_total['Nome'].astype(str).str.contains(termo_limpo, case=False, na=False, regex=False)
                                resultados = df_total[mask_nome].head(10).to_dict('records')
                            
                            if resultados:
                                st.success(f"✅ {len(resultados)} cliente(s) encontrado(s)!")
                                st.markdown("**Selecione o cliente:**")
                                
                                for i, cliente in enumerate(resultados):
                                    with st.container():
                                        col1, col2 = st.columns([4, 1])
                                        
                                        with col1:
                                            st.write(f"**{cliente.get('Nome', 'N/D')}**")
                                            st.caption(f"📱 {cliente.get('Telefone', 'N/D')} | 🏷️ {cliente.get('Classificação', 'N/D')}")
                                        
                                        with col2:
                                            if st.button("✅ Selecionar", key=f"sel_cli_{i}", use_container_width=True):
                                                st.session_state.cliente_selecionado_ticket = cliente
                                                st.rerun()
                                        
                                        st.markdown("---")
                            else:
                                st.warning(f"⚠️ Nenhum cliente encontrado para: {termo_busca_cliente}")
                                st.info("💡 Cadastre o cliente primeiro na aba 'Total'")
                    
                    except Exception as e:
                        st.error(f"❌ Erro ao buscar: {e}")
            
            elif btn_buscar_cliente:
                st.warning("⚠️ Digite um nome ou telefone")
            
            # Botão cancelar
            if st.button("❌ Cancelar", key="cancelar_busca"):
                st.session_state.mostrar_form_novo = False
                st.session_state.cliente_selecionado_ticket = None
                st.rerun()
            
            return  # Para aqui até selecionar cliente
        
        # ETAPA 2: FORMULÁRIO COM DADOS DO CLIENTE
        else:
            cliente = st.session_state.cliente_selecionado_ticket
            
            st.success(f"✅ Cliente: **{cliente.get('Nome', 'N/D')}** | {cliente.get('Telefone', 'N/D')}")
            
            if st.button("🔄 Trocar Cliente", key="trocar_cli"):
                st.session_state.cliente_selecionado_ticket = None
                st.rerun()
            
            st.markdown("---")
            st.info("📋 **Passo 2:** Preencha os detalhes do ticket")
            
            with st.form(key="form_novo_ticket"):
                
                st.markdown("### 👤 Dados do Cliente")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.info(f"**Nome:**\n{cliente.get('Nome', 'N/D')}")
                with col2:
                    st.info(f"**Telefone:**\n{cliente.get('Telefone', 'N/D')}")
                with col3:
                    st.info(f"**Classificação:**\n{cliente.get('Classificação', 'N/D')}")
                
                st.markdown("### 🎫 Detalhes do Ticket")
                
                col_f1, col_f2 = st.columns(2)
                
                with col_f1:
                    tipo_problema = st.selectbox(
                        "🔧 Tipo de Problema *",
                        ["Defeito no Produto", "Problema na Entrega", "Dúvida Técnica",
                         "Reclamação de Atendimento", "Pedido de Reembolso",
                         "Solicitação de Troca", "Outros"]
                    )
                    
                    prioridade = st.selectbox(
                        "⚠️ Prioridade *",
                        ["Baixa", "Média", "Alta", "Urgente"]
                    )
                
                with col_f2:
                    aberto_por = st.text_input(
                        "👨‍💼 Aberto Por",
                        value="Sistema CRM"
                    )
                
                descricao = st.text_area(
                    "📝 Descrição do Problema *",
                    height=150,
                    placeholder="Descreva detalhadamente o problema..."
                )
                
                st.markdown("---")
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    btn_criar = st.form_submit_button(
                        "✅ Criar Ticket",
                        type="primary",
                        use_container_width=True
                    )
                
                with col_btn2:
                    btn_cancelar = st.form_submit_button(
                        "❌ Cancelar",
                        use_container_width=True
                    )
                
                # AÇÃO: CANCELAR
                if btn_cancelar:
                    st.session_state.mostrar_form_novo = False
                    st.session_state.cliente_selecionado_ticket = None
                    st.rerun()
                
                # AÇÃO: CRIAR TICKET
                if btn_criar:
                    if not descricao:
                        st.error("❌ Preencha a descrição do problema!")
                    else:
                        with st.spinner("Criando ticket..."):
                            try:
                                conn = st.connection("gsheets", type="GSheetsConnection")
                                
                                # Gerar ID
                                id_ticket = gerar_id_ticket()
                                
                                # Ler planilha atual
                                df_suporte = conn.read(worksheet="SUPORTE", ttl=0)
                                
                                # Criar novo ticket
                                novo_ticket = {
                                    'ID_Ticket': id_ticket,
                                    'Nome': cliente.get('Nome', 'N/D'),
                                    'Telefone': cliente.get('Telefone', 'N/D'),
                                    'Classificação': cliente.get('Classificação', 'Não classificado'),
                                    'Tipo_Problema': tipo_problema,
                                    'Prioridade': prioridade,
                                    'Descrição do problema': descricao,
                                    'Data de abertura': datetime.now().strftime('%d/%m/%Y %H:%M'),
                                    'Último contato': '',
                                    'Próximo contato': '',
                                    'Progresso': 0,
                                    'Observações': f'Ticket criado via CRM por {aberto_por}'
                                }
                                
                                # Adicionar à planilha
                                df_novo = pd.concat([df_suporte, pd.DataFrame([novo_ticket])], ignore_index=True)
                                conn.update(worksheet="SUPORTE", data=df_novo)
                                
                                # Registrar log
                                dados_log = {
                                    'Nome': cliente.get('Nome', ''),
                                    'Telefone': cliente.get('Telefone', ''),
                                    'Classificacao': cliente.get('Classificação', ''),
                                    'TipoProblema': tipo_problema,
                                    'Prioridade': prioridade,
                                    'Descricao': descricao
                                }
                                
                                registrar_ticket_log_aberto(id_ticket, dados_log, aberto_por)
                                
                                # Limpar cache e session state
                                carregar_dados_suporte.clear()
                                st.success(f"✅ Ticket **{id_ticket}** criado com sucesso!")
                                st.balloons()
                                
                                st.session_state.mostrar_form_novo = False
                                st.session_state.cliente_selecionado_ticket = None
                                
                                time.sleep(2)
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Erro ao criar ticket: {e}")
                                st.exception(e)
            
            return  # Para não mostrar lista enquanto cria ticket
    
    # ========== BUSCAR TICKET ==========
    if btn_buscar and termo_busca:
        with st.spinner("Buscando ticket..."):
            try:
                conn = st.connection("gsheets", type="GSheetsConnection")
                df_suporte = conn.read(worksheet="SUPORTE", ttl=0)
                
                if df_suporte.empty:
                    st.warning("⚠️ Nenhum ticket no sistema")
                    st.session_state.ticket_encontrado = None
                else:
                    termo_limpo = termo_busca.strip()
                    resultado = None
                    
                    # Buscar por ID
                    if 'ID_Ticket' in df_suporte.columns:
                        mask_id = df_suporte['ID_Ticket'].astype(str).str.contains(termo_limpo, case=False, na=False, regex=False)
                        if mask_id.any():
                            resultado = df_suporte[mask_id].iloc[0]
                    
                    # Buscar por telefone
                    if resultado is None and 'Telefone' in df_suporte.columns:
                        tel_busca = limpar_telefone(termo_limpo)
                        df_suporte['Tel_Limpo'] = df_suporte['Telefone'].apply(limpar_telefone)
                        mask_tel = df_suporte['Tel_Limpo'].str.contains(tel_busca, case=False, na=False, regex=False)
                        if mask_tel.any():
                            resultado = df_suporte[mask_tel].iloc[0]
                    
                    # Buscar por nome
                    if resultado is None and 'Nome' in df_suporte.columns:
                        mask_nome = df_suporte['Nome'].astype(str).str.contains(termo_limpo, case=False, na=False, regex=False)
                        if mask_nome.any():
                            resultado = df_suporte[mask_nome].iloc[0]
                    
                    if resultado is not None:
                        st.session_state.ticket_encontrado = resultado.to_dict()
                    else:
                        st.warning(f"⚠️ Ticket não encontrado: {termo_busca}")
                        st.session_state.ticket_encontrado = None
            
            except Exception as e:
                st.error(f"❌ Erro na busca: {e}")
                st.session_state.ticket_encontrado = None
    
    elif btn_buscar:
        st.warning("⚠️ Digite algo para buscar")
    
    # ========== EXIBIR TICKET ENCONTRADO ==========
    if st.session_state.ticket_encontrado is not None:
        ticket = st.session_state.ticket_encontrado
        
        id_ticket = ticket.get('ID_Ticket', 'N/D')
        nome = ticket.get('Nome', 'N/D')
        prioridade = ticket.get('Prioridade', 'Média')
        
        icones = {'Urgente': '🔴', 'Alta': '🟠', 'Média': '🟡', 'Baixa': '🟢'}
        icone = icones.get(prioridade, '⚪')
        
        st.success(f"✅ Ticket encontrado: **{id_ticket}** - {nome}")
        
        if st.button("⬅️ Voltar para Lista", key="voltar_lista"):
            st.session_state.ticket_encontrado = None
            st.rerun()
        
        st.markdown("---")
        st.subheader(f"📋 Detalhes do Ticket {id_ticket}")
        
        # Exibir informações do ticket
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**{icone} Prioridade:** {prioridade}")
            st.write(f"**👤 Nome:** {nome}")
            st.write(f"**📱 Telefone:** {ticket.get('Telefone', 'N/D')}")
            st.write(f"**🏷️ Classificação:** {ticket.get('Classificação', 'N/D')}")
        
        with col2:
            st.write(f"**🔧 Tipo:** {ticket.get('Tipo_Problema', 'N/D')}")
            st.write(f"**📅 Aberto em:** {ticket.get('Data de abertura', 'N/D')}")
            
            progresso = ticket.get('Progresso', 0)
            try:
                prog_val = float(progresso) if progresso else 0
            except:
                prog_val = 0
            
            st.write(f"**📊 Progresso:** {prog_val}%")
            st.progress(prog_val / 100)
        
        st.markdown("---")
        st.markdown("### 🔍 Descrição do Problema")
        descricao = ticket.get('Descrição do problema', '')
        if descricao:
            st.error(f"**Problema relatado:**\n\n{descricao}")
        else:
            st.caption("_Sem descrição_")
        
        st.markdown("---")
        st.markdown("### 📝 Histórico")
        
        ultimo = ticket.get('Último contato', '')
        if ultimo:
            st.info(f"**Último acompanhamento:**\n\n{ultimo}")
        else:
            st.caption("_Nenhum acompanhamento registrado_")
        
        proximo = ticket.get('Próximo contato', '')
        if proximo:
            st.info(f"**📅 Próximo contato:** {proximo}")
        
        obs = ticket.get('Observações', '')
        if obs:
            st.info(f"**💬 Observações:** {obs}")
        
        return  # Para não mostrar lista quando está vendo ticket
    
    # ========== LISTA DE TICKETS ==========
    st.subheader("📋 Tickets Ativos")
    
    with st.spinner("Carregando tickets..."):
        df_suporte = carregar_dados_suporte()
    
    if df_suporte.empty:
        st.info("Nenhum ticket ativo no momento")
        st.write("Use o botão '**Novo Ticket**' acima para abrir um chamado")
        return
    
    # Métricas
    hoje = datetime.now().date()
    hoje_str = hoje.strftime('%d/%m/%Y')
    
    col_m1, col_m2, col_m3 = st.columns(3)
    
    with col_m1:
        st.metric("🎫 Total de Tickets", len(df_suporte))
    
    with col_m2:
        urgentes = len(df_suporte[df_suporte['Prioridade'] == 'Urgente'])
        st.metric("🔴 Urgentes", urgentes)
    
    with col_m3:
        em_aberto = len(df_suporte[df_suporte['Progresso'] < 100])
        st.metric("⏳ Em Aberto", em_aberto)
    
    st.markdown("---")
    
    # Filtros
    st.subheader("🔍 Filtros")
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        filtro_prioridade = st.selectbox(
            "Prioridade",
            ["Todas", "Urgente", "Alta", "Média", "Baixa"]
        )
    
    with col_f2:
        busca_lista = st.text_input(
            "Buscar por nome",
            placeholder="Digite o nome do cliente..."
        )
    
    # Aplicar filtros
    df_filtrado = df_suporte.copy()
    
    if filtro_prioridade != "Todas":
        df_filtrado = df_filtrado[df_filtrado['Prioridade'] == filtro_prioridade]
    
    if busca_lista:
        df_filtrado = df_filtrado[
            df_filtrado['Nome'].astype(str).str.contains(busca_lista, case=False, na=False, regex=False)
        ]
    
    st.markdown("---")
    
    if df_filtrado.empty:
        st.info("Nenhum ticket encontrado com os filtros aplicados")
        return
    
    # Ordenar por prioridade
    ordem_prioridade = {'Urgente': 0, 'Alta': 1, 'Média': 2, 'Baixa': 3}
    df_filtrado['Ordem'] = df_filtrado['Prioridade'].map(ordem_prioridade).fillna(4)
    df_filtrado = df_filtrado.sort_values('Ordem')
    
    # Exibir tickets
    st.subheader(f"📚 Lista de Tickets ({len(df_filtrado)})")
    
    icones = {'Urgente': '🔴', 'Alta': '🟠', 'Média': '🟡', 'Baixa': '🟢'}
    
    for idx, row in df_filtrado.iterrows():
        id_ticket = row.get('ID_Ticket', 'N/D')
        nome = row.get('Nome', 'N/D')
        prioridade = row.get('Prioridade', 'Média')
        progresso = row.get('Progresso', 0)
        
        try:
            prog_val = float(progresso) if progresso else 0
        except:
            prog_val = 0
        
        icone = icones.get(prioridade, '⚪')
        
        # Badge de status
        if prog_val >= 100:
            badge = "✅ RESOLVIDO"
        elif prog_val >= 50:
            badge = "🔄 EM ANDAMENTO"
        else:
            badge = "🆕 ABERTO"
        
        titulo = f"{badge} | {icone} {id_ticket} | {nome} | {prog_val}%"
        
        expandir = prioridade == 'Urgente'
        
        with st.expander(titulo, expanded=expandir):
            col_info, col_acao = st.columns([3, 1])
            
            with col_info:
                st.write(f"**🎫 ID:** {id_ticket}")
                st.write(f"**👤 Cliente:** {nome}")
                st.write(f"**📱 Telefone:** {row.get('Telefone', 'N/D')}")
                st.write(f"**{icone} Prioridade:** {prioridade}")
                st.write(f"**🔧 Tipo:** {row.get('Tipo_Problema', 'N/D')}")
                st.write(f"**📅 Aberto:** {row.get('Data de abertura', 'N/D')}")
                
                proximo = row.get('Próximo contato', '')
                if proximo:
                    st.write(f"**📅 Próximo contato:** {proximo}")
            
            with col_acao:
                if st.button("👁️ Ver Detalhes", key=f"ver_{idx}_{id_ticket}", use_container_width=True):
                    st.session_state.ticket_encontrado = row.to_dict()
                    st.rerun()
            
            st.markdown("---")


# ============================================================================
# RENDER - PÁGINA HISTÓRICO
# ============================================================================

def render_historico():
    """Renderiza a página de Histórico - Busca Unificada de Clientes"""
    
    st.title("📜 Histórico de Clientes")
    st.markdown("Busque clientes e visualize todo o histórico de atendimentos")
    st.markdown("---")
    
    # Inicializar session_state
    if 'cliente_encontrado' not in st.session_state:
        st.session_state.cliente_encontrado = None
    
    # ========== BARRA DE BUSCA ==========
    st.subheader("🔍 Buscar Cliente")
    
    col_busca1, col_busca2 = st.columns([3, 1])
    
    with col_busca1:
        termo_busca = st.text_input(
            "Digite o telefone ou nome do cliente:",
            placeholder="Ex: (11) 99999-9999 ou João Silva",
            help="Busca por telefone ou nome em todas as bases",
            key="busca_historico"
        )
    
    with col_busca2:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_buscar = st.button("🔍 Buscar", type="primary", use_container_width=True)
    
    st.markdown("---")
    
    # ========== REALIZAR BUSCA ==========
    if btn_buscar and termo_busca:
        
        with st.spinner("🔎 Buscando em todas as bases..."):
            # Carregar todas as abas necessárias
            df_total = carregar_dados("Total")
            
            # Limpar termo de busca
            termo_limpo = termo_busca.strip()
            
            # Buscar na aba Total (dados cadastrais)
            cliente_encontrado = None
            
            if not df_total.empty:
                # Buscar por telefone
                if 'Telefone' in df_total.columns:
                    mask_telefone = df_total['Telefone'].astype(str).str.contains(termo_limpo, case=False, na=False, regex=False)
                    resultado_telefone = df_total[mask_telefone]
                    
                    if not resultado_telefone.empty:
                        cliente_encontrado = resultado_telefone.iloc[0]
                
                # Se não encontrou por telefone, buscar por nome
                if cliente_encontrado is None and 'Nome' in df_total.columns:
                    mask_nome = df_total['Nome'].astype(str).str.contains(termo_limpo, case=False, na=False, regex=False)
                    resultado_nome = df_total[mask_nome]
                    
                    if not resultado_nome.empty:
                        cliente_encontrado = resultado_nome.iloc[0]
            
            # Salvar no session_state
            if cliente_encontrado is not None:
                st.session_state.cliente_encontrado = cliente_encontrado.to_dict()
            else:
                st.session_state.cliente_encontrado = None
    
    # ========== EXIBIR RESULTADO ==========
    if st.session_state.cliente_encontrado is not None:
        
        cliente = st.session_state.cliente_encontrado
        nome_cliente = cliente.get('Nome', 'N/D')
        telefone_cliente = cliente.get('Telefone', '')
        
        st.success(f"✅ Cliente encontrado: **{nome_cliente}**")
        
        # Botão para limpar busca
        if st.button("🔄 Nova Busca"):
            st.session_state.cliente_encontrado = None
            st.rerun()
        
        st.markdown("---")
        
        # ========== DADOS CADASTRAIS ==========
        st.subheader("📊 Dados Cadastrais")
        
        col_info1, col_info2, col_info3 = st.columns(3)
        
        with col_info1:
            st.write(f"**👤 Nome:** {nome_cliente}")
            st.write(f"**📱 Telefone:** {telefone_cliente}")
            st.write(f"**📧 E-mail:** {cliente.get('Email', 'N/D')}")
        
        with col_info2:
            st.write(f"**🏷️ Classificação:** {cliente.get('Classificação ', 'N/D')}")
            
            valor = cliente.get('Valor', 0)
            if pd.notna(valor) and valor != '':
                try:
                    st.write(f"**💰 Valor Total:** R$ {float(valor):,.2f}")
                except:
                    st.write(f"**💰 Valor Total:** {valor}")
            else:
                st.write("**💰 Valor Total:** R$ 0,00")
            
            compras = cliente.get('Compras', 0)
            if pd.notna(compras) and compras != '':
                try:
                    st.write(f"**🛒 Total de Compras:** {int(float(compras))}")
                except:
                    st.write(f"**🛒 Total de Compras:** {compras}")
            else:
                st.write("**🛒 Total de Compras:** 0")
        
        with col_info3:
            dias = cliente.get('Dias desde a compra', 0)
            if pd.notna(dias) and dias != '':
                try:
                    st.write(f"**📅 Dias desde última compra:** {int(round(float(dias)))}")
                except:
                    st.write(f"**📅 Dias desde última compra:** {dias}")
            else:
                st.write("**📅 Dias desde última compra:** N/D")
        
        st.markdown("---")
        
        # ========== BUSCAR HISTÓRICO POR TELEFONE ==========
        df_historico = carregar_dados("HISTORICO")
        df_agendamentos = carregar_dados("AGENDAMENTOS_ATIVOS")
        df_suporte = carregar_dados("SUPORTE")
        
        historico_cliente = []
        agendamentos_ativos = []
        tickets_suporte = []
        
        # Limpar telefone do cliente para comparação
        telefone_limpo = limpar_telefone(telefone_cliente)
        
        # Histórico de atendimentos finalizados
        if not df_historico.empty and 'Telefone' in df_historico.columns:
            df_historico['Telefone_Limpo'] = df_historico['Telefone'].apply(limpar_telefone)
            historico_cliente = df_historico[
                df_historico['Telefone_Limpo'].str.contains(telefone_limpo, case=False, na=False, regex=False)
            ].to_dict('records')
        
        # Agendamentos ativos
        if not df_agendamentos.empty and 'Telefone' in df_agendamentos.columns:
            df_agendamentos['Telefone_Limpo'] = df_agendamentos['Telefone'].apply(limpar_telefone)
            agendamentos_ativos = df_agendamentos[
                df_agendamentos['Telefone_Limpo'].str.contains(telefone_limpo, case=False, na=False, regex=False)
            ].to_dict('records')
        
        # Tickets de suporte
        if not df_suporte.empty and 'Telefone' in df_suporte.columns:
            df_suporte['Telefone_Limpo'] = df_suporte['Telefone'].apply(limpar_telefone)
            tickets_suporte = df_suporte[
                df_suporte['Telefone_Limpo'].str.contains(telefone_limpo, case=False, na=False, regex=False)
            ].to_dict('records')
        
        # ========== MÉTRICAS DE HISTÓRICO ==========
        st.subheader("📈 Resumo de Atendimentos")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            st.metric("📜 Histórico", len(historico_cliente), help="Atendimentos finalizados")
        
        with col_m2:
            st.metric("📞 Agendamentos Ativos", len(agendamentos_ativos), help="Atendimentos em andamento")
        
        with col_m3:
            st.metric("🆘 Tickets de Suporte", len(tickets_suporte), help="Chamados de suporte")
        
        st.markdown("---")
        
        # ========== EXIBIR HISTÓRICO ==========
        if historico_cliente:
            st.subheader(f"📜 Histórico de Atendimentos ({len(historico_cliente)})")
            
            for i, hist in enumerate(historico_cliente):
                with st.expander(f"📅 {hist.get('Data de contato', 'N/D')} - {hist.get('Follow up', 'Atendimento')}"):
                    col_h1, col_h2 = st.columns(2)
                    
                    with col_h1:
                        st.write(f"**📅 Data:** {hist.get('Data de contato', 'N/D')}")
                        st.write(f"**🏷️ Classificação:** {hist.get('Classificação', 'N/D')}")
                        st.write(f"**🎯 Follow-up:** {hist.get('Follow up', 'N/D')}")
                    
                    with col_h2:
                        st.write(f"**📅 Data da chamada:** {hist.get('Data de chamada', 'N/D')}")
                        st.write(f"**✅ Finalizado em:** {hist.get('Data de conclusão', 'N/D')}")
                    
                    st.markdown("---")
                    st.write(f"**📝 Relato:**")
                    st.info(hist.get('Relato da conversa', 'Sem relato'))
                    
                    if hist.get('Observação'):
                        st.write(f"**💬 Observação:** {hist.get('Observação')}")
            
            st.markdown("---")
        else:
            st.info("📜 Nenhum histórico de atendimento encontrado para este cliente")
            st.markdown("---")
        
        # ========== AGENDAMENTOS ATIVOS ==========
        if agendamentos_ativos:
            st.subheader(f"📞 Agendamentos Ativos ({len(agendamentos_ativos)})")
            
            for agend in agendamentos_ativos:
                with st.expander(f"📅 {agend.get('Data de chamada', 'N/D')} - {agend.get('Follow up', 'Atendimento')}"):
                    st.write(f"**📅 Agendado para:** {agend.get('Data de chamada', 'N/D')}")
                    st.write(f"**🎯 Motivo:** {agend.get('Follow up', 'N/D')}")
                    st.write(f"**📝 Último contato:** {agend.get('Data de contato', 'N/D')}")
                    
                    if agend.get('Relato da conversa'):
                        st.info(f"**Relato:** {agend.get('Relato da conversa')}")
            
            st.markdown("---")
        
        # ========== TICKETS DE SUPORTE ==========
        if tickets_suporte:
            st.subheader(f"🆘 Tickets de Suporte ({len(tickets_suporte)})")
            
            for ticket in tickets_suporte:
                with st.expander(f"🎫 {ticket.get('Data de abertura', 'N/D')} - {ticket.get('Assunto', 'Suporte')}"):
                    st.write(f"**📅 Aberto em:** {ticket.get('Data de abertura', 'N/D')}")
                    st.write(f"**🏷️ Status:** {ticket.get('Status', 'N/D')}")
                    st.write(f"**📝 Problema:** {ticket.get('Descrição', 'N/D')}")
            
            st.markdown("---")
        
        # ========== CRIAR NOVO ATENDIMENTO ==========
        st.subheader("➕ Criar Novo Atendimento")
        
        col_acao1, col_acao2 = st.columns(2)
        
        with col_acao1:
            st.markdown("### 📞 Criar Agendamento")
            st.info("💡 Use para vendas, follow-ups comerciais ou satisfação")
            
            with st.form(key="form_novo_agendamento"):
                
                motivo_agend = st.text_input(
                    "🎯 Motivo do contato:",
                    placeholder="Ex: Oferta de novo produto..."
                )
                
                data_agend = st.date_input(
                    "📅 Data do agendamento:",
                    value=None
                )
                
                obs_agend = st.text_area(
                    "💬 Observações:",
                    height=100,
                    placeholder="Informações relevantes..."
                )
                
                btn_criar_agend = st.form_submit_button(
                    "✅ Criar Agendamento",
                    type="primary",
                    use_container_width=True
                )
                
                if btn_criar_agend:
                    if not motivo_agend:
                        st.error("❌ Defina o motivo do contato!")
                    elif not data_agend:
                        st.error("❌ Selecione a data do agendamento!")
                    else:
                        try:
                            conn = get_gsheets_connection()
                            df_agend_atual = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
                            
                            novo_agend = {
                                'Data de contato': datetime.now().strftime('%d/%m/%Y'),
                                'Nome': nome_cliente,
                                'Classificação': cliente.get('Classificação ', 'N/D'),
                                'Valor': cliente.get('Valor', ''),
                                'Telefone': telefone_cliente,
                                'Relato da conversa': '',
                                'Follow up': motivo_agend,
                                'Data de chamada': data_agend.strftime('%d/%m/%Y'),
                                'Observação': obs_agend if obs_agend else 'Agendamento criado via Histórico'
                            }
                            
                            df_novo = pd.concat([df_agend_atual, pd.DataFrame([novo_agend])], ignore_index=True)
                            conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_novo)
                            
                            carregar_dados.clear()
                            st.success(f"✅ Agendamento criado!")
                            time.sleep(1)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")
        
        with col_acao2:
            st.markdown("### 🆘 Abrir Ticket de Suporte")
            st.warning("⚠️ Use para problemas técnicos ou reclamações")
            
            with st.form(key="form_novo_suporte"):
                
                assunto_suporte = st.text_input(
                    "📌 Assunto:",
                    placeholder="Ex: Produto com defeito..."
                )
                
                prioridade = st.selectbox(
                    "🚨 Prioridade:",
                    ["Baixa", "Média", "Alta", "Urgente"]
                )
                
                descricao_suporte = st.text_area(
                    "📝 Descrição do problema:",
                    height=100,
                    placeholder="Descreva o problema..."
                )
                
                btn_criar_suporte = st.form_submit_button(
                    "🆘 Abrir Ticket",
                    type="secondary",
                    use_container_width=True
                )
                
                if btn_criar_suporte:
                    if not assunto_suporte:
                        st.error("❌ Informe o assunto!")
                    elif not descricao_suporte:
                        st.error("❌ Descreva o problema!")
                    else:
                        try:
                            conn = get_gsheets_connection()
                            df_suporte_atual = conn.read(worksheet="SUPORTE", ttl=0)
                            
                            novo_ticket = {
                                'Data de abertura': datetime.now().strftime('%d/%m/%Y %H:%M'),
                                'Nome': nome_cliente,
                                'Telefone': telefone_cliente,
                                'Assunto': assunto_suporte,
                                'Prioridade': prioridade,
                                'Status': 'Aberto',
                                'Descrição': descricao_suporte,
                                'Data de atualização': datetime.now().strftime('%d/%m/%Y %H:%M'),
                                'Solução': '',
                                'Data de resolução': ''
                            }
                            
                            df_novo = pd.concat([df_suporte_atual, pd.DataFrame([novo_ticket])], ignore_index=True)
                            conn.update(worksheet="SUPORTE", data=df_novo)
                            
                            carregar_dados.clear()
                            st.success(f"✅ Ticket aberto!")
                            time.sleep(1)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")
    
    elif btn_buscar and not termo_busca:
        st.warning("⚠️ Digite um telefone ou nome para buscar")
    
    elif st.session_state.cliente_encontrado is None and not btn_buscar:
        st.info("👆 Digite o telefone ou nome do cliente acima e clique em Buscar")

# ============================================================================
# RENDER - PÁGINA DASHBOARD
# ============================================================================

def render_dashboard():
    """Renderiza a página de Dashboard com análises e gráficos"""
    
    st.title("📊 Dashboard Analítico")
    st.markdown("Visão geral e análises do CRM")
    st.markdown("---")
    
    # Aqui vamos adicionar os gráficos aos poucos
    st.info("🚧 Dashboard em construção - Gráficos serão adicionados passo a passo")
    
    # Espaço reservado para gráficos futuros
    st.subheader("📈 Análises")
    st.write("Aqui entrarão os gráficos e métricas")


# ============================================================================
# SIDEBAR E NAVEGAÇÃO
# ============================================================================

with st.sidebar:
    st.title("📋 Menu Principal")
    st.markdown("---")
    pagina = st.radio(
        "Navegação:",
        ["✅ Check-in", "📞 Em Atendimento", "🆘 Suporte", "📜 Histórico", "Dashboard 📈" ],
        index=0
    )
    st.markdown("---")
    st.caption("CRM Pós-Vendas v1.0")

# ============================================================================
# ROUTER - CHAMADA DAS PÁGINAS
# ============================================================================

if pagina == "✅ Check-in":
    render_checkin()
elif pagina == "📞 Em Atendimento":
    render_em_atendimento()
elif pagina == "🆘 Suporte":
    render_suporte()
elif pagina == "📜 Histórico":
    render_historico()
elif menu == "Dashboard 📈":
    render_dashboard()    
