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
# ============================================================================
# FUNÇÕES DE POPULAÇÃO - NOVAS ABAS
# ============================================================================

def gerar_id_unico(prefixo):
    """Gera ID único para registros (ex: CHK-20251217-001)"""
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    return f"{prefixo}-{timestamp}"


def registrar_checkin(dados_cliente, classificacao, respondeu="SEM_RESPOSTA"):
    """Registra check-in na aba LOG_CHECKINS"""
    try:
        conn = get_gsheets_connection()
        df_log = conn.read(worksheet="LOG_CHECKINS", ttl=0)
        
        novo_registro = {
            'ID_Checkin': gerar_id_unico('CHK'),
            'Data_Checkin': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'Nome_Cliente': dados_cliente.get('Nome', ''),
            'Telefone': dados_cliente.get('Telefone', ''),
            'Classificacao_Cliente': classificacao,
            'Valor_Cliente_Antes': dados_cliente.get('Valor', 0),
            'Compras_Cliente_Antes': dados_cliente.get('Compras', 0),
            'Respondeu': respondeu,
            'Relato_Resumo': dados_cliente.get('Relato', '')[:100],
            'Criado_Por': 'Sistema',
            'Dia_Semana': datetime.now().strftime('%A'),
            'Hora_Checkin': datetime.now().strftime('%H:%M')
        }
        
        df_atualizado = pd.concat([df_log, pd.DataFrame([novo_registro])], ignore_index=True)
        conn.update(worksheet="LOG_CHECKINS", data=df_atualizado)
        return True
    except Exception as e:
        st.error(f"Erro ao registrar check-in: {e}")
        return False


def detectar_conversao_automatica():
    """
    Detecta conversões comparando HISTORICO com aba Total
    Deve rodar 1x por dia às 00h
    """
    try:
        conn = get_gsheets_connection()
        
        # Carregar dados necessários
        df_historico = conn.read(worksheet="HISTORICO", ttl=0)
        df_total = conn.read(worksheet="Total", ttl=0)
        df_conversoes = conn.read(worksheet="LOG_CONVERSOES", ttl=0)
        
        if df_historico.empty or df_total.empty:
            return False
        
        conversoes_detectadas = []
        hoje = datetime.now().strftime('%d/%m/%Y')
        
        # Para cada cliente no histórico
        for telefone in df_historico['Telefone'].unique():
            if pd.isna(telefone) or telefone == '':
                continue
            
            # Última entrada do histórico deste cliente
            df_cliente_hist = df_historico[df_historico['Telefone'] == telefone]
            if df_cliente_hist.empty:
                continue
            
            ultima_entrada_hist = df_cliente_hist.iloc[-1]
            
            # Dados atuais na aba Total
            df_cliente_total = df_total[df_total['Telefone'] == telefone]
            if df_cliente_total.empty:
                continue
            
            dados_total = df_cliente_total.iloc[0]
            
            # Comparar valores
            valor_antes = float(ultima_entrada_hist.get('Valor', 0))
            valor_depois = float(dados_total.get('Valor', 0))
            compras_antes = int(ultima_entrada_hist.get('Compras', 0))
            compras_depois = int(dados_total.get('Compras', 0))
            
            diferenca_valor = valor_depois - valor_antes
            diferenca_compras = compras_depois - compras_antes
            
            # Critério de conversão: +R$5 OU +1 compra
            if diferenca_valor >= 5 or diferenca_compras >= 1:
                
                # Verificar se já não foi registrada hoje
                ja_registrado = False
                if not df_conversoes.empty:
                    df_conv_cliente = df_conversoes[
                        (df_conversoes['Telefone'] == telefone) & 
                        (df_conversoes['Data_Conversao'].str.startswith(hoje))
                    ]
                    ja_registrado = not df_conv_cliente.empty
                
                if not ja_registrado:
                    # Buscar último check-in
                    df_checkins = conn.read(worksheet="LOG_CHECKINS", ttl=0)
                    dias_desde_checkin = 0
                    
                    if not df_checkins.empty:
                        df_checkins_cliente = df_checkins[df_checkins['Telefone'] == telefone]
                        if not df_checkins_cliente.empty:
                            ultima_data_checkin = pd.to_datetime(
                                df_checkins_cliente.iloc[-1]['Data_Checkin'], 
                                format='%d/%m/%Y %H:%M',
                                errors='coerce'
                            )
                            if pd.notna(ultima_data_checkin):
                                dias_desde_checkin = (datetime.now() - ultima_data_checkin).days
                    
                    conversoes_detectadas.append({
                        'ID_Conversao': gerar_id_unico('CONV'),
                        'Data_Conversao': datetime.now().strftime('%d/%m/%Y %H:%M'),
                        'Nome_Cliente': dados_total.get('Nome', ''),
                        'Telefone': telefone,
                        'Classificacao_Cliente': dados_total.get('Classificação', ''),
                        'Valor_Antes': valor_antes,
                        'Valor_Depois': valor_depois,
                        'Diferenca_Valor': diferenca_valor,
                        'Compras_Antes': compras_antes,
                        'Compras_Depois': compras_depois,
                        'Dias_Desde_Ultimo_Checkin': dias_desde_checkin
                    })
        
        # Salvar conversões detectadas
        if conversoes_detectadas:
            df_novas_conv = pd.DataFrame(conversoes_detectadas)
            df_conv_atualizado = pd.concat([df_conversoes, df_novas_conv], ignore_index=True)
            conn.update(worksheet="LOG_CONVERSOES", data=df_conv_atualizado)
            return True
        
        return False
        
    except Exception as e:
        st.error(f"Erro ao detectar conversões: {e}")
        return False

