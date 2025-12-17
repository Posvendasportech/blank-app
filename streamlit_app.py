
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
import pytz

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

def registrar_log_checkin(dados_cliente, classificacao, respondeu, relato_resumo, criado_por="Sistema"):
    """Registra cada check-in realizado na aba LOG_CHECKINS com ID único - Horário de Brasília"""
    try:
        conn = get_gsheets_connection()
        df_log = conn.read(worksheet="LOG_CHECKINS", ttl=0)
        
        # HORÁRIO DE BRASÍLIA para pegar o ano
        timezone_brasilia = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(timezone_brasilia)
        ano_atual = agora.strftime('%Y')  # 2025, 2026, etc.
        
        # Gerar ID único no formato CHK-AAAA-NNNNN
        if df_log.empty or 'ID_Checkin' not in df_log.columns:
            numero_sequencial = 1
        else:
            # Filtrar IDs do ano atual
            ids_ano_atual = df_log[df_log['ID_Checkin'].str.contains(f'CHK-{ano_atual}-', na=False)]
            
            if len(ids_ano_atual) > 0:
                # Extrair números dos IDs (CHK-2025-00001 -> 1)
                ultimos_numeros = ids_ano_atual['ID_Checkin'].str.extract(r'CHK-\d{4}-(\d{5})')[0]
                ultimo_numero = ultimos_numeros.astype(int).max()
                numero_sequencial = ultimo_numero + 1
            else:
                numero_sequencial = 1
        
        # Formatar ID: CHK-2025-00001
        proximo_id = f"CHK-{ano_atual}-{numero_sequencial:05d}"

            else:
            # Pegar o maior ID existente e adicionar 1
            ids_existentes = df_log['ID_Checkin'].dropna()
            if len(ids_existentes) > 0:
                proximo_id = int(ids_existentes.max()) + 1
            else:
                proximo_id = 1
        
        # ========== HORÁRIO DE BRASÍLIA (UTC-3) ==========
        timezone_brasilia = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(timezone_brasilia)
        
        data_checkin = agora.strftime('%d/%m/%Y')
        hora_checkin = agora.strftime('%H:%M:%S')
        dia_semana = agora.strftime('%A')
        
        # Traduzir dia da semana para português
        dias_pt = {
            'Monday': 'Segunda-feira',
            'Tuesday': 'Terça-feira',
            'Wednesday': 'Quarta-feira',
            'Thursday': 'Quinta-feira',
            'Friday': 'Sexta-feira',
            'Saturday': 'Sábado',
            'Sunday': 'Domingo'
        }
        dia_semana = dias_pt.get(dia_semana, dia_semana)
        
        # Preparar linha de log
        nova_linha_log = {
            'ID_Checkin': proximo_id,
            'Data_Checkin': data_checkin,
            'Nome_Cliente': dados_cliente.get('Nome', ''),
            'Telefone': dados_cliente.get('Telefone', ''),
            'Classificacao_Cliente': classificacao,
            'Valor_Cliente_Antes': dados_cliente.get('Valor', 0),
            'Compras_Cliente_Antes': dados_cliente.get('Compras', 0),
            'Respondeu': respondeu,
            'Relato_Resumo': relato_resumo[:200] if relato_resumo else '',
            'Criado_Por': criado_por,
            'Dia_Semana': dia_semana,
            'Hora_Checkin': hora_checkin
        }
        
        # Adicionar ao log
        df_log_novo = pd.concat([df_log, pd.DataFrame([nova_linha_log])], ignore_index=True)
        conn.update(worksheet="LOG_CHECKINS", data=df_log_novo)
        
        return proximo_id
        
    except Exception as e:
        st.error(f"Erro ao registrar log: {e}")
        return None


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
                                        # ========== BOTÃO DE CHECK-IN RÁPIDO SEM RESPOSTA ==========
                st.markdown("### 📞 Status de Contato")
                
                col_btn_checkin = st.columns(1)
                
                                if st.button(
                    "❌ Cliente Não Respondeu (Check-in Rápido)", 
                    key=f"nao_resp_{index}",
                    use_container_width=True,
                    type="secondary",
                    help="Registra tentativa de contato sem resposta"
                ):
                    with st.spinner('Registrando tentativa sem resposta...'):
                        try:
                            # APENAS REGISTRAR NO LOG - NÃO ADICIONA EM AGENDAMENTOS
                            id_checkin = registrar_log_checkin(
                                dados_cliente=cliente,
                                classificacao=classificacao_selecionada,
                                respondeu="NÃO RESPONDEU",
                                relato_resumo="Cliente não respondeu ao contato",
                                criado_por="CRM"
                            )
                            
                            carregar_dados.clear()
                            st.warning(f"⏳ Tentativa #{id_checkin} registrada - Cliente não respondeu")
                            st.info("💡 Este cliente permanece disponível para nova tentativa de contato")
                            time.sleep(2)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Erro ao registrar: {e}")
                
                st.caption("💡 Use este botão para registrar rapidamente tentativas sem resposta")
            
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
                                    
                                    # REGISTRAR NO LOG
                                    id_checkin = registrar_log_checkin(
                                        dados_cliente=cliente,
                                        classificacao=classificacao_selecionada,
                                        respondeu="NÃO RESPONDEU",
                                        relato_resumo=primeira_conversa,
                                        criado_por="CRM"
                                    )
                                    
                                    carregar_dados.clear()
                                    st.success(f"✅ Check-in #{id_checkin} realizado com sucesso para **{nome_cliente}**!")
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
# RENDER - PÁGINA SUPORTE
# ============================================================================

