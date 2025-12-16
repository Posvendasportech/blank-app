# ============================================================================
# CRM PÓS-VENDAS - STREAMLIT APP
# Versão: 1.0
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
# FUNÇÕES AUXILIARES
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
# SIDEBAR
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
# PÁGINA: CHECK-IN
# ============================================================================

if pagina == "✅ Check-in":
    st.title("✅ Check-in de Clientes")
    st.markdown("Selecione clientes para iniciar o fluxo de atendimento")
    st.markdown("---")
    
    classificacoes_disponiveis = ["Total", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"]
    classificacao_selecionada = st.selectbox(
        "📂 Escolha a classificação:",
        classificacoes_disponiveis,
        index=0
    )
    
    st.info(f"📊 Visualizando: **{classificacao_selecionada}**")
    st.markdown("---")
    
    with st.spinner(f"Carregando clientes..."):
        df_clientes = carregar_dados(classificacao_selecionada)
    
    if df_clientes.empty:
        st.warning(f"⚠️ Nenhum cliente encontrado")
        st.stop()
    
    st.success(f"✅ {len(df_clientes)} clientes encontrados")
    
    with st.expander("🔍 Debug"):
        st.write("Colunas:", df_clientes.columns.tolist())
        st.dataframe(df_clientes.head(3))
    
    st.markdown("---")
    
    # Filtros
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        busca_nome = st.text_input("Buscar por nome:", "")
    with col_f2:
        if 'Dias desde a compra' in df_clientes.columns:
            dias_min = 0
            dias_max = int(df_clientes['Dias desde a compra'].max()) if df_clientes['Dias desde a compra'].max() > 0 else 365
            filtro_dias = st.slider("Dias desde última compra:", dias_min, dias_max, (dias_min, dias_max))
        else:
            filtro_dias = None
    
    # Aplicar filtros
    df_filtrado = df_clientes.copy()
    if busca_nome and 'Nome' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['Nome'].str.contains(busca_nome, case=False, na=False)]
    if filtro_dias and 'Dias desde a compra' in df_filtrado.columns:
        df_filtrado = df_filtrado[(df_filtrado['Dias desde a compra'] >= filtro_dias[0]) & (df_filtrado['Dias desde a compra'] <= filtro_dias[1])]
    
    st.markdown("---")
    st.subheader(f"📋 Clientes ({len(df_filtrado)})")
    
    if df_filtrado.empty:
        st.info("Nenhum cliente encontrado")
    else:
        for index, cliente in df_filtrado.iterrows():
            with st.container():
                col_info, col_metricas, col_acao = st.columns([2, 3, 1])
                
                with col_info:
                    st.markdown(f"### 👤 {cliente.get('Nome', 'N/D')}")
                    st.caption(f"📧 {cliente.get('Email', 'N/D')}")
                    st.caption(f"📱 {cliente.get('Telefone', 'N/D')}")
                
                with col_metricas:
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        valor = cliente.get('Valor', 0)
                        if pd.notna(valor) and valor != '':
                            try:
                                st.metric("💰 Total", f"R$ {float(valor):,.2f}")
                            except:
                                st.metric("💰 Total", "R$ 0,00")
                        else:
                            st.metric("💰 Total", "R$ 0,00")
                    
                    with m2:
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
                    
                    with m3:
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
                
                with col_acao:
                    st.write("")
                    st.write("")
                    if st.button("✅ Check-in", key=f"btn_{index}", type="primary", use_container_width=True):
                        with st.spinner('Processando...'):
                            if adicionar_agendamento(cliente, classificacao_selecionada):
                                st.cache_data.clear()
                                st.success(f"✅ Check-in realizado!")
                                st.balloons()
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Erro ao realizar check-in")
                
                st.markdown("---")

# ============================================================================
# PÁGINA: EM ATENDIMENTO
# ============================================================================