def detectar_mudanca_classificacao():
    """
    Detecta mudanças de classificação comparando HISTORICO com abas atuais
    Lógica: Cliente está em HISTORICO com classificação X, mas agora está na aba Y
    """
    try:
        conn = get_gsheets_connection()
        
        # Carregar histórico
        df_historico = conn.read(worksheet="HISTORICO", ttl=0)
        
        if df_historico.empty or 'Telefone' not in df_historico.columns:
            return False  # Sem dados para comparar
        
        # Carregar histórico de classificações
        df_historico_class = conn.read(worksheet="HISTORICO_CLASSIFICACOES", ttl=0)
        
        # Carregar todas as abas de classificação atuais
        abas_classificacao = ['Novo', 'Promissor', 'Leal', 'Campeão', 'Em risco', 'Dormente']
        clientes_atuais = {}  # {telefone: {dados}}
        
        for aba in abas_classificacao:
            df = conn.read(worksheet=aba, ttl=0)
            if not df.empty and 'Telefone' in df.columns:
                for _, cliente in df.iterrows():
                    telefone = limpar_telefone(cliente.get('Telefone', ''))
                    if telefone:
                        # Tratar valores NaN
                        valor_raw = cliente.get('Valor', 0)
                        compras_raw = cliente.get('Compras', 0)
                        
                        valor_limpo = 0.0
                        if pd.notna(valor_raw) and valor_raw != '':
                            try:
                                valor_limpo = float(valor_raw)
                            except:
                                valor_limpo = 0.0
                        
                        compras_limpo = 0
                        if pd.notna(compras_raw) and compras_raw != '':
                            try:
                                compras_limpo = int(float(compras_raw))
                            except:
                                compras_limpo = 0
                        
                        clientes_atuais[telefone] = {
                            'Nome': cliente.get('Nome', ''),
                            'Classificacao_Atual': aba,
                            'Valor_Atual': valor_limpo,
                            'Compras_Atual': compras_limpo
                        }
        
        mudancas_detectadas = []
        hoje = datetime.now().strftime('%d/%m/%Y')
        
        # Para cada cliente no HISTORICO, verificar se mudou de classificação
        for telefone in df_historico['Telefone'].unique():
            if pd.isna(telefone) or telefone == '':
                continue
            
            telefone_limpo = limpar_telefone(str(telefone))
            
            # Última entrada no histórico deste cliente
            df_cliente_hist = df_historico[df_historico['Telefone'] == telefone]
            if df_cliente_hist.empty:
                continue
            
            ultima_entrada = df_cliente_hist.iloc[-1]
            classificacao_historico = ultima_entrada.get('Classificação', '')
            
            # Tratar valores NaN do histórico
            valor_antes_raw = ultima_entrada.get('Valor', 0)
            compras_antes_raw = ultima_entrada.get('Compras', 0)
            
            valor_antes = 0.0
            if pd.notna(valor_antes_raw) and valor_antes_raw != '':
                try:
                    valor_antes = float(valor_antes_raw)
                except:
                    valor_antes = 0.0
            
            compras_antes = 0
            if pd.notna(compras_antes_raw) and compras_antes_raw != '':
                try:
                    compras_antes = int(float(compras_antes_raw))
                except:
                    compras_antes = 0
            
            # Verificar se cliente existe nas abas atuais
            if telefone_limpo in clientes_atuais:
                dados_atuais = clientes_atuais[telefone_limpo]
                classificacao_atual = dados_atuais['Classificacao_Atual']
                
                # SE MUDOU DE CLASSIFICAÇÃO
                if classificacao_historico != classificacao_atual and classificacao_historico != '':
                    
                    # Verificar se já não foi registrada hoje
                    ja_registrado = False
                    if not df_historico_class.empty and 'Telefone' in df_historico_class.columns and 'Data' in df_historico_class.columns:
                        df_mudanca_hoje = df_historico_class[
                            (df_historico_class['Telefone'] == telefone) & 
                            (df_historico_class['Data'] == hoje)
                        ]
                        ja_registrado = not df_mudanca_hoje.empty
                    
                    if not ja_registrado:
                        mudancas_detectadas.append({
                            'Data': hoje,
                            'Nome_Cliente': dados_atuais['Nome'],
                            'Telefone': telefone,
                            'Classificacao_Anterior': classificacao_historico,
                            'Classificacao_Nova': classificacao_atual,
                            'Valor_Antes': valor_antes,
                            'Valor_Depois': dados_atuais['Valor_Atual'],
                            'Compras_Antes': compras_antes,
                            'Compras_Depois': dados_atuais['Compras_Atual']
                        })
                        
                        # ATUALIZAR O HISTORICO COM A NOVA CLASSIFICAÇÃO
                        mask = df_historico['Telefone'] == telefone
                        df_historico.loc[mask, 'Classificação'] = classificacao_atual
                        df_historico.loc[mask, 'Valor'] = dados_atuais['Valor_Atual']
                        df_historico.loc[mask, 'Compras'] = dados_atuais['Compras_Atual']
        
        # Salvar mudanças detectadas
        if mudancas_detectadas:
            # Salvar em HISTORICO_CLASSIFICACOES
            df_mudancas = pd.DataFrame(mudancas_detectadas)
            df_historico_class_atualizado = pd.concat([df_historico_class, df_mudancas], ignore_index=True)
            conn.update(worksheet="HISTORICO_CLASSIFICACOES", data=df_historico_class_atualizado)
            
            # Atualizar HISTORICO com novas classificações
            conn.update(worksheet="HISTORICO", data=df_historico)
            
            return True
        
        return False
        
    except Exception as e:
        st.error(f"Erro ao detectar mudanças de classificação: {e}")
        import traceback
        st.error(traceback.format_exc())
        return False