def render_suporte():
    """Renderiza a página de Suporte - Gestão de Tickets"""
    
    st.title("🆘 Suporte ao Cliente")
    st.markdown("Gerencie tickets de suporte com acompanhamento personalizado")
    st.markdown("---")
    
    # Carregar dados
    with st.spinner("Carregando tickets de suporte..."):
        df_suporte = carregar_dados("SUPORTE")
    
    if df_suporte.empty:
        st.info("✅ Nenhum ticket de suporte ativo no momento")
        st.write("👉 Tickets são criados automaticamente na página **Histórico** quando necessário")
        return
    
    # ========== FILTRAR TICKETS DO DIA ==========
    hoje_dt = datetime.now()
    hoje_str_br = hoje_dt.strftime('%d/%m/%Y')
    
    df_hoje = pd.DataFrame()
    if 'Próximo contato' in df_suporte.columns:
        df_hoje = df_suporte[df_suporte['Próximo contato'] == hoje_str_br].copy()
    
    # ========== DASHBOARD DE MÉTRICAS ==========
    st.subheader("📊 Resumo de Suporte")
    
    # Contar por prioridade
    prioridades = {
        'Urgente': 0,
        'Alta': 0,
        'Média': 0,
        'Baixa': 0
    }
    
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
        st.metric("🔴 Urgente", prioridades['Urgente'], 
                  delta=f"-{prioridades['Urgente']}" if prioridades['Urgente'] > 0 else "0",
                  delta_color="inverse")
    
    with col_m4:
        st.metric("🟠 Alta", prioridades['Alta'])
    
    with col_m5:
        total_criticos = prioridades['Urgente'] + prioridades['Alta']
        st.metric("⚠️ Críticos", total_criticos,
                  delta=f"-{total_criticos}" if total_criticos > 0 else "0",
                  delta_color="inverse")
    
    # Alerta de urgentes
    if prioridades['Urgente'] > 0:
        st.error(f"🚨 **ATENÇÃO:** Você tem {prioridades['Urgente']} ticket(s) URGENTE(S)! Priorize-os imediatamente.")
    
    st.markdown("---")
    
    # ========== FILTROS ==========
    st.subheader("🔍 Filtros")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        visualizar = st.selectbox(
            "Visualizar:",
            ["Hoje", "Todos"],
            help="Escolha quais tickets deseja ver"
        )
    
    with col_f2:
        busca = st.text_input(
            "Buscar cliente:",
            "",
            placeholder="Digite o nome...",
            key="busca_suporte"
        )
    
    with col_f3:
        filtro_prioridade = st.selectbox(
            "Prioridade:",
            ["Todas", "Urgente", "Alta", "Média", "Baixa"]
        )
    
    # Selecionar dataset
    if visualizar == "Hoje":
        df_trabalho = df_hoje.copy()
    else:
        df_trabalho = df_suporte.copy()
    
    # Aplicar filtros
    df_filt = df_trabalho.copy()
    
    if busca and 'Nome' in df_filt.columns:
        df_filt = df_filt[df_filt['Nome'].str.contains(busca, case=False, na=False)]
    
    if filtro_prioridade != 'Todas' and 'Prioridade' in df_filt.columns:
        df_filt = df_filt[df_filt['Prioridade'] == filtro_prioridade]
    
    st.markdown("---")
    
    # ========== LISTA DE TICKETS ==========
    st.subheader(f"🎫 Tickets de Suporte ({len(df_filt)})")
    
    if df_filt.empty:
        if visualizar == "Hoje":
            st.info("✅ Nenhum ticket agendado para hoje!")
        else:
            st.info("Nenhum ticket encontrado com os filtros aplicados")
        return
    
    # Ordenar por prioridade (Urgente > Alta > Média > Baixa)
    ordem_prioridade = {'Urgente': 0, 'Alta': 1, 'Média': 2, 'Baixa': 3}
    if 'Prioridade' in df_filt.columns:
        df_filt['_ordem'] = df_filt['Prioridade'].map(ordem_prioridade).fillna(4)
        df_filt = df_filt.sort_values('_ordem')
    
    # Cards de tickets
    for idx, ticket in df_filt.iterrows():
        
        # Dados do ticket
        nome_cliente = ticket.get('Nome', 'N/D')
        prioridade = ticket.get('Prioridade', 'Média')
        progresso = ticket.get('Progresso', 0)
        
        # Ícones de prioridade
        icones_prioridade = {
            'Urgente': '🔴',
            'Alta': '🟠',
            'Média': '🟡',
            'Baixa': '🟢'
        }
        
        icone = icones_prioridade.get(prioridade, '⚪')
        
        # Título do card
        titulo_card = f"{icone} {prioridade.upper()} | 👤 {nome_cliente} | 📊 {progresso}% concluído"
        
        with st.expander(titulo_card, expanded=(prioridade in ['Urgente', 'Alta'])):
            col_esq, col_dir = st.columns([1, 1])
            
            # ========== COLUNA ESQUERDA: INFORMAÇÕES ==========
            with col_esq:
                st.markdown("### 📋 Dados do Ticket")
                
                # Informações básicas
                st.write(f"**👤 Nome:** {nome_cliente}")
                st.write(f"**📱 Telefone:** {ticket.get('Telefone', 'N/D')}")
                st.write(f"**🏷️ Classificação:** {ticket.get('Classificação', 'N/D')}")
                st.write(f"**{icone} Prioridade:** {prioridade}")
                
                st.markdown("---")
                
                # Barra de progresso
                st.markdown("### 📊 Progresso do Atendimento")
                
                # Converter progresso para decimal
                try:
                    progresso_decimal = float(progresso) / 100
                except:
                    progresso_decimal = 0
                
                st.progress(progresso_decimal)
                st.write(f"**{progresso}% concluído**")
                
                # Labels de progresso
                if progresso == 0:
                    st.info("🆕 Ticket aberto - Aguardando primeiro contato")
                elif progresso == 25:
                    st.info("📞 Primeiro contato realizado")
                elif progresso == 50:
                    st.warning("🔄 Em andamento - Acompanhamento ativo")
                elif progresso == 75:
                    st.success("✨ Quase concluído - Finalizando")
                elif progresso >= 100:
                    st.success("✅ Pronto para finalizar")
                
                st.markdown("---")
                
                # Informações do problema
                st.markdown("### 🔍 Descrição do Problema")
                
                descricao = ticket.get('Descrição do problema', '')
                if descricao and descricao != '':
                    st.error(f"**Problema relatado:**\n\n{descricao}")
                else:
                    st.caption("_Sem descrição registrada_")
                
                st.markdown("---")
                
                # Histórico
                st.markdown("### 📝 Histórico de Acompanhamento")
                
                data_abertura = ticket.get('Data de abertura', 'N/D')
                st.write(f"**📅 Aberto em:** {data_abertura}")
                
                ultimo_contato = ticket.get('Último contato', '')
                if ultimo_contato and ultimo_contato != '':
                    st.info(f"**Último acompanhamento:**\n\n{ultimo_contato}")
                else:
                    st.caption("_Nenhum acompanhamento registrado ainda_")
                
                proximo_contato_data = ticket.get('Próximo contato', '')
                if proximo_contato_data and proximo_contato_data != '':
                    # Verificar se é hoje
                    if proximo_contato_data == hoje_str_br:
                        st.success(f"**📅 Próximo contato:** {proximo_contato_data} ✅ HOJE")
                    else:
                        st.info(f"**📅 Próximo contato:** {proximo_contato_data}")
                
                obs = ticket.get('Observações', '')
                if obs and obs != '':
                    st.info(f"**💬 Observações:** {obs}")
            
            # ========== COLUNA DIREITA: NOVO ACOMPANHAMENTO ==========
            with col_dir:
                st.markdown("### ✏️ Registrar Acompanhamento")
                
                with st.form(key=f"form_suporte_{idx}"):
                    
                    st.info("💡 Registre o acompanhamento e atualize o status do ticket")
                    
                    # Campo: Relato do acompanhamento
                    novo_acompanhamento = st.text_area(
                        "📝 Como foi o contato de hoje?",
                        height=120,
                        placeholder="Descreva o que foi conversado e as ações tomadas...",
                        help="Registre o acompanhamento realizado"
                    )
                    
                    # Campo: Próxima data
                    nova_data_contato = st.date_input(
                        "📅 Próximo Contato:",
                        value=None,
                        help="Quando será o próximo acompanhamento?"
                    )
                    
                    # Campo: Atualizar progresso
                    novo_progresso = st.selectbox(
                        "📊 Atualizar Progresso:",
                        [0, 25, 50, 75, 100],
                        index=[0, 25, 50, 75, 100].index(progresso) if progresso in [0, 25, 50, 75, 100] else 0,
                        help="Atualize o percentual de conclusão do ticket"
                    )
                    
                    # Explicação dos níveis
                    st.caption("""
                    **Níveis de progresso:**
                    - 0% = Ticket aberto
                    - 25% = Primeiro contato
                    - 50% = Em andamento
                    - 75% = Quase concluído
                    - 100% = Pronto para finalizar
                    """)
                    
                    # Campo: Observações
                    novas_obs = st.text_area(
                        "💬 Observações Adicionais:",
                        height=60,
                        placeholder="Informações extras relevantes..."
                    )
                    
                    st.markdown("---")
                    
                    # Botões
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        btn_atualizar = st.form_submit_button(
                            "✅ Atualizar Ticket",
                            type="primary",
                            use_container_width=True
                        )
                    
                    with col_btn2:
                        btn_finalizar = st.form_submit_button(
                            "🎉 Finalizar Suporte",
                            type="secondary",
                            use_container_width=True,
                            help="Move para Agendamentos Ativos"
                        )
                    
                    # ========== AÇÃO: ATUALIZAR TICKET ==========
                    if btn_atualizar:
                        if not novo_acompanhamento:
                            st.error("❌ Preencha como foi o contato de hoje!")
                        elif not nova_data_contato:
                            st.error("❌ Selecione a data do próximo contato!")
                        else:
                            with st.spinner("Atualizando ticket..."):
                                try:
                                    conn = get_gsheets_connection()
                                    df_suporte_atual = conn.read(worksheet="SUPORTE", ttl=0)
                                    
                                    # Atualizar campos
                                    df_suporte_atual.at[idx, 'Último contato'] = novo_acompanhamento
                                    df_suporte_atual.at[idx, 'Próximo contato'] = nova_data_contato.strftime('%d/%m/%Y')
                                    df_suporte_atual.at[idx, 'Progresso'] = novo_progresso
                                    if novas_obs:
                                        df_suporte_atual.at[idx, 'Observações'] = novas_obs
                                    
                                    # Salvar
                                    conn.update(worksheet="SUPORTE", data=df_suporte_atual)
                                    
                                    carregar_dados.clear()
                                    st.success(f"✅ Ticket atualizado! Progresso: {novo_progresso}%")
                                    time.sleep(1)
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Erro ao atualizar: {e}")
                    
                    # ========== AÇÃO: FINALIZAR SUPORTE ==========
                    if btn_finalizar:
                        if novo_progresso < 100:
                            st.warning("⚠️ Recomendamos marcar o progresso como 100% antes de finalizar")
                        
                        with st.spinner("Finalizando suporte..."):
                            try:
                                conn = get_gsheets_connection()
                                
                                # 1. Mover para AGENDAMENTOS_ATIVOS
                                df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
                                
                                novo_agendamento = {
                                    'Data de contato': datetime.now().strftime('%d/%m/%Y'),
                                    'Nome': ticket.get('Nome', ''),
                                    'Classificação': ticket.get('Classificação', ''),
                                    'Valor': '',  # Pode ser recuperado da base Total se necessário
                                    'Telefone': ticket.get('Telefone', ''),
                                    'Relato da conversa': f"[SUPORTE CONCLUÍDO] {novo_acompanhamento if novo_acompanhamento else 'Ticket finalizado'}",
                                    'Follow up': 'Acompanhamento pós-suporte',
                                    'Data de chamada': nova_data_contato.strftime('%d/%m/%Y') if nova_data_contato else '',
                                    'Observação': f"Cliente retornando do suporte. Problema: {ticket.get('Descrição do problema', 'N/D')}"
                                }
                                
                                df_agendamentos_novo = pd.concat([df_agendamentos, pd.DataFrame([novo_agendamento])], ignore_index=True)
                                conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_agendamentos_novo)
                                
                                # 2. Remover de SUPORTE
                                df_suporte_atual = conn.read(worksheet="SUPORTE", ttl=0)
                                df_suporte_novo = df_suporte_atual.drop(idx).reset_index(drop=True)
                                conn.update(worksheet="SUPORTE", data=df_suporte_novo)
                                
                                carregar_dados.clear()
                                st.success(f"🎉 Suporte finalizado! Cliente {nome_cliente} movido para Agendamentos Ativos")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ Erro ao finalizar: {e}")
        
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

