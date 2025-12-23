
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
    """Remove caracteres especiais do telefone, deixando apenas números"""
    if pd.isna(telefone) or telefone == '':
        return ''
    return ''.join(filter(str.isdigit, str(telefone)))

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
    """Gera ID único no formato TKT-2025-00014"""
    try:
        conn = get_gsheets_connection()
        df_log = conn.read(worksheet="LOG_TICKETS_ABERTOS", ttl=0)
        
        ano_atual = datetime.now().year
        
        # Filtrar tickets do ano atual
        if not df_log.empty and 'ID_Ticket' in df_log.columns:
            tickets_ano = df_log[df_log['ID_Ticket'].str.contains(f'TKT-{ano_atual}', na=False)]
            if not tickets_ano.empty:
                # Pegar último número
                ultimos_numeros = tickets_ano['ID_Ticket'].str.extract(r'TKT-\d{4}-(\d{5})')[0].astype(int)
                proximo_numero = ultimos_numeros.max() + 1
            else:
                proximo_numero = 1
        else:
            proximo_numero = 1
        
        # Formatar com 5 dígitos
        id_ticket = f"TKT-{ano_atual}-{proximo_numero:05d}"
        return id_ticket
        
    except Exception as e:
        st.error(f"Erro ao gerar ID: {e}")
        return f"TKT-{datetime.now().year}-00001"


def registrar_ticket_log_aberto(id_ticket, dados_ticket, aberto_por):
    """Registra ticket na aba LOG_TICKETS_ABERTOS"""
    try:
        conn = get_gsheets_connection()
        df_log = conn.read(worksheet="LOG_TICKETS_ABERTOS", ttl=0)
        
        agora = datetime.now()
        dias_semana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        
        nova_linha = {
            'ID_Ticket': id_ticket,
            'Data_Abertura': agora.strftime('%d/%m/%Y'),
            'Hora_Abertura': agora.strftime('%H:%M:%S'),
            'Nome_Cliente': dados_ticket.get('Nome', ''),
            'Telefone': dados_ticket.get('Telefone', ''),
            'Classificacao_Cliente': dados_ticket.get('Classificacao', ''),
            'Tipo_Problema': dados_ticket.get('Tipo_Problema', ''),
            'Prioridade': dados_ticket.get('Prioridade', ''),
            'Descricao_Resumida': dados_ticket.get('Descricao', ''),
            'Aberto_Por': aberto_por,
            'Dia_Semana': dias_semana[agora.weekday()]
        }
        
        df_novo = pd.concat([df_log, pd.DataFrame([nova_linha])], ignore_index=True)
        conn.update(worksheet="LOG_TICKETS_ABERTOS", data=df_novo)
        return True
        
    except Exception as e:
        st.error(f"Erro ao registrar no log de abertos: {e}")
        return False


