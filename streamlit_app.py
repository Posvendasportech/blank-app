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
    hoje = datetime.now().strftime('%d/%m/%Y')
    hoje_dt = datetime.now()
    
    # Filtrar apenas agendamentos para hoje
    if 'Data de chamada' in df_agendamentos.columns:
        df_hoje = df_agendamentos[df_agendamentos['Data de chamada'] == hoje].copy()
    else:
        df_hoje = pd.DataFrame()
    
    # Calcular vencidos (datas anteriores a hoje)
    df_vencidos = pd.DataFrame()
    if 'Data de chamada' in df_agendamentos.columns:
        vencidos_lista = []
        for idx, row in df_agendamentos.iterrows():
            data_chamada_str = row.get('Data de chamada', '')
            if data_chamada_str and data_chamada_str != '':
                try:
                    data_chamada_dt = datetime.strptime(data_chamada_str, '%d/%m/%Y')
                    if data_chamada_dt < hoje_dt:
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
    st.subheader(f"📋 Atendimentos ({len(df_filt)})")
    
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
                data_chamada_dt = datetime.strptime(data_chamada_str, '%d/%m/%Y')
                if data_chamada_dt < hoje_dt:
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
                                    st.success(f"✅ Novo agendamento criado para {novo_follow} em {nova_data.strftime('%d/%m/%Y')}!")
                                    st.balloons()
                                    time.sleep(2)
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
    """Renderiza a página de Histórico"""
    st.title("📜 Histórico")
    st.info("Esta página será implementada em breve")

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