# ============================================================================
# RENDER - PÁGINA DASHBOARD
# ============================================================================

def render_dashboard():
    """Renderiza a página de Dashboard com análises e gráficos"""
    
    st.title("📊 Dashboard Analítico")
    st.markdown("Visão geral e análises do CRM")
    st.markdown("---")
    
    # ========== SEÇÃO DE FILTROS ==========
    st.subheader("🔍 Filtros de Análise")
    
    # Criar 3 colunas para os filtros
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
    
    with col_filtro1:
        # Filtro de Classificação
        opcoes_classificacao = [
            "Todas",
            "Novo",
            "Promissor", 
            "Leal",
            "Campeão",
            "Em risco",
            "Dormente"
        ]
        
        filtro_classificacao = st.multiselect(
            "🏷️ Classificações:",
            options=opcoes_classificacao[1:],  # Todas exceto "Todas"
            default=opcoes_classificacao[1:],  # Todas selecionadas por padrão
            help="Selecione uma ou mais classificações para analisar"
        )
        
        # Se nenhuma selecionada, usar todas
        if not filtro_classificacao:
            filtro_classificacao = opcoes_classificacao[1:]
    
    with col_filtro2:
        # Filtro de Data Inicial
        data_inicial = st.date_input(
            "📅 Data Inicial:",
            value=datetime.now().replace(day=1),  # Primeiro dia do mês atual
            help="Data inicial para análise"
        )
    
    with col_filtro3:
        # Filtro de Data Final
        data_final = st.date_input(
            "📅 Data Final:",
            value=datetime.now(),  # Hoje
            help="Data final para análise"
        )
    
    # Validação de datas
    if data_inicial > data_final:
        st.error("⚠️ A data inicial não pode ser maior que a data final!")
        return
    
    # Mostrar período selecionado
    dias_periodo = (data_final - data_inicial).days + 1
    st.info(f"📊 **Período selecionado:** {data_inicial.strftime('%d/%m/%Y')} até {data_final.strftime('%d/%m/%Y')} ({dias_periodo} dias)")
    
    # Mostrar classificações selecionadas
    st.info(f"🏷️ **Classificações:** {', '.join(filtro_classificacao)}")
    
    st.markdown("---")
    
    # ========== ÁREA DOS GRÁFICOS (virá depois) ==========
    st.subheader("📈 Análises e Gráficos")
    st.write("🚧 Gráficos serão adicionados aqui em seguida...")
    
    # Aqui vamos adicionar os gráficos nos próximos passos
    # Os filtros já estarão disponíveis nas variáveis:
    # - filtro_classificacao (lista de classificações selecionadas)
    # - data_inicial (data inicial do período)
    # - data_final (data final do período)



# ============================================================================
# SIDEBAR E NAVEGAÇÃO
# ============================================================================

with st.sidebar:
    st.title("📋 Menu Principal")
    st.markdown("---")
    pagina = st.radio(
        "Navegação:",
        ["Dashboard 📊", "✅ Check-in", "📞 Em Atendimento", "🆘 Suporte", "📜 Histórico"],
        index=0
    )
    st.markdown("---")
    st.caption("CRM Pós-Vendas v1.0")

# ============================================================================
# ROUTER - CHAMADA DAS PÁGINAS
# ============================================================================

# ============================================================================
# ROTEAMENTO DE PÁGINAS
# ============================================================================

if pagina == "Dashboard 📊":
    render_dashboard()
elif pagina == "✅ Check-in":
    render_checkin()
elif pagina == "📞 Em Atendimento":
    render_em_atendimento()
elif pagina == "🆘 Suporte":
    render_suporte()
elif pagina == "📜 Histórico":
    render_historico()