def registrar_ticket_log_resolvido(id_ticket, dados_resolucao, resolvido_por):
    """Registra ticket resolvido na aba LOG_TICKETS_RESOLVIDOS"""
    try:
        conn = get_gsheets_connection()
        
        # Buscar dados originais do ticket no LOG_ABERTOS
        df_log_abertos = conn.read(worksheet="LOG_TICKETS_ABERTOS", ttl=0)
        ticket_original = df_log_abertos[df_log_abertos['ID_Ticket'] == id_ticket]
        
        if ticket_original.empty:
            st.warning(f"Ticket {id_ticket} não encontrado no log de abertos")
            return False
        
        ticket_orig = ticket_original.iloc[0]
        
        # Calcular tempo de resolução
        data_abertura_str = ticket_orig.get('Data_Abertura', '')
        hora_abertura_str = ticket_orig.get('Hora_Abertura', '')
        
        try:
            data_hora_abertura = datetime.strptime(f"{data_abertura_str} {hora_abertura_str}", '%d/%m/%Y %H:%M:%S')
            data_hora_resolucao = datetime.now()
            tempo_resolucao = (data_hora_resolucao - data_hora_abertura).total_seconds() / 3600  # em horas
        except:
            tempo_resolucao = 0
        
        # Registrar em LOG_TICKETS_RESOLVIDOS
        df_log_resolvidos = conn.read(worksheet="LOG_TICKETS_RESOLVIDOS", ttl=0)
        
        nova_linha = {
            'ID_Ticket': id_ticket,
            'Data_Abertura': ticket_orig.get('Data_Abertura', ''),
            'Data_Resolucao': datetime.now().strftime('%d/%m/%Y'),
            'Tempo_Resolucao_Horas': round(tempo_resolucao, 2),
            'Nome_Cliente': ticket_orig.get('Nome_Cliente', ''),
            'Telefone': ticket_orig.get('Telefone', ''),
            'Tipo_Problema': ticket_orig.get('Tipo_Problema', ''),
            'Prioridade': ticket_orig.get('Prioridade', ''),
            'Como_Foi_Resolvido': dados_resolucao.get('Solucao', ''),
            'Resultado_Final': dados_resolucao.get('Resultado', ''),
            'Gerou_Conversao': dados_resolucao.get('Conversao', 'Não'),
            'Resolvido_Por': resolvido_por
        }
        
        df_novo = pd.concat([df_log_resolvidos, pd.DataFrame([nova_linha])], ignore_index=True)
        conn.update(worksheet="LOG_TICKETS_RESOLVIDOS", data=df_novo)
        return True
        
    except Exception as e:
        st.error(f"Erro ao registrar no log de resolvidos: {e}")
        return False



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
    """Renderiza a página de Suporte - Gestão de Tickets com Busca Unificada"""
    
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
            placeholder="Ex: TKT-2025-00014 ou João Silva ou 11 99999-9999",
            help="Busca por ID, nome ou telefone em todos os tickets",
            key="busca_ticket"
        )
    
    with col_busca2:
        btn_buscar = st.button("🔍 Buscar", type="primary", use_container_width=True)
    
    with col_busca3:
        btn_novo_ticket = st.button("➕ Novo Ticket", type="secondary", use_container_width=True)
    
    st.markdown("---")
    
    # ========== FORMULÁRIO: CRIAR NOVO TICKET ==========
    if btn_novo_ticket:
        st.session_state.mostrar_form_novo = True
        st.session_state.ticket_encontrado = None
        if 'cliente_selecionado_ticket' not in st.session_state:
            st.session_state.cliente_selecionado_ticket = None
    
    if st.session_state.mostrar_form_novo:
        st.subheader("🎫 Abrir Novo Ticket de Suporte")
        
        # ========== ETAPA 1: BUSCAR CLIENTE NA ABA TOTAL ==========
        if st.session_state.cliente_selecionado_ticket is None:
            st.info("📋 **Passo 1:** Busque o cliente na base de dados")
            
            col_busca_cliente1, col_busca_cliente2 = st.columns([3, 1])
            
            with col_busca_cliente1:
                termo_busca_cliente = st.text_input(
                    "🔍 Buscar Cliente (Nome ou Telefone)",
                    placeholder="Digite o nome ou telefone do cliente",
                    key="busca_cliente_novo_ticket"
                )
            
            with col_busca_cliente2:
                btn_buscar_cliente = st.button(
                    "🔍 Buscar Cliente", 
                    type="primary", 
                    use_container_width=True,
                    key="btn_buscar_cliente_ticket"
                )
            
            # Realizar busca na aba TOTAL
            if btn_buscar_cliente and termo_busca_cliente:
                with st.spinner("Buscando cliente..."):
                    try:
                        conn = get_gsheets_connection()
                        df_total = conn.read(worksheet="Total", ttl=0)
                        
                        if df_total.empty:
                            st.warning("⚠️ Nenhum cliente encontrado na base de dados")
                        else:
                            termo_limpo = termo_busca_cliente.strip()
                            telefone_limpo = limpar_telefone(termo_limpo)
                            
                            resultados = []
                            
                            # Buscar por telefone
                            if 'Telefone' in df_total.columns:
                                df_total['Telefone_Limpo'] = df_total['Telefone'].apply(limpar_telefone)
                                mask_tel = df_total['Telefone_Limpo'].str.contains(telefone_limpo, case=False, na=False, regex=False)
                                resultados_tel = df_total[mask_tel]
                                if not resultados_tel.empty:
                                    resultados = resultados_tel.to_dict('records')
                            
                            # Se não encontrou por telefone, buscar por nome
                            if not resultados and 'Nome' in df_total.columns:
                                mask_nome = df_total['Nome'].astype(str).str.contains(termo_limpo, case=False, na=False)
                                resultados_nome = df_total[mask_nome]
                                if not resultados_nome.empty:
                                    resultados = resultados_nome.to_dict('records')
                            
                            if resultados:
                                st.success(f"✅ {len(resultados)} cliente(s) encontrado(s)!")
                                
                                # Mostrar resultados para seleção
                                st.markdown("**Selecione o cliente:**")
                                
                                for i, cliente in enumerate(resultados[:5]):  # Limitar a 5 resultados
                                    nome_cliente = cliente.get('Nome', 'N/D')
                                    tel_cliente = cliente.get('Telefone', 'N/D')
                                    class_cliente = cliente.get('Classificação', 'Não classificado')
                                    
                                    col1, col2 = st.columns([4, 1])
                                    
                                    with col1:
                                        st.write(f"**{nome_cliente}** | {tel_cliente} | {class_cliente}")
                                    
                                    with col2:
                                        if st.button(
                                            "Selecionar", 
                                            key=f"selecionar_cliente_{i}",
                                            use_container_width=True
                                        ):
                                            st.session_state.cliente_selecionado_ticket = cliente
                                            st.rerun()
                            else:
                                st.warning(f"⚠️ Nenhum cliente encontrado para: {termo_busca_cliente}")
                                st.info("💡 **Dica:** Se o cliente não existe na base, cadastre-o primeiro na aba TOTAL")
                    
                    except Exception as e:
                        st.error(f"❌ Erro ao buscar cliente: {e}")
            
            elif btn_buscar_cliente and not termo_busca_cliente:
                st.warning("⚠️ Digite um nome ou telefone para buscar")
            
            # Opção para cancelar
            if st.button("❌ Cancelar", key="cancelar_busca_cliente"):
                st.session_state.mostrar_form_novo = False
                st.session_state.cliente_selecionado_ticket = None
                st.rerun()
            
            st.markdown("---")
            return  # Retorna até o cliente ser selecionado
        
        # ========== ETAPA 2: FORMULÁRIO COM DADOS PRÉ-PREENCHIDOS ==========
        else:
            cliente = st.session_state.cliente_selecionado_ticket
            
            # Exibir cliente selecionado
            st.success(f"✅ Cliente selecionado: **{cliente.get('Nome', 'N/D')}** | {cliente.get('Telefone', 'N/D')}")
            
            if st.button("🔄 Trocar Cliente", key="trocar_cliente_ticket"):
                st.session_state.cliente_selecionado_ticket = None
                st.rerun()
            
            st.markdown("---")
            st.info("📋 **Passo 2:** Preencha os detalhes do ticket")
            
            with st.form(key="form_novo_ticket_suporte"):
                
                # Dados do cliente (somente leitura via st.info)
                st.markdown("### 👤 Dados do Cliente")
                
                col_info1, col_info2, col_info3 = st.columns(3)
                
                with col_info1:
                    st.info(f"**Nome:**  \n{cliente.get('Nome', 'N/D')}")
                
                with col_info2:
                    st.info(f"**Telefone:**  \n{cliente.get('Telefone', 'N/D')}")
                
                with col_info3:
                    st.info(f"**Classificação:**  \n{cliente.get('Classificação', 'Não classificado')}")
                
                st.markdown("---")
                st.markdown("### 🎫 Detalhes do Ticket")
                
                col_form1, col_form2 = st.columns(2)
                
                with col_form1:
                    tipo_problema = st.selectbox(
                        "🔧 Tipo de Problema *",
                        ["Defeito no Produto", "Problema na Entrega", "Dúvida Técnica", 
                         "Reclamação de Atendimento", "Pedido de Reembolso", 
                         "Solicitação de Troca", "Outros"]
                    )
                    
                    prioridade_novo = st.selectbox(
                        "⚠️ Prioridade *",
                        ["Baixa", "Média", "Alta", "Urgente"]
                    )
                
                with col_form2:
                    aberto_por = st.text_input(
                        "👨‍💼 Aberto Por",
                        placeholder="Seu nome",
                        value="Sistema CRM"
                    )
                
                descricao_problema_novo = st.text_area(
                    "📝 Descrição Completa do Problema *",
                    height=150,
                    placeholder="Descreva detalhadamente o problema relatado pelo cliente..."
                )
                
                st.markdown("---")
                
                col_btn_form1, col_btn_form2, col_btn_form3 = st.columns(3)
                
                with col_btn_form1:
                    btn_criar_ticket = st.form_submit_button(
                        "✅ Criar Ticket",
                        type="primary",
                        use_container_width=True
                    )
                
                with col_btn_form2:
                    btn_voltar_busca = st.form_submit_button(
                        "🔄 Trocar Cliente",
                        use_container_width=True
                    )
                
                with col_btn_form3:
                    btn_cancelar_form = st.form_submit_button(
                        "❌ Cancelar",
                        use_container_width=True
                    )
                
                # ========== AÇÃO: VOLTAR À BUSCA ==========
                if btn_voltar_busca:
                    st.session_state.cliente_selecionado_ticket = None
                    st.rerun()
                
                # ========== AÇÃO: CANCELAR ==========
                if btn_cancelar_form:
                    st.session_state.mostrar_form_novo = False
                    st.session_state.cliente_selecionado_ticket = None
                    st.rerun()
                
                # ========== AÇÃO: CRIAR TICKET ==========
                if btn_criar_ticket:
                    # Validações
                    if not descricao_problema_novo:
                        st.error("❌ Descreva o problema!")
                    else:
                        with st.spinner("Criando ticket..."):
                            try:
                                conn = get_gsheets_connection()
                                
                                # Extrair dados do cliente selecionado
                                nome_cliente_novo = cliente.get('Nome', 'N/D')
                                telefone_cliente_novo = cliente.get('Telefone', 'N/D')
                                classificacao_novo = cliente.get('Classificação', 'Não classificado')
                                
                                # 1. Gerar ID único
                                id_ticket = gerar_id_ticket()
                                
                                # 2. Adicionar na aba SUPORTE
                                df_suporte = conn.read(worksheet="SUPORTE", ttl=0)
                                
                                novo_ticket_suporte = {
                                    'ID_Ticket': id_ticket,
                                    'Nome': nome_cliente_novo,
                                    'Telefone': telefone_cliente_novo,
                                    'Classificação': classificacao_novo,
                                    'Tipo_Problema': tipo_problema,
                                    'Prioridade': prioridade_novo,
                                    'Descrição do problema': descricao_problema_novo,
                                    'Data de abertura': datetime.now().strftime('%d/%m/%Y %H:%M'),
                                    'Último contato': '',
                                    'Próximo contato': '',
                                    'Progresso': 0,
                                    'Observações': f'Ticket criado via CRM por {aberto_por}'
                                }
                                
                                df_suporte_novo = pd.concat([df_suporte, pd.DataFrame([novo_ticket_suporte])], ignore_index=True)
                                conn.update(worksheet="SUPORTE", data=df_suporte_novo)
                                
                                # 3. Registrar em LOG_TICKETS_ABERTOS
                                dados_log = {
                                    'Nome': nome_cliente_novo,
                                    'Telefone': telefone_cliente_novo,
                                    'Classificacao': classificacao_novo,
                                    'Tipo_Problema': tipo_problema,
                                    'Prioridade': prioridade_novo,
                                    'Descricao': descricao_problema_novo
                                }
                                
                                registrar_ticket_log_aberto(id_ticket, dados_log, aberto_por)
                                
                                # Limpar cache e recarregar
                                carregar_dados.clear()
                                st.success(f"✅ Ticket **{id_ticket}** criado com sucesso!")
                                st.balloons()
                                
                                # Limpar formulário
                                st.session_state.mostrar_form_novo = False
                                st.session_state.cliente_selecionado_ticket = None
                                time.sleep(2)
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Erro ao criar ticket: {e}")
            
            st.markdown("---")
            return  # Retorna para não mostrar a lista enquanto está criando
    
    # ========== REALIZAR BUSCA ==========
    if btn_buscar and termo_busca:
        with st.spinner("Buscando ticket..."):
            try:
                conn = get_gsheets_connection()
                df_suporte = conn.read(worksheet="SUPORTE", ttl=0)
                
                if df_suporte.empty:
                    st.warning("⚠️ Nenhum ticket encontrado no sistema")
                    st.session_state.ticket_encontrado = None
                else:
                    termo_limpo = termo_busca.strip()
                    telefone_limpo = limpar_telefone(termo_limpo)
                    
                    # Buscar por ID do Ticket
                    resultado = None
                    if 'ID_Ticket' in df_suporte.columns:
                        mask_id = df_suporte['ID_Ticket'].astype(str).str.contains(termo_limpo, case=False, na=False)
                        resultado_id = df_suporte[mask_id]
                        if not resultado_id.empty:
                            resultado = resultado_id.iloc[0]
                    
                    # Se não encontrou por ID, buscar por telefone
                    if resultado is None and 'Telefone' in df_suporte.columns:
                        df_suporte['Telefone_Limpo'] = df_suporte['Telefone'].apply(limpar_telefone)
                        mask_tel = df_suporte['Telefone_Limpo'].str.contains(telefone_limpo, case=False, na=False, regex=False)
                        resultado_tel = df_suporte[mask_tel]
                        if not resultado_tel.empty:
                            resultado = resultado_tel.iloc[0]
                    
                    # Se não encontrou, buscar por nome
                    if resultado is None and 'Nome' in df_suporte.columns:
                        mask_nome = df_suporte['Nome'].astype(str).str.contains(termo_limpo, case=False, na=False)
                        resultado_nome = df_suporte[mask_nome]
                        if not resultado_nome.empty:
                            resultado = resultado_nome.iloc[0]
                    
                    if resultado is not None:
                        st.session_state.ticket_encontrado = resultado.to_dict()
                    else:
                        st.warning(f"⚠️ Nenhum ticket encontrado para: {termo_busca}")
                        st.session_state.ticket_encontrado = None
                        
            except Exception as e:
                st.error(f"❌ Erro na busca: {e}")
                st.session_state.ticket_encontrado = None
    
    elif btn_buscar and not termo_busca:
        st.warning("⚠️ Digite um ID, nome ou telefone para buscar")
    
    # ========== EXIBIR TICKET ENCONTRADO (VISÃO DETALHADA) ==========
    if st.session_state.ticket_encontrado is not None:
        ticket = st.session_state.ticket_encontrado
        
        id_ticket = ticket.get('ID_Ticket', 'N/D')
        nome_cliente = ticket.get('Nome', 'N/D')
        prioridade = ticket.get('Prioridade', 'Média')
        
        # Ícone de prioridade
        icones_prioridade = {
            'Urgente': '🔴',
            'Alta': '🟠',
            'Média': '🟡',
            'Baixa': '🟢'
        }
        icone = icones_prioridade.get(prioridade, '⚪')
        
        st.success(f"✅ Ticket encontrado: **{id_ticket}** - {nome_cliente}")
        
        # Botão para voltar à lista
        if st.button("⬅️ Voltar para Lista de Tickets", key="voltar_lista"):
            st.session_state.ticket_encontrado = None
            st.rerun()
        
        st.markdown("---")
        
        # ========== BUSCAR HISTÓRICO COMPLETO DO CLIENTE ==========
        st.subheader(f"📋 Histórico Completo do Ticket {id_ticket}")
        
        try:
            conn = get_gsheets_connection()
            df_suporte_completo = conn.read(worksheet="SUPORTE", ttl=0)
            
            # Buscar TODOS os tickets deste cliente (por nome e telefone)
            telefone_cliente = ticket.get('Telefone', '')
            
            historico_tickets = []
            
            if not df_suporte_completo.empty:
                if 'Telefone' in df_suporte_completo.columns and telefone_cliente:
                    df_suporte_completo['Telefone_Limpo'] = df_suporte_completo['Telefone'].apply(limpar_telefone)
                    telefone_limpo_busca = limpar_telefone(telefone_cliente)
                    
                    historico_tickets = df_suporte_completo[
                        df_suporte_completo['Telefone_Limpo'].str.contains(telefone_limpo_busca, case=False, na=False, regex=False)
                    ].to_dict('records')
                elif 'Nome' in df_suporte_completo.columns:
                    historico_tickets = df_suporte_completo[
                        df_suporte_completo['Nome'].str.contains(nome_cliente, case=False, na=False)
                    ].to_dict('records')
            
            # Exibir resumo
            col_resumo1, col_resumo2, col_resumo3 = st.columns(3)
            
            with col_resumo1:
                st.metric("🎫 Total de Tickets", len(historico_tickets), help="Tickets abertos por este cliente")
            
            with col_resumo2:
                tickets_abertos = len([t for t in historico_tickets if float(t.get('Progresso', 0) or 0) < 100])
                st.metric("⏳ Em Aberto", tickets_abertos)
            
            with col_resumo3:
                tickets_resolvidos = len([t for t in historico_tickets if float(t.get('Progresso', 0) or 0) >= 100])
                st.metric("✅ Resolvidos", tickets_resolvidos)
            
            st.markdown("---")
            
            # ========== CARDS DE HISTÓRICO ==========
            if historico_tickets:
                st.subheader(f"📚 Histórico de Tickets ({len(historico_tickets)})")
                
                # Ordenar por data de abertura (mais recente primeiro)
                historico_tickets_ordenado = sorted(
                    historico_tickets, 
                    key=lambda x: x.get('Data de abertura', ''), 
                    reverse=True
                )
                
                for hist_ticket in historico_tickets_ordenado:
                    id_hist = hist_ticket.get('ID_Ticket', 'N/D')
                    prioridade_hist = hist_ticket.get('Prioridade', 'Média')
                    progresso_hist = hist_ticket.get('Progresso', 0)
                    icone_hist = icones_prioridade.get(prioridade_hist, '⚪')
                    
                    # Badge de status
                    try:
                        prog_valor = float(progresso_hist) if progresso_hist else 0
                    except:
                        prog_valor = 0
                    
                    if prog_valor >= 100:
                        badge_status = "✅ RESOLVIDO"
                    elif prog_valor >= 50:
                        badge_status = "🔄 EM ANDAMENTO"
                    else:
                        badge_status = "🆕 ABERTO"
                    
                    titulo_card_hist = f"{badge_status} | {icone_hist} {id_hist} | {prioridade_hist} | {prog_valor}%"
                    
                    # Expandir automaticamente o ticket atual
                    expandir = (id_hist == id_ticket)
                    
                    with st.expander(titulo_card_hist, expanded=expandir):
                        col_esq_hist, col_dir_hist = st.columns([1, 1])
                        
                        # ========== COLUNA ESQUERDA: INFORMAÇÕES DO TICKET ==========
                        with col_esq_hist:
                            st.markdown("### 📋 Dados do Ticket")
                            
                            st.write(f"**🎫 ID:** {id_hist}")
                            st.write(f"**👤 Nome:** {hist_ticket.get('Nome', 'N/D')}")
                            st.write(f"**📱 Telefone:** {hist_ticket.get('Telefone', 'N/D')}")
                            st.write(f"**🏷️ Classificação:** {hist_ticket.get('Classificação', 'N/D')}")
                            st.write(f"**🔧 Tipo:** {hist_ticket.get('Tipo_Problema', 'N/D')}")
                            st.write(f"**{icone_hist} Prioridade:** {prioridade_hist}")
                            
                            st.markdown("---")
                            
                            # Barra de progresso - CORRIGIDO
                            st.markdown("### 📊 Progresso")
                            
                            try:
                                progresso_valor = float(progresso_hist) if progresso_hist else 0
                                progresso_decimal = max(0.0, min(1.0, progresso_valor / 100))
                            except:
                                progresso_decimal = 0.0
                            
                            st.progress(progresso_decimal)
                            st.write(f"**{prog_valor}% concluído**")
                            
                            # Labels de progresso
                            if prog_valor == 0:
                                st.info("🆕 Ticket aberto - Aguardando primeiro contato")
                            elif prog_valor == 25:
                                st.info("📞 Primeiro contato realizado")
                            elif prog_valor == 50:
                                st.warning("🔄 Em andamento - Acompanhamento ativo")
                            elif prog_valor == 75:
                                st.success("✨ Quase concluído - Finalizando")
                            elif prog_valor >= 100:
                                st.success("✅ Pronto para finalizar")
                            
                            st.markdown("---")
                            
                            # Descrição do problema
                            st.markdown("### 🔍 Descrição do Problema")
                            
                            descricao_hist_raw = hist_ticket.get('Descrição do problema', '')
                            descricao_hist = str(descricao_hist_raw) if descricao_hist_raw else ''
                            if descricao_hist and descricao_hist.strip():
                                st.error(f"**Problema relatado:**\n\n{descricao_hist}")
                            else:
                                st.caption("_Sem descrição registrada_")
                            
                            st.markdown("---")
                            
                            # Histórico de acompanhamento
                            st.markdown("### 📝 Histórico")
                            
                            data_abertura_hist = hist_ticket.get('Data de abertura', 'N/D')
                            st.write(f"**📅 Aberto em:** {data_abertura_hist}")
                            
                            ultimo_contato_hist = str(hist_ticket.get('Último contato', '')) if hist_ticket.get('Último contato') else ''
                            if ultimo_contato_hist and ultimo_contato_hist.strip():
                                st.info(f"**Último acompanhamento:**\n\n{ultimo_contato_hist}")
                            else:
                                st.caption("_Nenhum acompanhamento registrado ainda_")
                            
                            proximo_contato_hist = str(hist_ticket.get('Próximo contato', '')) if hist_ticket.get('Próximo contato') else ''
                            if proximo_contato_hist and proximo_contato_hist.strip():
                                hoje_str = datetime.now().strftime('%d/%m/%Y')
                                if proximo_contato_hist == hoje_str:
                                    st.success(f"**📅 Próximo contato:** {proximo_contato_hist} ✅ HOJE")
                                else:
                                    st.info(f"**📅 Próximo contato:** {proximo_contato_hist}")
                            
                            obs_hist = str(hist_ticket.get('Observações', '')) if hist_ticket.get('Observações') else ''
                            if obs_hist and obs_hist.strip():
                                st.info(f"**💬 Observações:** {obs_hist}")
                        
                        # ========== COLUNA DIREITA: ATUALIZAR TICKET (APENAS SE FOR O ATUAL) ==========
                        with col_dir_hist:
                            if id_hist == id_ticket:
                                st.markdown("### ✏️ Registrar Acompanhamento")
                                
                                # Obter índice real do DataFrame
                                df_suporte_atual = conn.read(worksheet="SUPORTE", ttl=0)
                                idx_real = df_suporte_atual[df_suporte_atual['ID_Ticket'] == id_ticket].index[0]
                                
                                with st.form(key=f"form_atualizar_{id_ticket}"):
                                    
                                    st.info("💡 Registre o acompanhamento e atualize o status")
                                    
                                    novo_acompanhamento = st.text_area(
                                        "📝 Como foi o contato de hoje?",
                                        height=120,
                                        placeholder="Descreva o que foi conversado...",
                                        help="Registre o acompanhamento realizado"
                                    )
                                    
                                    nova_data_contato = st.date_input(
                                        "📅 Próximo Contato:",
                                        value=None,
                                        help="Quando será o próximo acompanhamento?"
                                    )
                                    
                                    novo_progresso = st.selectbox(
                                        "📊 Atualizar Progresso:",
                                        [0, 25, 50, 75, 100],
                                        index=[0, 25, 50, 75, 100].index(int(prog_valor)) if int(prog_valor) in [0, 25, 50, 75, 100] else 0,
                                        help="Atualize o percentual de conclusão"
                                    )
                                    
                                    st.caption("""
                                    **Níveis de progresso:**
                                    - 0% = Ticket aberto
                                    - 25% = Primeiro contato
                                    - 50% = Em andamento
                                    - 75% = Quase concluído
                                    - 100% = Pronto para finalizar
                                    """)
                                    
                                    novas_obs = st.text_area(
                                        "💬 Observações:",
                                        height=60,
                                        placeholder="Informações extras..."
                                    )
                                    
                                    st.markdown("---")
                                    
                                    col_btn1, col_btn2 = st.columns(2)
                                    
                                    with col_btn1:
                                        btn_atualizar = st.form_submit_button(
                                            "✅ Atualizar",
                                            type="primary",
                                            use_container_width=True
                                        )
                                    
                                    with col_btn2:
                                        btn_finalizar = st.form_submit_button(
                                            "🎉 Finalizar",
                                            type="secondary",
                                            use_container_width=True
                                        )
                                    
                                    # ========== AÇÃO: ATUALIZAR ==========
                                    if btn_atualizar:
                                        if not novo_acompanhamento:
                                            st.error("❌ Preencha como foi o contato!")
                                        elif not nova_data_contato:
                                            st.error("❌ Selecione a data do próximo contato!")
                                        else:
                                            with st.spinner("Atualizando..."):
                                                try:
                                                    df_suporte_atual = conn.read(worksheet="SUPORTE", ttl=0)
                                                    
                                                    df_suporte_atual.at[idx_real, 'Último contato'] = novo_acompanhamento
                                                    df_suporte_atual.at[idx_real, 'Próximo contato'] = nova_data_contato.strftime('%d/%m/%Y')
                                                    df_suporte_atual.at[idx_real, 'Progresso'] = novo_progresso
                                                    if novas_obs:
                                                        df_suporte_atual.at[idx_real, 'Observações'] = novas_obs
                                                    
                                                    conn.update(worksheet="SUPORTE", data=df_suporte_atual)
                                                    carregar_dados.clear()
                                                    
                                                    st.success(f"✅ Ticket atualizado! Progresso: {novo_progresso}%")
                                                    time.sleep(1)
                                                    st.rerun()
                                                    
                                                except Exception as e:
                                                    st.error(f"❌ Erro: {e}")
                                    
                                    # ========== AÇÃO: FINALIZAR ==========
                                    if btn_finalizar:
                                        if novo_progresso < 100:
                                            st.warning("⚠️ Recomendamos marcar como 100% antes de finalizar")
                                        
                                        st.session_state[f'finalizar_{id_ticket}'] = True
                                
                                # Campos de finalização fora do form
                                if st.session_state.get(f'finalizar_{id_ticket}', False):
                                    st.markdown("---")
                                    st.markdown("### 📝 Informações de Finalização")
                                    
                                    with st.form(key=f"form_finalizar_{id_ticket}"):
                                        solucao_final = st.text_area(
                                            "Como foi resolvido? *",
                                            height=100,
                                            placeholder="Descreva a solução aplicada..."
                                        )
                                        
                                        resultado_final = st.selectbox(
                                            "Resultado Final *",
                                            ["Problema Resolvido", "Cliente Satisfeito", 
                                             "Reembolso Concedido", "Troca Realizada", 
                                             "Não Resolvido", "Cliente Insatisfeito"]
                                        )
                                        
                                        gerou_conversao = st.radio(
                                            "Gerou nova venda?",
                                            ["Não", "Sim"],
                                            horizontal=True
                                        )
                                        
                                        resolvido_por = st.text_input(
                                            "Resolvido por",
                                            value="Sistema CRM"
                                        )
                                        
                                        col_fin1, col_fin2 = st.columns(2)
                                        
                                        with col_fin1:
                                            btn_confirmar_fin = st.form_submit_button(
                                                "✅ Confirmar",
                                                type="primary",
                                                use_container_width=True
                                            )
                                        
                                        with col_fin2:
                                            btn_cancelar_fin = st.form_submit_button(
                                                "❌ Cancelar",
                                                use_container_width=True
                                            )
                                        
                                        if btn_cancelar_fin:
                                            del st.session_state[f'finalizar_{id_ticket}']
                                            st.rerun()
                                        
                                        if btn_confirmar_fin:
                                            if not solucao_final:
                                                st.error("❌ Descreva como foi resolvido!")
                                            else:
                                                with st.spinner("Finalizando..."):
                                                    try:
                                                        # 1. Registrar em LOG_TICKETS_RESOLVIDOS
                                                        dados_resolucao = {
                                                            'Solucao': solucao_final,
                                                            'Resultado': resultado_final,
                                                            'Conversao': gerou_conversao
                                                        }
                                                        
                                                        registrar_ticket_log_resolvido(id_ticket, dados_resolucao, resolvido_por)
                                                        
                                                        # 2. Mover para AGENDAMENTOS_ATIVOS
                                                        df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
                                                        
                                                        # Buscar próximo contato do form de atualização
                                                        prox_contato = nova_data_contato.strftime('%d/%m/%Y') if nova_data_contato else ''
                                                        
                                                        novo_agendamento = {
                                                            'Data de contato': datetime.now().strftime('%d/%m/%Y'),
                                                            'Nome': ticket.get('Nome', ''),
                                                            'Classificação': ticket.get('Classificação', ''),
                                                            'Valor': '',
                                                            'Telefone': ticket.get('Telefone', ''),
                                                            'Relato da conversa': f"[SUPORTE {id_ticket} CONCLUÍDO] {solucao_final}",
                                                            'Follow up': 'Acompanhamento pós-suporte',
                                                            'Data de chamada': prox_contato,
                                                            'Observação': f"Ticket resolvido. Resultado: {resultado_final}"
                                                        }
                                                        
                                                        df_agendamentos_novo = pd.concat([df_agendamentos, pd.DataFrame([novo_agendamento])], ignore_index=True)
                                                        conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_agendamentos_novo)
                                                        
                                                        # 3. Remover de SUPORTE
                                                        df_suporte_final = conn.read(worksheet="SUPORTE", ttl=0)
                                                        df_suporte_novo = df_suporte_final.drop(idx_real).reset_index(drop=True)
                                                        conn.update(worksheet="SUPORTE", data=df_suporte_novo)
                                                        
                                                        carregar_dados.clear()
                                                        st.success(f"🎉 Ticket {id_ticket} finalizado! Cliente movido para Agendamentos Ativos")
                                                        st.balloons()
                                                        
                                                        # Limpar busca
                                                        st.session_state.ticket_encontrado = None
                                                        del st.session_state[f'finalizar_{id_ticket}']
                                                        time.sleep(2)
                                                        st.rerun()
                                                        
                                                    except Exception as e:
                                                        st.error(f"❌ Erro ao finalizar: {e}")
                            else:
                                st.info("ℹ️ Este é um ticket histórico. Selecione o ticket atual para atualizar.")
                        
                        st.markdown("---")
            
            else:
                st.info("ℹ️ Nenhum histórico encontrado para este cliente")
                
        except Exception as e:
            st.error(f"❌ Erro ao carregar histórico: {e}")
        
        return  # Retorna para não mostrar a lista quando está em modo busca
    
    # ========== VISÃO GERAL - LISTA DE TICKETS ==========
    st.subheader("📊 Gestão de Tickets de Suporte")
    
    # Carregar dados
    with st.spinner("Carregando tickets de suporte..."):
        df_suporte = carregar_dados("SUPORTE")
    
    if df_suporte.empty:
        st.info("✅ Nenhum ticket de suporte ativo no momento")
        st.write("👉 Use o botão **➕ Novo Ticket** acima para abrir um chamado")
        return
    
    # ========== FILTRAR TICKETS DO DIA E VENCIDOS ==========
    hoje_dt = datetime.now()
    hoje_str_br = hoje_dt.strftime('%d/%m/%Y')
    
    df_hoje = pd.DataFrame()
    df_vencidos = pd.DataFrame()
    
    if 'Próximo contato' in df_suporte.columns:
        # Tickets de hoje
        df_hoje = df_suporte[df_suporte['Próximo contato'] == hoje_str_br].copy()
        
        # Tickets vencidos
        vencidos_lista = []
        for idx, row in df_suporte.iterrows():
            data_contato_str = row.get('Próximo contato', '')
            if data_contato_str and data_contato_str != '':
                try:
                    # Tentar formato brasileiro DD/MM/YYYY
                    data_contato_dt = datetime.strptime(data_contato_str, '%d/%m/%Y')
                    if data_contato_dt.date() < hoje_dt.date():
                        vencidos_lista.append(idx)
                except:
                    pass
        
        if vencidos_lista:
            df_vencidos = df_suporte.loc[vencidos_lista].copy()
    
    # ========== DASHBOARD DE MÉTRICAS ==========
    st.subheader("📊 Resumo de Suporte")
    
    # Contar por prioridade
    prioridades = {'Urgente': 0, 'Alta': 0, 'Média': 0, 'Baixa': 0}
    
    if 'Prioridade' in df_suporte.columns:
        for p in prioridades.keys():
            prioridades[p] = len(df_suporte[df_suporte['Prioridade'] == p])
    
    # Métricas
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    
    with col_m1:
        st.metric("📋 Total de Tickets", len(df_suporte))
    
    with col_m2:
        st.metric("📅 Hoje", len(df_hoje), help="Tickets agendados para hoje")
    
    with col_m3:
        st.metric("🔥 Vencidos", len(df_vencidos),
                  delta=f"-{len(df_vencidos)}" if len(df_vencidos) > 0 else "0",
                  delta_color="inverse",
                  help="Tickets com data de contato vencida")
    
    with col_m4:
        st.metric("🔴 Urgente", prioridades['Urgente'], 
                  delta=f"-{prioridades['Urgente']}" if prioridades['Urgente'] > 0 else "0",
                  delta_color="inverse")
    
    with col_m5:
        total_criticos = prioridades['Urgente'] + prioridades['Alta']
        st.metric("⚠️ Críticos", total_criticos,
                  delta=f"-{total_criticos}" if total_criticos > 0 else "0",
                  delta_color="inverse")
    
    # Alertas
    if prioridades['Urgente'] > 0:
        st.error(f"🚨 **ATENÇÃO:** Você tem {prioridades['Urgente']} ticket(s) URGENTE(S)! Priorize-os imediatamente.")
    
    if len(df_vencidos) > 0:
        st.warning(f"⚠️ **ATENÇÃO:** Você tem {len(df_vencidos)} ticket(s) VENCIDO(S) de dias anteriores!")
    
    st.markdown("---")
    
    # ========== FILTROS ==========
    st.subheader("🔍 Filtros")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        visualizar = st.selectbox(
            "Visualizar:",
            ["Todos", "Hoje", "Vencidos"],
            help="Escolha quais tickets deseja ver"
        )
    
    with col_f2:
        busca_lista = st.text_input(
            "Buscar na lista:",
            "",
            placeholder="Digite o nome...",
            key="busca_lista_suporte"
        )
    
    with col_f3:
        filtro_prioridade = st.selectbox(
            "Prioridade:",
            ["Todas", "Urgente", "Alta", "Média", "Baixa"]
        )
    
    # Selecionar dataset
    if visualizar == "Hoje":
        df_trabalho = df_hoje.copy()
    elif visualizar == "Vencidos":
        df_trabalho = df_vencidos.copy()
    else:
        df_trabalho = df_suporte.copy()
    
    # Aplicar filtros
    df_filt = df_trabalho.copy()
    
    if busca_lista and 'Nome' in df_filt.columns:
        df_filt = df_filt[df_filt['Nome'].str.contains(busca_lista, case=False, na=False)]
    
    if filtro_prioridade != 'Todas' and 'Prioridade' in df_filt.columns:
        df_filt = df_filt[df_filt['Prioridade'] == filtro_prioridade]
    
    st.markdown("---")
    
    # ========== LISTA DE TICKETS ==========
    st.subheader(f"🎫 Tickets de Suporte ({len(df_filt)})")
    
    if df_filt.empty:
        if visualizar == "Hoje":
            st.info("✅ Nenhum ticket agendado para hoje!")
        elif visualizar == "Vencidos":
            st.success("✅ Você não tem tickets vencidos! Parabéns!")
        else:
            st.info("Nenhum ticket encontrado com os filtros aplicados")
        return
    
    # Ordenar por prioridade (Urgente > Alta > Média > Baixa)
    ordem_prioridade = {'Urgente': 0, 'Alta': 1, 'Média': 2, 'Baixa': 3}
    if 'Prioridade' in df_filt.columns:
        df_filt['_ordem'] = df_filt['Prioridade'].map(ordem_prioridade).fillna(4)
        df_filt = df_filt.sort_values('_ordem')
    
    # Ícones de prioridade
    icones_prioridade = {
        'Urgente': '🔴',
        'Alta': '🟠',
        'Média': '🟡',
        'Baixa': '🟢'
    }
    
    # Cards de tickets (versão resumida para lista)
    for idx, ticket in df_filt.iterrows():
        
        # Dados do ticket
        id_ticket = str(ticket.get('ID_Ticket', 'N/D')) if ticket.get('ID_Ticket') else 'N/D'
        nome_cliente = str(ticket.get('Nome', 'N/D')) if ticket.get('Nome') else 'N/D'
        prioridade = str(ticket.get('Prioridade', 'Média')) if ticket.get('Prioridade') else 'Média'
        progresso = ticket.get('Progresso', 0)
        
        # Converter progresso corretamente - CORRIGIDO
        try:
            progresso_valor = float(progresso) if progresso else 0
        except:
            progresso_valor = 0
        
        icone = icones_prioridade.get(prioridade, '⚪')
        
        # Verificar se está vencido
        esta_vencido = False
        proximo_contato_str = str(ticket.get('Próximo contato', '')) if ticket.get('Próximo contato') else ''
        if proximo_contato_str and proximo_contato_str.strip():
            try:
                data_contato_dt = datetime.strptime(proximo_contato_str, '%d/%m/%Y')
                if data_contato_dt.date() < hoje_dt.date():
                    esta_vencido = True
            except:
                pass
        
        # Badge de status
        if esta_vencido:
            badge = "🔥 VENCIDO"
        elif proximo_contato_str == hoje_str_br:
            badge = "📅 HOJE"
        else:
            badge = "📋 ATIVO"
        
        # Título do card
        titulo_card = f"{badge} | {icone} {prioridade.upper()} | 🎫 {id_ticket} | 👤 {nome_cliente} | 📊 {progresso_valor}%"
        
        # Expandir automaticamente tickets urgentes ou vencidos
        expandir = (prioridade == 'Urgente' or esta_vencido)
        
        with st.expander(titulo_card, expanded=expandir):
            
            col_info, col_acoes = st.columns([2, 1])
            
            with col_info:
                st.write(f"**🎫 ID do Ticket:** {id_ticket}")
                st.write(f"**👤 Cliente:** {nome_cliente}")
                
                telefone_ticket = str(ticket.get('Telefone', 'N/D')) if ticket.get('Telefone') else 'N/D'
                st.write(f"**📱 Telefone:** {telefone_ticket}")
                
                tipo_problema_ticket = str(ticket.get('Tipo_Problema', 'N/D')) if ticket.get('Tipo_Problema') else 'N/D'
                st.write(f"**🔧 Tipo:** {tipo_problema_ticket}")
                
                st.write(f"**{icone} Prioridade:** {prioridade}")
                
                # Progresso - CORRIGIDO
                try:
                    progresso_decimal = max(0.0, min(1.0, progresso_valor / 100))
                except:
                    progresso_decimal = 0.0
                
                st.progress(progresso_decimal)
                st.caption(f"{progresso_valor}% concluído")
                
                # Descrição resumida
                descricao_raw = ticket.get('Descrição do problema', '')
                descricao = str(descricao_raw) if descricao_raw else ''
                if descricao and descricao.strip():
                    st.info(f"**Problema:** {descricao[:150]}{'...' if len(descricao) > 150 else ''}")
                
                # Datas
                data_abertura = str(ticket.get('Data de abertura', 'N/D')) if ticket.get('Data de abertura') else 'N/D'
                st.write(f"**📅 Aberto em:** {data_abertura}")
                
                if proximo_contato_str and proximo_contato_str.strip():
                    if esta_vencido:
                        st.error(f"**⚠️ Próximo contato:** {proximo_contato_str} (VENCIDO)")
                    elif proximo_contato_str == hoje_str_br:
                        st.success(f"**📅 Próximo contato:** {proximo_contato_str} (HOJE)")
                    else:
                        st.info(f"**📅 Próximo contato:** {proximo_contato_str}")
            
            with col_acoes:
                st.markdown("### 🎯 Ações")
                
                # Botão para ver detalhes completos
                if st.button(f"📋 Ver Detalhes", key=f"ver_detalhes_{idx}_{id_ticket}", use_container_width=True):
                    st.session_state.ticket_encontrado = ticket.to_dict()
                    st.rerun()
                
                st.caption(f"Clique para ver o histórico completo e atualizar o ticket")
        
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