def executar_rotinas_diarias():
    """
    Executa todas as rotinas diárias automáticas COM LOGS DETALHADOS
    """
    try:
        st.markdown("---")
        st.markdown("### 🔄 Executando Rotinas Diárias...")
        
        # Container para logs
        log_container = st.container()
        
        with log_container:
            # ========== 1. SNAPSHOT DE MÉTRICAS ==========
            st.write("**1️⃣ Verificando Snapshot de Métricas...**")
            
            try:
                conn = get_gsheets_connection()
                df_metricas = conn.read(worksheet="HISTORICO_METRICAS", ttl=0)
                hoje = datetime.now().strftime('%d/%m/%Y')
                
                # Verificar se já existe snapshot de hoje
                if not df_metricas.empty and 'Data' in df_metricas.columns:
                    if hoje in df_metricas['Data'].values:
                        st.info(f"   ℹ️ Snapshot de hoje ({hoje}) já existe. Pulando...")
                        sucesso_metricas = True
                    else:
                        st.write(f"   🔄 Criando snapshot para {hoje}...")
                        sucesso_metricas = snapshot_metricas_diarias()
                        if sucesso_metricas:
                            st.success("   ✅ Snapshot criado com sucesso!")
                        else:
                            st.error("   ❌ Erro ao criar snapshot")
                else:
                    st.write(f"   🔄 Primeira vez! Criando snapshot para {hoje}...")
                    sucesso_metricas = snapshot_metricas_diarias()
                    if sucesso_metricas:
                        st.success("   ✅ Snapshot criado com sucesso!")
                    else:
                        st.error("   ❌ Erro ao criar snapshot")
                        
            except Exception as e:
                st.error(f"   ❌ Erro no snapshot: {e}")
                sucesso_metricas = False
            
            st.markdown("---")
            
            # ========== 2. DETECÇÃO DE CONVERSÕES ==========
            st.write("**2️⃣ Detectando Conversões...**")
            
            try:
                conn = get_gsheets_connection()
                df_historico = conn.read(worksheet="HISTORICO", ttl=0)
                df_total = conn.read(worksheet="Total", ttl=0)
                
                if df_historico.empty:
                    st.warning("   ⚠️ Aba HISTORICO vazia. Não há dados para comparar.")
                    sucesso_conversoes = False
                elif df_total.empty:
                    st.warning("   ⚠️ Aba Total vazia. Não há dados para comparar.")
                    sucesso_conversoes = False
                else:
                    total_clientes_historico = len(df_historico['Telefone'].unique())
                    total_clientes_total = len(df_total)
                    
                    st.write(f"   📊 Clientes no HISTORICO: {total_clientes_historico}")
                    st.write(f"   📊 Clientes no Total: {total_clientes_total}")
                    st.write("   🔍 Comparando dados...")
                    
                    sucesso_conversoes = detectar_conversao_automatica()
                    
                    if sucesso_conversoes:
                        st.success("   ✅ Conversões detectadas e registradas!")
                    else:
                        st.info("   ℹ️ Nenhuma conversão detectada hoje")
                        
            except Exception as e:
                st.error(f"   ❌ Erro na detecção de conversões: {e}")
                sucesso_conversoes = False
            
            st.markdown("---")
            
            # ========== 3. DETECÇÃO DE MUDANÇAS DE CLASSIFICAÇÃO ==========
            st.write("**3️⃣ Detectando Mudanças de Classificação...**")
            
            try:
                conn = get_gsheets_connection()
                
                # Verificar se aba existe
                try:
                    df_hist_class = conn.read(worksheet="HISTORICO_CLASSIFICACOES", ttl=0)
                    st.write("   📋 Aba HISTORICO_CLASSIFICACOES encontrada")
                except:
                    st.error("   ❌ Aba HISTORICO_CLASSIFICACOES não existe! Crie-a no Google Sheets")
                    sucesso_classificacoes = False
                    return
                
                st.write("   🔍 Analisando mudanças...")
                sucesso_classificacoes = detectar_mudanca_classificacao()
                
                if sucesso_classificacoes:
                    st.success("   ✅ Mudanças de classificação detectadas!")
                else:
                    st.info("   ℹ️ Nenhuma mudança de classificação detectada")
                    
            except Exception as e:
                st.error(f"   ❌ Erro na detecção de mudanças: {e}")
                sucesso_classificacoes = False
            
            st.markdown("---")
            
            # ========== RESUMO FINAL ==========
            st.markdown("### 📊 Resumo da Execução")
            
            col_r1, col_r2, col_r3 = st.columns(3)
            
            with col_r1:
                if sucesso_metricas:
                    st.success("✅ Snapshot")
                else:
                    st.error("❌ Snapshot")
            
            with col_r2:
                if sucesso_conversoes:
                    st.success("✅ Conversões")
                else:
                    st.info("ℹ️ Conversões")
            
            with col_r3:
                if sucesso_classificacoes:
                    st.success("✅ Classificações")
                else:
                    st.info("ℹ️ Classificações")
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erro crítico nas rotinas: {e}")
        import traceback
        st.code(traceback.format_exc())
        return False