elif pagina == "📞 Em Atendimento":
    st.title("📞 Em Atendimento")
    st.markdown("Registre conversas e agende próximos contatos")
    st.markdown("---")
    
    with st.spinner("Carregando..."):
        df_agendamentos = carregar_dados("AGENDAMENTOS_ATIVOS")
    
    if df_agendamentos.empty:
        st.info("✅ Nenhum agendamento ativo")
        st.write("👉 Faça check-in na página **Check-in**")
    else:
        # Métricas
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("📊 Total", len(df_agendamentos))
        with c2:
            if 'Follow up' in df_agendamentos.columns:
                pend = len(df_agendamentos[df_agendamentos['Follow up'] == 'Pendente'])
                st.metric("⏳ Pendentes", pend)
        with c3:
            hoje = datetime.now().strftime('%d/%m/%Y')
            if 'Data de contato' in df_agendamentos.columns:
                hj = len(df_agendamentos[df_agendamentos['Data de contato'] == hoje])
                st.metric("📅 Hoje", hj)
        with c4:
            if 'Relato da conversa' in df_agendamentos.columns:
                rel = len(df_agendamentos[df_agendamentos['Relato da conversa'].notna() & (df_agendamentos['Relato da conversa'] != '')])
                st.metric("✅ Com Relato", rel)
        
        st.markdown("---")
        
        # Filtros
        cf1, cf2, cf3 = st.columns(3)
        with cf1:
            busca = st.text_input("Buscar:", "", key="busca_atend")
        with cf2:
            if 'Follow up' in df_agendamentos.columns:
                status_opts = ['Todos'] + list(df_agendamentos['Follow up'].unique())
                filtro_st = st.selectbox("Status:", status_opts)
            else:
                filtro_st = 'Todos'
        with cf3:
            if 'Classificação' in df_agendamentos.columns:
                class_opts = ['Todos'] + list(df_agendamentos['Classificação'].unique())
                filtro_cl = st.selectbox("Classificação:", class_opts)
            else:
                filtro_cl = 'Todos'
        
        df_filt = df_agendamentos.copy()
        if busca and 'Nome' in df_filt.columns:
            df_filt = df_filt[df_filt['Nome'].str.contains(busca, case=False, na=False)]
        if filtro_st != 'Todos' and 'Follow up' in df_filt.columns:
            df_filt = df_filt[df_filt['Follow up'] == filtro_st]
        if filtro_cl != 'Todos' and 'Classificação' in df_filt.columns:
            df_filt = df_filt[df_filt['Classificação'] == filtro_cl]
        
        st.markdown("---")
        st.subheader(f"📋 Agendamentos ({len(df_filt)})")
        
        if df_filt.empty:
            st.info("Nenhum agendamento encontrado")
        else:
            for idx, agend in df_filt.iterrows():
                with st.expander(f"👤 {agend.get('Nome', 'N/D')} - {agend.get('Classificação', 'N/D')}", expanded=False):
                    ce, cd = st.columns([1, 1])
                    
                    with ce:
                        st.markdown("### 📊 Informações")
                        st.write(f"**👤 Nome:** {agend.get('Nome', 'N/D')}")
                        st.write(f"**📱 Telefone:** {agend.get('Telefone', 'N/D')}")
                        st.write(f"**🏷️ Classificação:** {agend.get('Classificação', 'N/D')}")
                        
                        val = agend.get('Valor', 0)
                        if pd.notna(val) and val != '':
                            try:
                                st.write(f"**💰 Valor:** R$ {float(val):,.2f}")
                            except:
                                st.write(f"**💰 Valor:** {val}")
                        else:
                            st.write("**💰 Valor:** R$ 0,00")
                        
                        st.write(f"**📅 Check-in:** {agend.get('Data de contato', 'N/D')}")
                        st.markdown("---")
                        st.markdown("### 📝 Histórico")
                        
                        rel_at = agend.get('Relato da conversa', '')
                        if rel_at:
                            st.info(f"**Relato:** {rel_at}")
                        else:
                            st.caption("_Sem relato_")
                        
                        fol_at = agend.get('Follow up', '')
                        if fol_at:
                            st.info(f"**Follow-up:** {fol_at}")
                        else:
                            st.caption("_Sem follow-up_")
                        
                        dat_at = agend.get('Data de chamada', '')
                        if dat_at:
                            st.info(f"**Data:** {dat_at}")
                        else:
                            st.caption("_Sem data_")
                        
                        obs_at = agend.get('Observação', '')
                        if obs_at:
                            st.info(f"**Obs:** {obs_at}")
                    
                    with cd:
                        st.markdown("### ✏️ Atualizar")
                        
                        with st.form(key=f"form_{idx}"):
                            n_relato = st.text_area("📝 Relato:", value=rel_at if rel_at else "", height=100, placeholder="Descreva a conversa...")
                            n_follow = st.text_input("🎯 Follow-up:", value=fol_at if fol_at else "", placeholder="Motivo do próximo contato...")
                            n_data = st.date_input("📅 Data:", value=None)
                            n_obs = st.text_area("💬 Observações:", value=obs_at if obs_at else "", height=80, placeholder="Informações extras...")
                            
                            st.markdown("---")
                            cb1, cb2 = st.columns(2)
                            
                            with cb1:
                                btn_salv = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)
                            with cb2:
                                btn_fin = st.form_submit_button("✅ Finalizar", use_container_width=True)
                            
                            if btn_salv:
                                if not n_relato and not n_follow:
                                    st.warning("⚠️ Preencha ao menos Relato ou Follow-up")
                                else:
                                    with st.spinner("Salvando..."):
                                        dados_upd = {
                                            'Relato da conversa': n_relato,
                                            'Follow up': n_follow,
                                            'Data de chamada': n_data.strftime('%d/%m/%Y') if n_data else '',
                                            'Observação': n_obs
                                        }
                                        if atualizar_agendamento(idx, dados_upd):
                                            st.cache_data.clear()
                                            st.success("✅ Salvo com sucesso!")
                                            st.balloons()
                                            time.sleep(1.5)
                                            st.rerun()
                            
                            if btn_fin:
                                if not n_relato:
                                    st.error("❌ Preencha o Relato antes de finalizar!")
                                else:
                                    with st.spinner("Finalizando..."):
                                        dados_fin = agend.copy()
                                        dados_fin['Relato da conversa'] = n_relato
                                        dados_fin['Follow up'] = n_follow
                                        dados_fin['Data de chamada'] = n_data.strftime('%d/%m/%Y') if n_data else ''
                                        dados_fin['Observação'] = n_obs
                                        
                                        if finalizar_atendimento(idx, dados_fin):
                                            st.cache_data.clear()
                                            st.success("✅ Finalizado e movido para histórico!")
                                            st.balloons()
                                            time.sleep(2)
                                            st.rerun()
                
                st.markdown("---")

# ============================================================================
# OUTRAS PÁGINAS
# ============================================================================

elif pagina == "🆘 Suporte":
    st.title("🆘 Suporte")
    st.info("Em breve")

elif pagina == "📜 Histórico":
    st.title("📜 Histórico")
    st.info("Em breve")
