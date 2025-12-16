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

def limpar_telefone(telefone):
    """Remove caracteres especiais do telefone, deixando apenas números"""
    if pd.isna(telefone) or telefone == '':
        return ''
    return ''.join(filter(str.isdigit, str(telefone)))
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
# FUNÇÕES AUXILIARES - UTILITÁRIOS
# ============================================================================

@st.cache_data(ttl=60)
def carregar_dados(nome_aba):
    """Carrega dados de uma aba específica do Google Sheets"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=nome_aba, ttl=60)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar aba '{nome_aba}': {e}")
        return pd.DataFrame()


def adicionar_agendamento(dados_cliente, classificacao_origem):
    """Adiciona um cliente na aba AGENDAMENTOS_ATIVOS"""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
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
        conn = st.connection("gsheets", type=GSheetsConnection)
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
        conn = st.connection("gsheets", type=GSheetsConnection)
        
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
# RENDER - PÁGINA CHECK-IN
# ============================================================================

# ============================================================================
# RENDER - PÁGINA CHECK-IN (VERSÃO OTIMIZADA)
# ============================================================================

def render_checkin():
    """Renderiza a página de Check-in de clientes - Versão otimizada"""
    
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
            meta_novo = st.number_input("🆕 Novo", min_value=0, max_value=50, value=5, step=1)
            meta_promissor = st.number_input("⭐ Promissor", min_value=0, max_value=50, value=5, step=1)
        
        with col_meta2:
            meta_leal = st.number_input("💙 Leal", min_value=0, max_value=50, value=5, step=1)
            meta_campeao = st.number_input("🏆 Campeão", min_value=0, max_value=50, value=3, step=1)
        
        with col_meta3:
            meta_risco = st.number_input("⚠️ Em risco", min_value=0, max_value=50, value=5, step=1)
            meta_dormente = st.number_input("😴 Dormente", min_value=0, max_value=50, value=5, step=1)
        
        # Calcular meta total
        meta_total = meta_novo + meta_promissor + meta_leal + meta_campeao + meta_risco + meta_dormente
        
        st.markdown("---")
        st.info(f"🎯 **Meta Total do Dia:** {meta_total} check-ins")
    
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
            "Novo": meta_novo,
            "Promissor": meta_promissor,
            "Leal": meta_leal,
            "Campeão": meta_campeao,
            "Em risco": meta_risco,
            "Dormente": meta_dormente
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
                                    conn = st.connection("gsheets", type=GSheetsConnection)
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
                                    
                                    st.cache_data.clear()
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
                                    conn = st.connection("gsheets", type=GSheetsConnection)
                                    
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
                                    st.cache_data.clear()
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
    """Renderiza a página de Suporte"""
    st.title("🆘 Suporte")
    st.info("Esta página será implementada em breve")

# ============================================================================
# RENDER - PÁGINA HISTÓRICO
# ============================================================================

def render_historico():
    """Renderiza a página de Histórico - Busca Unificada de Clientes"""
    
    st.title("📜 Histórico de Clientes")
    st.markdown("Busque clientes e visualize todo o histórico de atendimentos")
    st.markdown("---")
    
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
            df_historico = carregar_dados("HISTORICO")
            df_agendamentos = carregar_dados("AGENDAMENTOS_ATIVOS")
            df_suporte = carregar_dados("SUPORTE")
            
            # Limpar termo de busca (remover caracteres especiais para telefone)
            termo_limpo = termo_busca.strip()
            
            # Buscar na aba Total (dados cadastrais)
            cliente_encontrado = None
            
            if not df_total.empty:
                # Buscar por telefone (exato ou contém)
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
        
        # ========== RESULTADO DA BUSCA ==========
        if cliente_encontrado is not None:
            
            st.success(f"✅ Cliente encontrado: **{cliente_encontrado.get('Nome', 'N/D')}**")
            st.markdown("---")
            
            # Pegar telefone para buscar histórico
            telefone_cliente = cliente_encontrado.get('Telefone', '')
            nome_cliente = cliente_encontrado.get('Nome', 'N/D')
            
            # ========== DADOS CADASTRAIS ==========
            st.subheader("📊 Dados Cadastrais")
            
            col_info1, col_info2, col_info3 = st.columns(3)
            
            with col_info1:
                st.write(f"**👤 Nome:** {nome_cliente}")
                st.write(f"**📱 Telefone:** {telefone_cliente}")
                st.write(f"**📧 E-mail:** {cliente_encontrado.get('Email', 'N/D')}")
            
            with col_info2:
                st.write(f"**🏷️ Classificação:** {cliente_encontrado.get('Classificação ', 'N/D')}")
                
                valor = cliente_encontrado.get('Valor', 0)
                if pd.notna(valor) and valor != '':
                    try:
                        st.write(f"**💰 Valor Total:** R$ {float(valor):,.2f}")
                    except:
                        st.write(f"**💰 Valor Total:** {valor}")
                else:
                    st.write("**💰 Valor Total:** R$ 0,00")
                
                compras = cliente_encontrado.get('Compras', 0)
                if pd.notna(compras) and compras != '':
                    try:
                        st.write(f"**🛒 Total de Compras:** {int(float(compras))}")
                    except:
                        st.write(f"**🛒 Total de Compras:** {compras}")
                else:
                    st.write("**🛒 Total de Compras:** 0")
            
            with col_info3:
                dias = cliente_encontrado.get('Dias desde a compra', 0)
                if pd.notna(dias) and dias != '':
                    try:
                        st.write(f"**📅 Dias desde última compra:** {int(round(float(dias)))}")
                    except:
                        st.write(f"**📅 Dias desde última compra:** {dias}")
                else:
                    st.write("**📅 Dias desde última compra:** N/D")
            
            st.markdown("---")
            
            # ========== BUSCAR HISTÓRICO POR TELEFONE ==========
                        # ========== BUSCAR HISTÓRICO POR TELEFONE ==========
            historico_cliente = []
            agendamentos_ativos = []
            tickets_suporte = []
            
            # Limpar telefone do cliente para comparação
            telefone_limpo = limpar_telefone(telefone_cliente)
            
            # Histórico de atendimentos finalizados
            if not df_historico.empty and 'Telefone' in df_historico.columns:
                # Criar coluna temporária com telefone limpo
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
                with st.expander("📞 Criar Agendamento (Vendas/Pós-vendas)", expanded=False):
                    st.info("💡 Use para vendas, follow-ups comerciais ou satisfação do cliente")
                    
                    with st.form(key=f"form_novo_agendamento_{telefone_cliente}"):
                        
                        motivo_agend = st.text_input(
                            "🎯 Motivo do contato:",
                            placeholder="Ex: Oferta de novo produto, Follow-up de satisfação..."
                        )
                        
                        data_agend = st.date_input(
                            "📅 Data do agendamento:",
                            value=None
                        )
                        
                        obs_agend = st.text_area(
                            "💬 Observações:",
                            height=100,
                            placeholder="Informações relevantes sobre este agendamento..."
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
                                with st.spinner("Criando agendamento..."):
                                    try:
                                        conn = st.connection("gsheets", type=GSheetsConnection)
                                        df_agend_atual = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
                                        
                                        novo_agend = {
                                            'Data de contato': datetime.now().strftime('%d/%m/%Y'),
                                            'Nome': nome_cliente,
                                            'Classificação': cliente_encontrado.get('Classificação ', 'N/D'),
                                            'Valor': cliente_encontrado.get('Valor', ''),
                                            'Telefone': telefone_cliente,
                                            'Relato da conversa': '',
                                            'Follow up': motivo_agend,
                                            'Data de chamada': data_agend.strftime('%d/%m/%Y'),
                                            'Observação': obs_agend if obs_agend else 'Agendamento criado via Histórico'
                                        }
                                        
                                        df_novo = pd.concat([df_agend_atual, pd.DataFrame([novo_agend])], ignore_index=True)
                                        conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_novo)
                                        
                                        st.cache_data.clear()
                                        st.success(f"✅ Agendamento criado para {data_agend.strftime('%d/%m/%Y')}!")
                                        time.sleep(1)
                                        st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"❌ Erro: {e}")
            
            with col_acao2:
                with st.expander("🆘 Abrir Ticket de Suporte", expanded=False):
                    st.warning("⚠️ Use para problemas técnicos, reclamações ou suporte")
                    
                    with st.form(key=f"form_novo_suporte_{telefone_cliente}"):
                        
                        assunto_suporte = st.text_input(
                            "📌 Assunto:",
                            placeholder="Ex: Produto com defeito, Problema na entrega..."
                        )
                        
                        prioridade = st.selectbox(
                            "🚨 Prioridade:",
                            ["Baixa", "Média", "Alta", "Urgente"]
                        )
                        
                        descricao_suporte = st.text_area(
                            "📝 Descrição do problema:",
                            height=100,
                            placeholder="Descreva detalhadamente o problema..."
                        )
                        
                        btn_criar_suporte = st.form_submit_button(
                            "🆘 Abrir Ticket",
                            type="secondary",
                            use_container_width=True
                        )
                        
                        if btn_criar_suporte:
                            if not assunto_suporte:
                                st.error("❌ Informe o assunto do ticket!")
                            elif not descricao_suporte:
                                st.error("❌ Descreva o problema!")
                            else:
                                with st.spinner("Abrindo ticket de suporte..."):
                                    try:
                                        conn = st.connection("gsheets", type=GSheetsConnection)
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
                                        
                                        st.cache_data.clear()
                                        st.success(f"✅ Ticket de suporte aberto com sucesso!")
                                        time.sleep(1)
                                        st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"❌ Erro: {e}")
        
        else:
            st.error("❌ Nenhum cliente encontrado com esse telefone ou nome")
            st.info("💡 **Dica:** Verifique se digitou corretamente ou tente buscar apenas parte do nome/telefone")
    
    elif btn_buscar and not termo_busca:
        st.warning("⚠️ Digite um telefone ou nome para buscar")

# ============================================================================
# SIDEBAR E NAVEGAÇÃO
# ============================================================================

with st.sidebar:
    st.title("📋 Menu Principal")
    st.markdown("---")
    pagina = st.radio(
        "Navegação:",
        ["✅ Check-in", "📞 Em Atendimento", "🆘 Suporte", "📜 Histórico"],
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