def salvar_metas_diarias(metas_dict):
    """Salva metas do dia na aba METAS_DIARIAS"""
    try:
        conn = get_gsheets_connection()
        df_metas = conn.read(worksheet="METAS_DIARIAS", ttl=0)
        
        hoje = datetime.now().strftime('%d/%m/%Y')
        
        # Verificar se já existe registro de hoje
        if not df_metas.empty and 'Data' in df_metas.columns:
            if hoje in df_metas['Data'].values:
                return True  # Já salvo hoje
        
        meta_total = sum(metas_dict.values())
        
        novo_registro = {
            'Data': hoje,
            'Meta_Novo': metas_dict.get('novo', 5),
            'Meta_Promissor': metas_dict.get('promissor', 5),
            'Meta_Leal': metas_dict.get('leal', 5),
            'Meta_Campeao': metas_dict.get('campeao', 3),
            'Meta_EmRisco': metas_dict.get('risco', 5),
            'Meta_Dormente': metas_dict.get('dormente', 5),
            'Meta_Total': meta_total,
            'Usuario': 'Sistema',
            'Hora_Definicao': datetime.now().strftime('%H:%M')
        }
        
        df_atualizado = pd.concat([df_metas, pd.DataFrame([novo_registro])], ignore_index=True)
        conn.update(worksheet="METAS_DIARIAS", data=df_atualizado)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar metas: {e}")
        return False


def snapshot_metricas_diarias():
    """Gera snapshot diário de todas as métricas (rodar 1x por dia)"""
    try:
        conn = get_gsheets_connection()
        df_historico_metricas = conn.read(worksheet="HISTORICO_METRICAS", ttl=0)
        
        hoje = datetime.now().strftime('%d/%m/%Y')
        
        # Verificar se já existe snapshot de hoje
        if not df_historico_metricas.empty and 'Data' in df_historico_metricas.columns:
            if hoje in df_historico_metricas['Data'].values:
                return True  # Já existe snapshot de hoje
        
        # Carregar dados de todas as classificações
        classificacoes = ['Novo', 'Promissor', 'Leal', 'Campeão', 'Em risco', 'Dormente']
        totais = {}
        valores = {}
        
        for classif in classificacoes:
            df = conn.read(worksheet=classif, ttl=0)
            key = classif.replace(' ', '').replace('ã', 'a').replace('ê', 'e')
            totais[key] = len(df) if not df.empty else 0
            valores[key] = df['Valor'].sum() if not df.empty and 'Valor' in df.columns else 0
        
        # Carregar check-ins de hoje
        df_checkins = conn.read(worksheet="LOG_CHECKINS", ttl=0)
        if not df_checkins.empty and 'Data_Checkin' in df_checkins.columns:
            checkins_hoje = len(df_checkins[df_checkins['Data_Checkin'].str.startswith(hoje)])
        else:
            checkins_hoje = 0
        
        # Carregar meta de hoje
        df_metas = conn.read(worksheet="METAS_DIARIAS", ttl=0)
        if not df_metas.empty and 'Data' in df_metas.columns:
            meta_hoje_row = df_metas[df_metas['Data'] == hoje]
            meta_dia = int(meta_hoje_row.iloc[0]['Meta_Total']) if not meta_hoje_row.empty else 0
        else:
            meta_dia = 0
        
        meta_atingida = "SIM" if checkins_hoje >= meta_dia else "NAO"
        
        # Conversões de hoje
        df_conversoes = conn.read(worksheet="LOG_CONVERSOES", ttl=0)
        if not df_conversoes.empty and 'Data_Conversao' in df_conversoes.columns:
            conversoes_hoje = len(df_conversoes[df_conversoes['Data_Conversao'].str.startswith(hoje)])
        else:
            conversoes_hoje = 0
        
        novo_snapshot = {
            'Data': hoje,
            'Total_Novo': totais.get('Novo', 0),
            'Total_Promissor': totais.get('Promissor', 0),
            'Total_Leal': totais.get('Leal', 0),
            'Total_Campeao': totais.get('Campeao', 0),
            'Total_EmRisco': totais.get('Emrisco', 0),
            'Total_Dormente': totais.get('Dormente', 0),
            'Total_Clientes': sum(totais.values()),
            'CheckIns_Realizados': checkins_hoje,
            'Meta_Dia': meta_dia,
            'Meta_Atingida': meta_atingida,
            'Conversoes_Dia': conversoes_hoje,
            'Valor_Total_Novo': valores.get('Novo', 0),
            'Valor_Total_Promissor': valores.get('Promissor', 0),
            'Valor_Total_Leal': valores.get('Leal', 0),
            'Valor_Total_Campeao': valores.get('Campeao', 0),
            'Valor_Total_EmRisco': valores.get('Emrisco', 0),
            'Valor_Total_Dormente': valores.get('Dormente', 0),
            'Valor_Total_Geral': sum(valores.values())
        }
        
        df_atualizado = pd.concat([df_historico_metricas, pd.DataFrame([novo_snapshot])], ignore_index=True)
        conn.update(worksheet="HISTORICO_METRICAS", data=df_atualizado)
        return True
    except Exception as e:
        st.error(f"Erro ao gerar snapshot: {e}")
        return False


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
    
    # ✅ NOVO: Salvar metas diárias automaticamente (1x por dia)
    salvar_metas_diarias(st.session_state.metas_checkin)
    
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
                                    
                                    # ✅ NOVO: Registrar check-in no LOG
                                    dados_checkin = {
                                        'Nome': cliente.get('Nome', ''),
                                        'Telefone': cliente.get('Telefone', ''),
                                        'Valor': cliente.get('Valor', 0),
                                        'Compras': cliente.get('Compras', 0),
                                        'Relato': primeira_conversa
                                    }
                                    registrar_checkin(dados_checkin, classificacao_selecionada, respondeu="SIM" if primeira_conversa else "SEM_RESPOSTA")
                                    
                                    # ✅ NOVO: Detectar se houve conversão
                                    try:
                                        valor_atual = float(cliente.get('Valor', 0)) if pd.notna(cliente.get('Valor', 0)) else 0
                                        compras_atual = int(cliente.get('Compras', 0)) if pd.notna(cliente.get('Compras', 0)) else 0
                                        detectar_conversao(cliente.get('Nome', ''), valor_atual, compras_atual)
                                    except:
                                        pass  # Se falhar detecção, não interrompe o fluxo
                                    
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
                                    
                                    # ✅ NOVO: Registrar follow-up no LOG
                                    dados_followup = {
                                        'Nome': agend.get('Nome', ''),
                                        'Telefone': agend.get('Telefone', ''),
                                        'Valor': agend.get('Valor', 0),
                                        'Compras': agend.get('Compras', 0),
                                        'Relato': novo_relato
                                    }
                                    registrar_checkin(dados_followup, agend.get('Classificação', ''), respondeu="SIM" if novo_relato else "SEM_RESPOSTA")
                                    
                                    # ✅ NOVO: Detectar conversão
                                    try:
                                        valor_atual = float(agend.get('Valor', 0)) if pd.notna(agend.get('Valor', 0)) else 0
                                        compras_atual = int(agend.get('Compras', 0)) if pd.notna(agend.get('Compras', 0)) else 0
                                        detectar_conversao(agend.get('Nome', ''), valor_atual, compras_atual)
                                    except:
                                        pass  # Se falhar, não interrompe
                                    
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
                                    
                                    # ✅ NOVO: Registrar acompanhamento no LOG
                                    dados_acomp = {
                                        'Nome': ticket.get('Nome', ''),
                                        'Telefone': ticket.get('Telefone', ''),
                                        'Valor': ticket.get('Valor', 0),
                                        'Compras': ticket.get('Compras', 0),
                                        'Relato': novo_acompanhamento
                                    }
                                    registrar_checkin(dados_acomp, ticket.get('Classificação', ''), respondeu="SIM")
                                    
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
                                
                                # ✅ NOVO: Registrar finalização no LOG
                                dados_finalizacao = {
                                    'Nome': ticket.get('Nome', ''),
                                    'Telefone': ticket.get('Telefone', ''),
                                    'Valor': ticket.get('Valor', 0),
                                    'Compras': ticket.get('Compras', 0),
                                    'Relato': f"[SUPORTE FINALIZADO] {novo_acompanhamento if novo_acompanhamento else 'Ticket concluído'}"
                                }
                                registrar_checkin(dados_finalizacao, ticket.get('Classificação', ''), respondeu="SIM")
                                
                                # ✅ NOVO: Detectar conversão pós-suporte
                                try:
                                    valor_atual = float(ticket.get('Valor', 0)) if pd.notna(ticket.get('Valor', 0)) else 0
                                    compras_atual = int(ticket.get('Compras', 0)) if pd.notna(ticket.get('Compras', 0)) else 0
                                    detectar_conversao(ticket.get('Nome', ''), valor_atual, compras_atual)
                                except:
                                    pass  # Se falhar, não interrompe
                                
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
                            
                            # ✅ NOVO: Registrar criação do agendamento
                            dados_agend = {
                                'Nome': nome_cliente,
                                'Telefone': telefone_cliente,
                                'Valor': cliente.get('Valor', 0),
                                'Compras': cliente.get('Compras', 0),
                                'Relato': f"Agendamento criado: {motivo_agend}"
                            }
                            registrar_checkin(dados_agend, cliente.get('Classificação ', 'N/D'), respondeu="SEM_RESPOSTA")
                            
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
                            
                            # ✅ NOVO: Registrar abertura do ticket
                            dados_ticket = {
                                'Nome': nome_cliente,
                                'Telefone': telefone_cliente,
                                'Valor': cliente.get('Valor', 0),
                                'Compras': cliente.get('Compras', 0),
                                'Relato': f"[TICKET ABERTO] {assunto_suporte}: {descricao_suporte[:100]}"
                            }
                            registrar_checkin(dados_ticket, cliente.get('Classificação ', 'N/D'), respondeu="SIM")
                            
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
# DASHBOARD - ANÁLISES E MÉTRICAS
# ============================================================================

def render_dashboard():
    """Renderiza o Dashboard com análises e métricas do CRM"""
    
    st.title("📊 Dashboard de Análises")
    st.markdown("Visualize métricas, tendências e performance do CRM")
    st.markdown("---")
    
    # Abas do Dashboard
    aba_dash = st.tabs(["📊 Visão Geral", "📈 Performance", "🎯 Análises Avançadas"])
    
    # ========================================================================
    # ABA 1: VISÃO GERAL
    # ========================================================================
    with aba_dash[0]:
        st.subheader("📊 Visão Geral do Negócio")
        
        # Carregar dados necessários
        with st.spinner("Carregando dados..."):
            df_metricas = carregar_dados("HISTORICO_METRICAS")
            df_checkins = carregar_dados("LOG_CHECKINS")
            df_conversoes = carregar_dados("LOG_CONVERSOES")
            
            # Carregar todas as classificações
            df_novo = carregar_dados("Novo")
            df_promissor = carregar_dados("Promissor")
            df_leal = carregar_dados("Leal")
            df_campeao = carregar_dados("Campeão")
            df_risco = carregar_dados("Em risco")
            df_dormente = carregar_dados("Dormente")
        
        # ========== FILTRO GLOBAL ==========
        st.markdown("### 🔍 Filtros")
        
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            filtro_classificacao = st.selectbox(
                "📂 Classificação:",
                ["Todas", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
                help="Filtrar análises por classificação específica"
            )
        
        with col_f2:
            periodo_opcoes = ["Últimos 7 dias", "Últimos 15 dias", "Últimos 30 dias", "Todo período"]
            filtro_periodo = st.selectbox(
                "📅 Período:",
                periodo_opcoes,
                index=2
            )
        
        with col_f3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Atualizar Dados", use_container_width=True):
                carregar_dados.clear()
                st.rerun()
        
        st.markdown("---")
        
        # ========== MÉTRICA 2: TOTAL DE CLIENTES POR CLASSIFICAÇÃO + % CRESCIMENTO ==========
        st.markdown("### 👥 Total de Clientes por Classificação")
        
        # Calcular totais atuais
        totais = {
            'Novo': len(df_novo),
            'Promissor': len(df_promissor),
            'Leal': len(df_leal),
            'Campeão': len(df_campeao),
            'Em risco': len(df_risco),
            'Dormente': len(df_dormente)
        }
        
        total_geral = sum(totais.values())
        
        # Calcular crescimento (comparar com dia anterior se houver dados)
        crescimentos = {}
        if not df_metricas.empty and len(df_metricas) >= 2:
            ultima_linha = df_metricas.iloc[-1]
            penultima_linha = df_metricas.iloc[-2]
            
            crescimentos = {
                'Novo': calcular_percentual(penultima_linha.get('Total_Novo', 0), ultima_linha.get('Total_Novo', 0)),
                'Promissor': calcular_percentual(penultima_linha.get('Total_Promissor', 0), ultima_linha.get('Total_Promissor', 0)),
                'Leal': calcular_percentual(penultima_linha.get('Total_Leal', 0), ultima_linha.get('Total_Leal', 0)),
                'Campeão': calcular_percentual(penultima_linha.get('Total_Campeao', 0), ultima_linha.get('Total_Campeao', 0)),
                'Em risco': calcular_percentual(penultima_linha.get('Total_EmRisco', 0), ultima_linha.get('Total_EmRisco', 0)),
                'Dormente': calcular_percentual(penultima_linha.get('Total_Dormente', 0), ultima_linha.get('Total_Dormente', 0))
            }
        
        # Exibir métricas
        col_m1, col_m2, col_m3, col_m4, col_m5, col_m6 = st.columns(6)
        
        with col_m1:
            delta_novo = f"+{crescimentos.get('Novo', 0):.1f}%" if crescimentos.get('Novo', 0) > 0 else f"{crescimentos.get('Novo', 0):.1f}%" if crescimentos else None
            st.metric("🆕 Novo", totais['Novo'], delta=delta_novo)
        
        with col_m2:
            delta_prom = f"+{crescimentos.get('Promissor', 0):.1f}%" if crescimentos.get('Promissor', 0) > 0 else f"{crescimentos.get('Promissor', 0):.1f}%" if crescimentos else None
            st.metric("⭐ Promissor", totais['Promissor'], delta=delta_prom)
        
        with col_m3:
            delta_leal = f"+{crescimentos.get('Leal', 0):.1f}%" if crescimentos.get('Leal', 0) > 0 else f"{crescimentos.get('Leal', 0):.1f}%" if crescimentos else None
            st.metric("💙 Leal", totais['Leal'], delta=delta_leal)
        
        with col_m4:
            delta_camp = f"+{crescimentos.get('Campeão', 0):.1f}%" if crescimentos.get('Campeão', 0) > 0 else f"{crescimentos.get('Campeão', 0):.1f}%" if crescimentos else None
            st.metric("🏆 Campeão", totais['Campeão'], delta=delta_camp)
        
        with col_m5:
            delta_risco = f"+{crescimentos.get('Em risco', 0):.1f}%" if crescimentos.get('Em risco', 0) > 0 else f"{crescimentos.get('Em risco', 0):.1f}%" if crescimentos else None
            st.metric("⚠️ Em risco", totais['Em risco'], delta=delta_risco, delta_color="inverse")
        
        with col_m6:
            delta_dorm = f"+{crescimentos.get('Dormente', 0):.1f}%" if crescimentos.get('Dormente', 0) > 0 else f"{crescimentos.get('Dormente', 0):.1f}%" if crescimentos else None
            st.metric("😴 Dormente", totais['Dormente'], delta=delta_dorm, delta_color="inverse")
        
        # Gráfico de pizza
        st.markdown("#### 📊 Distribuição de Clientes")
        
        dados_pizza = {
            'Classificação': list(totais.keys()),
            'Quantidade': list(totais.values())
        }
        
        import plotly.express as px
        fig_pizza = px.pie(
            dados_pizza,
            values='Quantidade',
            names='Classificação',
            title=f'Total de Clientes: {total_geral}',
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_pizza.update_traces(textposition='inside', textinfo='percent+label+value')
        st.plotly_chart(fig_pizza, use_container_width=True)
        
        st.markdown("---")
        
        # ========== MÉTRICA 3: EVOLUÇÃO DE CHECK-INS POR DIA ==========
        st.markdown("### 📈 Evolução de Check-ins por Dia")
        
        if not df_checkins.empty and 'Data_Checkin' in df_checkins.columns:
            # Extrair apenas a data (remover hora)
            df_checkins['Data'] = pd.to_datetime(df_checkins['Data_Checkin'], format='%d/%m/%Y %H:%M', errors='coerce').dt.date
            
            # Agrupar por data
            checkins_por_dia = df_checkins.groupby('Data').size().reset_index(name='Check-ins')
            checkins_por_dia['Data'] = pd.to_datetime(checkins_por_dia['Data'])
            
            # Gráfico de linha
            fig_linha = px.line(
                checkins_por_dia,
                x='Data',
                y='Check-ins',
                title='Check-ins Realizados por Dia',
                markers=True
            )
            fig_linha.update_traces(line_color='#1f77b4', line_width=3)
            fig_linha.update_xaxes(title_text='Data')
            fig_linha.update_yaxes(title_text='Quantidade de Check-ins')
            st.plotly_chart(fig_linha, use_container_width=True)
            
            # Estatísticas
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            
            with col_stat1:
                st.metric("📊 Média Diária", f"{checkins_por_dia['Check-ins'].mean():.1f}")
            
            with col_stat2:
                st.metric("🔝 Dia com Mais", f"{checkins_por_dia['Check-ins'].max()}")
            
            with col_stat3:
                st.metric("📉 Dia com Menos", f"{checkins_por_dia['Check-ins'].min()}")
        else:
            st.info("📭 Nenhum check-in registrado ainda")
        
        st.markdown("---")
        
        # ========== MÉTRICA 4: TAXA DE CONVERSÃO DE ATENDIMENTOS ==========
        st.markdown("### 💰 Taxa de Conversão de Atendimentos")
        
        if not df_conversoes.empty and not df_checkins.empty:
            total_checkins = len(df_checkins)
            total_conversoes = len(df_conversoes)
            
            if total_checkins > 0:
                taxa_conversao = (total_conversoes / total_checkins) * 100
            else:
                taxa_conversao = 0
            
            col_conv1, col_conv2, col_conv3 = st.columns(3)
            
            with col_conv1:
                st.metric("✅ Total de Check-ins", total_checkins)
            
            with col_conv2:
                st.metric("💰 Conversões", total_conversoes)
            
            with col_conv3:
                st.metric("📊 Taxa de Conversão", f"{taxa_conversao:.1f}%")
            
            # Barra de progresso visual
            st.progress(min(taxa_conversao / 100, 1.0))
            
            if taxa_conversao >= 50:
                st.success(f"🎉 Excelente! Taxa de conversão de {taxa_conversao:.1f}%")
            elif taxa_conversao >= 30:
                st.info(f"👍 Boa taxa de conversão: {taxa_conversao:.1f}%")
            elif taxa_conversao >= 15:
                st.warning(f"⚠️ Taxa pode melhorar: {taxa_conversao:.1f}%")
            else:
                st.error(f"🔴 Taxa baixa: {taxa_conversao:.1f}% - Revise estratégias")
        else:
            st.info("📭 Dados insuficientes para calcular taxa de conversão")
        
        st.markdown("---")
        
        # ========== MÉTRICA 5: CLIENTES MAIS ATENDIDOS (POR CLASSIFICAÇÃO) ==========
        st.markdown("### 📞 Classificação Mais Atendida")
        
        if not df_checkins.empty and 'Classificacao_Cliente' in df_checkins.columns:
            atendimentos_por_class = df_checkins.groupby('Classificacao_Cliente').size().reset_index(name='Atendimentos')
            atendimentos_por_class = atendimentos_por_class.sort_values('Atendimentos', ascending=False)
            
            # Gráfico de barras
            fig_barras = px.bar(
                atendimentos_por_class,
                x='Classificacao_Cliente',
                y='Atendimentos',
                title='Quantidade de Atendimentos por Classificação',
                color='Atendimentos',
                color_continuous_scale='Blues'
            )
            fig_barras.update_xaxes(title_text='Classificação')
            fig_barras.update_yaxes(title_text='Quantidade de Atendimentos')
            st.plotly_chart(fig_barras, use_container_width=True)
            
            # Tabela detalhada
            st.dataframe(atendimentos_por_class, use_container_width=True, hide_index=True)
        else:
            st.info("📭 Nenhum atendimento registrado ainda")
        
        st.markdown("---")
        
        # ========== MÉTRICA 21: QUAL CLASSIFICAÇÃO GERA MAIS RESULTADO ==========
        st.markdown("### 💎 Classificação que Gera Mais Resultado")
        
        # Calcular valor total por classificação
        valores_por_class = {
            'Novo': df_novo['Valor'].sum() if 'Valor' in df_novo.columns and not df_novo.empty else 0,
            'Promissor': df_promissor['Valor'].sum() if 'Valor' in df_promissor.columns and not df_promissor.empty else 0,
            'Leal': df_leal['Valor'].sum() if 'Valor' in df_leal.columns and not df_leal.empty else 0,
            'Campeão': df_campeao['Valor'].sum() if 'Valor' in df_campeao.columns and not df_campeao.empty else 0,
            'Em risco': df_risco['Valor'].sum() if 'Valor' in df_risco.columns and not df_risco.empty else 0,
            'Dormente': df_dormente['Valor'].sum() if 'Valor' in df_dormente.columns and not df_dormente.empty else 0
        }
        
        df_valores = pd.DataFrame({
            'Classificação': list(valores_por_class.keys()),
            'Valor Total (R$)': list(valores_por_class.values())
        }).sort_values('Valor Total (R$)', ascending=False)
        
        # Calcular percentual de contribuição
        total_valor = df_valores['Valor Total (R$)'].sum()
        if total_valor > 0:
            df_valores['% Contribuição'] = (df_valores['Valor Total (R$)'] / total_valor * 100).round(1)
        else:
            df_valores['% Contribuição'] = 0
        
        # Gráfico de barras horizontal
        fig_resultado = px.bar(
            df_valores,
            y='Classificação',
            x='Valor Total (R$)',
            title=f'Valor Total por Classificação (Total: R$ {total_valor:,.2f})',
            orientation='h',
            color='Valor Total (R$)',
            color_continuous_scale='Greens',
            text='% Contribuição'
        )
        fig_resultado.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_resultado.update_xaxes(title_text='Valor Total (R$)')
        fig_resultado.update_yaxes(title_text='')
        st.plotly_chart(fig_resultado, use_container_width=True)
        
        # Tabela detalhada
        st.dataframe(df_valores, use_container_width=True, hide_index=True)
        
        # Insight
        if not df_valores.empty:
            melhor_class = df_valores.iloc[0]
            st.success(f"🏆 **{melhor_class['Classificação']}** é a classificação mais lucrativa com R$ {melhor_class['Valor Total (R$)']:,.2f} ({melhor_class['% Contribuição']:.1f}% do total)")
        
        st.markdown("---")
        
        # ========== DOWNLOAD CSV ==========
        st.markdown("### 💾 Exportar Dados")
        
        col_down1, col_down2 = st.columns(2)
        
        with col_down1:
            if not df_checkins.empty:
                csv_checkins = df_checkins.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Check-ins (CSV)",
                    data=csv_checkins,
                    file_name=f'checkins_{datetime.now().strftime("%Y%m%d")}.csv',
                    mime='text/csv',
                    use_container_width=True
                )
        
        with col_down2:
            if not df_conversoes.empty:
                csv_conversoes = df_conversoes.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Conversões (CSV)",
                    data=csv_conversoes,
                    file_name=f'conversoes_{datetime.now().strftime("%Y%m%d")}.csv',
                    mime='text/csv',
                    use_container_width=True
                )
    
    # ========================================================================
    # ABA 2: PERFORMANCE (Placeholder - próximo passo)
    # ========================================================================
    with aba_dash[1]:
        st.info("🚧 Aba de Performance em construção... Aguarde próxima atualização!")
    
    # ========================================================================
    # ABA 3: ANÁLISES AVANÇADAS (Placeholder - próximo passo)
    # ========================================================================
    with aba_dash[2]:
        st.info("🚧 Aba de Análises Avançadas em construção... Aguarde próxima atualização!")


# ============================================================================
# FUNÇÃO AUXILIAR PARA CÁLCULO DE PERCENTUAL
# ============================================================================

def calcular_percentual(valor_anterior, valor_atual):
    """Calcula percentual de crescimento entre dois valores"""
    if valor_anterior == 0:
        return 0
    return ((valor_atual - valor_anterior) / valor_anterior) * 100



# ============================================================================
# SIDEBAR E NAVEGAÇÃO
# ============================================================================

with st.sidebar:
    st.title("📋 Menu Principal")
    st.markdown("---")
    pagina = st.radio("Navegação", ["Check-in", "Em Atendimento", "Suporte", "Histórico", "📊 Dashboard"], index=0)
    st.markdown("---")
    st.caption("CRM Pós-Vendas v1.0")
  # No sidebar, após o botão de teste
st.markdown("---")
st.markdown("### ⏰ Rotinas Diárias")
st.caption("Executar manualmente (normalmente roda às 00h)")

if st.button("🔄 EXECUTAR ROTINAS DIÁRIAS", use_container_width=True):
    with st.spinner("Processando rotinas..."):
        executar_rotinas_diarias()
        time.sleep(2)
        st.rerun()
  

# ============================================================================
# ROTEAMENTO DE PÁGINAS (ADICIONAR AQUI!)
# ============================================================================

if pagina == "Check-in":
    render_checkin()
elif pagina == "Em Atendimento":
    render_em_atendimento()
elif pagina == "Suporte":
    render_suporte()
elif pagina == "Histórico":
    render_historico()
elif pagina == "📊 Dashboard":
    render_dashboard()


