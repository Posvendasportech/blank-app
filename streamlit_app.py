
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
        ano_atual = agora.strftime('%Y')
        
        # Gerar ID único no formato CHK-AAAA-NNNNN
        if df_log.empty or 'ID_Checkin' not in df_log.columns:
            numero_sequencial = 1
        else:
            # CONVERTER COLUNA PARA STRING
            df_log['ID_Checkin'] = df_log['ID_Checkin'].astype(str)
            
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
        
        # Resto do código continua igual
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
        import traceback
        st.code(traceback.format_exc())
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

def registrar_conversao(dados_cliente, valor_venda, origem="TOTAL_AUTOMATICO"):
    """
    Registra uma conversão (nova compra) na aba LOG_CONVERSOES.

    - dados_cliente: linha do cliente vinda da aba Total (Series do pandas)
    - valor_venda: apenas o valor da COMPRA nova (diferença entre hoje e ontem)
    - origem: texto para rastrear de onde veio a conversão (padrão: TOTAL_AUTOMATICO)
    """
    try:
        conn = get_gsheets_connection()
        df_conversoes = conn.read(worksheet="LOG_CONVERSOES", ttl=0)
        
        # Horário de Brasília
        timezone_brasilia = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(timezone_brasilia)
        ano_atual = agora.strftime('%Y')
        
        # Garantir que o DataFrame tem a coluna ID_Conversao
        if df_conversoes.empty:
            df_conversoes = pd.DataFrame(columns=[
                'ID_Conversao',
                'Data_Conversao',
                'Nome_Cliente',
                'Telefone',
                'Classificacao_Origem',
                'Valor_Venda',
                'Origem_Lead',
                'Dias_Ate_Conversao',
                'Criado_Por',
                'Hora_Registro'
            ])
        
        # Gerar ID único no formato CONV-AAAA-NNNNN
        if 'ID_Conversao' not in df_conversoes.columns or df_conversoes.empty:
            numero_sequencial = 1
        else:
            df_conversoes['ID_Conversao'] = df_conversoes['ID_Conversao'].astype(str)
            ids_ano_atual = df_conversoes[
                df_conversoes['ID_Conversao'].str.contains(f'CONV-{ano_atual}-', na=False)
            ]
            
            if len(ids_ano_atual) > 0:
                ultimos_numeros = ids_ano_atual['ID_Conversao'].str.extract(r'CONV-\d{4}-(\d{5})')[0]
                ultimo_numero = ultimos_numeros.astype(int).max()
                numero_sequencial = ultimo_numero + 1
            else:
                numero_sequencial = 1
        
        proximo_id = f"CONV-{ano_atual}-{numero_sequencial:05d}"
        
        # Tentar calcular dias até conversão usando "Data de contato" se existir
        dias_ate_conversao = ""
        data_contato_str = str(dados_cliente.get('Data de contato', '') or '')
        if data_contato_str:
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d']:
                try:
                    data_contato = datetime.strptime(data_contato_str, fmt)
                    dias_ate_conversao = (agora - data_contato).days
                    break
                except:
                    continue
        
        # Obter classificação de origem com fallback de nomes de coluna
        classificacao_origem = dados_cliente.get('Classificação', dados_cliente.get('Classificacao', ''))
        
        # Preparar linha da conversão
        nova_conversao = {
            'ID_Conversao': proximo_id,
            'Data_Conversao': agora.strftime('%d/%m/%Y'),
            'Nome_Cliente': dados_cliente.get('Nome', ''),
            'Telefone': dados_cliente.get('Telefone', ''),
            'Classificacao_Origem': classificacao_origem,
            'Valor_Venda': float(valor_venda) if valor_venda is not None else 0,
            'Origem_Lead': origem,
            'Dias_Ate_Conversao': dias_ate_conversao,
            'Criado_Por': 'CRM',
            'Hora_Registro': agora.strftime('%H:%M:%S')
        }
        
        # Adicionar no DataFrame e salvar na planilha
        df_conversoes_novo = pd.concat(
            [df_conversoes, pd.DataFrame([nova_conversao])],
            ignore_index=True
        )
        conn.update(worksheet="LOG_CONVERSOES", data=df_conversoes_novo)
        
        return proximo_id
    
    except Exception as e:
        st.error(f"Erro ao registrar conversão: {e}")
        return None

def gerar_snapshot_diario(data_especifica=None):
    """Gera snapshot de todas as métricas do dia e salva em HISTORICO_METRICAS"""
    try:
        timezone_brasilia = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(timezone_brasilia)
        
        if data_especifica:
            data_snapshot = data_especifica
        else:
            data_snapshot = agora.strftime('%d/%m/%Y')
        
        conn = get_gsheets_connection()
        
        # Carregar abas de clientes
        df_novo = conn.read(worksheet="Novo", ttl=0)
        df_promissor = conn.read(worksheet="Promissor", ttl=0)
        df_leal = conn.read(worksheet="Leal", ttl=0)
        df_campeao = conn.read(worksheet="Campeão", ttl=0)
        df_emrisco = conn.read(worksheet="Em risco", ttl=0)
        df_dormente = conn.read(worksheet="Dormente", ttl=0)
        df_total = conn.read(worksheet="Total", ttl=0)
        
        # Outras abas operacionais
        df_log_checkins = conn.read(worksheet="LOG_CHECKINS", ttl=0)
        df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
        df_historico = conn.read(worksheet="HISTORICO", ttl=0)
        df_suporte = conn.read(worksheet="SUPORTE", ttl=0)
        df_conversoes = conn.read(worksheet="LOG_CONVERSOES", ttl=0)
        
        # Totais de clientes por classificação
        total_novo = len(df_novo)
        total_promissor = len(df_promissor)
        total_leal = len(df_leal)
        total_campeao = len(df_campeao)
        total_emrisco = len(df_emrisco)
        total_dormente = len(df_dormente)
        total_clientes = len(df_total)
        
        # Check-ins do dia
        checkins_realizados = 0
        if not df_log_checkins.empty and 'Data_Checkin' in df_log_checkins.columns:
            checkins_realizados = len(df_log_checkins[df_log_checkins['Data_Checkin'] == data_snapshot])
        
        # Meta do dia (do session_state, se for o dia atual)
        meta_dia = 0
        if 'metas_checkin' in st.session_state and data_snapshot == agora.strftime('%d/%m/%Y'):
            meta_dia = sum(st.session_state.metas_checkin.values())
        
        # Agendamentos criados no dia (baseado na data de contato)
        agendamentos_criados = 0
        if not df_agendamentos.empty and 'Data de contato' in df_agendamentos.columns:
            agendamentos_criados = len(df_agendamentos[df_agendamentos['Data de contato'] == data_snapshot])
        
        # Agendamentos concluídos no dia (HISTORICO)
        agendamentos_concluidos = 0
        if not df_historico.empty and 'Data de conclusão' in df_historico.columns:
            df_hist_temp = df_historico.copy()
            df_hist_temp['Data_Simples'] = df_hist_temp['Data de conclusão'].astype(str).str[:10]
            agendamentos_concluidos = len(df_hist_temp[df_hist_temp['Data_Simples'] == data_snapshot])
        
        # Tickets abertos no dia (SUPORTE)
        tickets_abertos = 0
        if not df_suporte.empty and 'Data de abertura' in df_suporte.columns:
            tickets_abertos = len(df_suporte[df_suporte['Data de abertura'] == data_snapshot])
        
        # Tickets pendentes (total atual em SUPORTE)
        tickets_pendentes = len(df_suporte)
        
        # Tickets resolvidos no dia – para funcionar bem, ideal ter uma coluna "Data_Resolucao" em SUPORTE no futuro
        tickets_resolvidos = 0  # por enquanto fica 0 até definirmos a lógica
        
                # ========== DETECTAR CONVERSÕES AUTOMÁTICAS ==========
        st.subheader("🤖 Detecção automática de conversões")
        conversoes_automaticas = detectar_e_registrar_conversoes_automaticas()
        
        # Agora recarregar LOG_CONVERSOES para pegar as recém-criadas
        df_conversoes = conn.read(worksheet="LOG_CONVERSOES", ttl=0)
        
        # Conversões do dia (LOG_CONVERSOES)
        conversoes_dia = 0
        if not df_conversoes.empty and 'Data_Conversao' in df_conversoes.columns:
            conversoes_dia = len(df_conversoes[df_conversoes['Data_Conversao'] == data_snapshot])

        
        snapshot = {
            'Data': data_snapshot,
            'Total_Novo': total_novo,
            'Total_Promissor': total_promissor,
            'Total_Leal': total_leal,
            'Total_Campeao': total_campeao,
            'Total_EmRisco': total_emrisco,
            'Total_Dormente': total_dormente,
            'Total_Clientes': total_clientes,
            'CheckIns_Realizados': checkins_realizados,
            'Meta_Dia': meta_dia,
            'Agendamentos_Criados': agendamentos_criados,
            'Agendamentos_Concluidos': agendamentos_concluidos,
            'Tickets_Abertos': tickets_abertos,
            'Tickets_Resolvidos': tickets_resolvidos,
            'Tickets_Pendentes': tickets_pendentes,
            'Conversoes_Dia': conversoes_dia
        }
        
        df_metricas = conn.read(worksheet="HISTORICO_METRICAS", ttl=0)
        
        # Remove snapshot antigo do mesmo dia, se existir
        if not df_metricas.empty and 'Data' in df_metricas.columns:
            df_metricas = df_metricas[df_metricas['Data'] != data_snapshot]
        
        df_metricas_novo = pd.concat([df_metricas, pd.DataFrame([snapshot])], ignore_index=True)
        conn.update(worksheet="HISTORICO_METRICAS", data=df_metricas_novo)
        
        st.success(f"✅ Snapshot gerado para {data_snapshot}!")
        return True
        
    except Exception as e:
        st.error(f"Erro ao gerar snapshot: {e}")
        import traceback
        st.code(traceback.format_exc())
        return False


def detectar_e_registrar_conversoes_automaticas():
    """
    Detecta conversões automaticamente usando a aba PEDIDOS da Shopify.
    Filtra pedidos de hoje e verifica se o cliente passou pelo CRM.
    """
    try:
        conn = get_gsheets_connection()
        
        # Horário de Brasília
        timezone_brasilia = pytz.timezone('America/Sao_Paulo')
        hoje = datetime.now(timezone_brasilia)
        hoje_str = hoje.strftime('%d/%m/%Y')
        
        st.info(f"🔍 Buscando pedidos de hoje ({hoje_str})...")
        
        # Ler aba PEDIDOS
        df_pedidos = conn.read(worksheet="PEDIDOS", ttl=0)
        
        if df_pedidos.empty:
            st.warning("⚠️ Aba PEDIDOS está vazia")
            return 0
        
        # Verificar colunas necessárias
        if 'Data' not in df_pedidos.columns or 'Telefone' not in df_pedidos.columns:
            st.error("❌ Aba PEDIDOS precisa ter colunas 'Data' e 'Telefone'")
            return 0
        
        # Filtrar pedidos de hoje
        # A coluna Data vem como datetime do Google Sheets
        df_pedidos['Data_Formatada'] = pd.to_datetime(df_pedidos['Data'], errors='coerce').dt.strftime('%d/%m/%Y')
        df_pedidos_hoje = df_pedidos[df_pedidos['Data_Formatada'] == hoje_str].copy()
        
        if df_pedidos_hoje.empty:
            st.info(f"✅ Nenhum pedido encontrado para hoje ({hoje_str})")
            return 0
        
        st.success(f"📦 {len(df_pedidos_hoje)} pedido(s) encontrado(s) hoje")
        
        # Carregar abas do CRM
        df_checkins = conn.read(worksheet="LOG_CHECKINS", ttl=0)
        df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
        df_historico = conn.read(worksheet="HISTORICO", ttl=0)
        df_conversoes = conn.read(worksheet="LOG_CONVERSOES", ttl=0)
        
        # Criar dicionário de telefones do CRM com origem
        telefones_crm = {}
        
        if not df_checkins.empty and 'Telefone' in df_checkins.columns:
            for tel in df_checkins['Telefone'].dropna():
                tel_limpo = str(tel).strip()
                if tel_limpo:
                    telefones_crm[tel_limpo] = "Check-in"
        
        if not df_agendamentos.empty and 'Telefone' in df_agendamentos.columns:
            for tel in df_agendamentos['Telefone'].dropna():
                tel_limpo = str(tel).strip()
                if tel_limpo:
                    telefones_crm[tel_limpo] = "Atendimento Ativo"
        
        if not df_historico.empty and 'Telefone' in df_historico.columns:
            for tel in df_historico['Telefone'].dropna():
                tel_limpo = str(tel).strip()
                if tel_limpo:
                    telefones_crm[tel_limpo] = "Histórico"
        
        # Criar lista de números de pedidos já convertidos (evitar duplicatas)
        numeros_ja_convertidos = set()
        if not df_conversoes.empty and 'Numero_do_pedido' in df_conversoes.columns:
            numeros_ja_convertidos = set(df_conversoes['Numero_do_pedido'].dropna().astype(str).tolist())
        
        conversoes_detectadas = 0
        
        # Verificar cada pedido de hoje
        for idx, pedido in df_pedidos_hoje.iterrows():
            numero_pedido = str(pedido.get('Numero_do_pedido', ''))
            telefone = str(pedido.get('Telefone', '')).strip()
            
            # Pular se não tem telefone ou já foi convertido
            if not telefone:
                continue
            
            if numero_pedido in numeros_ja_convertidos:
                continue
            
            # Verificar se cliente passou pelo CRM
            if telefone in telefones_crm:
                # É CONVERSÃO DO CRM!
                origem = telefones_crm[telefone]
                
                # Preparar dados do cliente
                dados_cliente = {
                    'Nome': pedido.get('Nome_Cliente', ''),
                    'Telefone': telefone,
                    'Email': pedido.get('Email', ''),
                    'Classificação': '',  # não temos no pedido
                    'Data de contato': ''  # não temos no pedido
                }
                
                valor_pedido = float(pedido.get('Valor_Pedido', 0) or 0)
                
                # Registrar conversão
                id_conv = registrar_conversao(
                    dados_cliente=dados_cliente,
                    valor_venda=valor_pedido,
                    origem=origem
                )
                
                if id_conv:
                    # Adicionar número do pedido na conversão para evitar duplicatas
                    df_conv_atualizado = conn.read(worksheet="LOG_CONVERSOES", ttl=0)
                    df_conv_atualizado.loc[df_conv_atualizado['ID_Conversao'] == id_conv, 'Numero_do_pedido'] = numero_pedido
                    conn.update(worksheet="LOG_CONVERSOES", data=df_conv_atualizado)
                    
                    conversoes_detectadas += 1
                    st.success(
                        f"✅ Conversão CRM: {dados_cliente['Nome']} - "
                        f"R$ {valor_pedido:.2f} - Pedido #{numero_pedido} ({origem})"
                    )
        
        if conversoes_detectadas == 0:
            st.info("✅ Nenhuma conversão nova de clientes do CRM detectada nos pedidos de hoje")
        else:
            st.success(f"🎉 {conversoes_detectadas} conversão(ões) do CRM registrada(s)!")
        
        return conversoes_detectadas
    
    except Exception as e:
        st.error(f"Erro ao detectar conversões: {e}")
        import traceback
        st.code(traceback.format_exc())
        return 0
def registrar_ticket_aberto(dados_cliente, tipo_problema, prioridade, descricao, aberto_por="CRM"):
    """Registra abertura de ticket na aba LOG_TICKETS_ABERTOS"""
    try:
        conn = get_gsheets_connection()
        df_log_tickets = conn.read(worksheet="LOG_TICKETS_ABERTOS", ttl=0)
        
        # Horário de Brasília
        timezone_brasilia = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(timezone_brasilia)
        ano_atual = agora.strftime('%Y')
        
        # Gerar ID único no formato TKT-AAAA-NNNNN
        if df_log_tickets.empty or 'ID_Ticket' not in df_log_tickets.columns:
            numero_sequencial = 1
        else:
            df_log_tickets['ID_Ticket'] = df_log_tickets['ID_Ticket'].astype(str)
            ids_ano_atual = df_log_tickets[
                df_log_tickets['ID_Ticket'].str.contains(f'TKT-{ano_atual}-', na=False)
            ]
            
            if len(ids_ano_atual) > 0:
                ultimos_numeros = ids_ano_atual['ID_Ticket'].str.extract(r'TKT-\d{4}-(\d{5})')[0]
                ultimo_numero = ultimos_numeros.astype(int).max()
                numero_sequencial = ultimo_numero + 1
            else:
                numero_sequencial = 1
        
        id_ticket = f"TKT-{ano_atual}-{numero_sequencial:05d}"
        
        # Traduzir dia da semana
        dia_semana = agora.strftime('%A')
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
        
        # Preparar linha
        novo_ticket = {
            'ID_Ticket': id_ticket,
            'Data_Abertura': agora.strftime('%d/%m/%Y'),
            'Hora_Abertura': agora.strftime('%H:%M:%S'),
            'Nome_Cliente': dados_cliente.get('Nome', ''),
            'Telefone': dados_cliente.get('Telefone', ''),
            'Classificacao_Cliente': dados_cliente.get('Classificação', dados_cliente.get('Classificacao', '')),
            'Tipo_Problema': tipo_problema,
            'Prioridade': prioridade,
            'Descricao_Resumida': descricao[:200] if descricao else '',
            'Aberto_Por': aberto_por,
            'Dia_Semana': dia_semana
        }
        
        # Adicionar
        df_novo = pd.concat([df_log_tickets, pd.DataFrame([novo_ticket])], ignore_index=True)
        conn.update(worksheet="LOG_TICKETS_ABERTOS", data=df_novo)
        
        return id_ticket
    
    except Exception as e:
        st.error(f"Erro ao registrar ticket aberto: {e}")
        return None

def registrar_ticket_resolvido(id_ticket, dados_cliente, data_abertura, tipo_problema, prioridade, 
                                como_resolvido, resultado_final, gerou_conversao=False, resolvido_por="CRM"):
    """Registra resolução de ticket na aba LOG_TICKETS_RESOLVIDOS"""
    try:
        conn = get_gsheets_connection()
        df_log_resolvidos = conn.read(worksheet="LOG_TICKETS_RESOLVIDOS", ttl=0)
        
        # Horário de Brasília
        timezone_brasilia = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(timezone_brasilia)
        data_resolucao = agora.strftime('%d/%m/%Y')
        
        # Calcular tempo de resolução em horas
        tempo_resolucao_horas = ""
        if data_abertura:
            try:
                # Tentar converter data de abertura
                for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d/%m/%Y %H:%M:%S']:
                    try:
                        dt_abertura = datetime.strptime(str(data_abertura)[:10], fmt[:10])
                        diferenca = agora - dt_abertura
                        tempo_resolucao_horas = round(diferenca.total_seconds() / 3600, 1)
                        break
                    except:
                        continue
            except:
                tempo_resolucao_horas = ""
        
        # Preparar linha
        ticket_resolvido = {
            'ID_Ticket': id_ticket,
            'Data_Abertura': data_abertura if data_abertura else '',
            'Data_Resolucao': data_resolucao,
            'Tempo_Resolucao_Horas': tempo_resolucao_horas,
            'Nome_Cliente': dados_cliente.get('Nome', ''),
            'Telefone': dados_cliente.get('Telefone', ''),
            'Tipo_Problema': tipo_problema,
            'Prioridade': prioridade,
            'Como_Foi_Resolvido': como_resolvido[:200] if como_resolvido else '',
            'Resultado_Final': resultado_final,
            'Gerou_Conversao': 'SIM' if gerou_conversao else 'NÃO',
            'Resolvido_Por': resolvido_por
        }
        
        # Adicionar
        df_novo = pd.concat([df_log_resolvidos, pd.DataFrame([ticket_resolvido])], ignore_index=True)
        conn.update(worksheet="LOG_TICKETS_RESOLVIDOS", data=df_novo)
        
        return True
    
    except Exception as e:
        st.error(f"Erro ao registrar ticket resolvido: {e}")
        return False


# ============================================================================
# RENDER - PÁGINA CHECK-IN (VERSÃO OTIMIZADA)
# ============================================================================

def render_checkin():
    """Renderiza a página de Check-in - COMPLETA + OTIMIZADA"""

    # ---------------- SESSION STATE ----------------
    if 'metas_checkin' not in st.session_state:
        st.session_state.metas_checkin = {
            'novo': 5,
            'promissor': 5,
            'leal': 5,
            'campeao': 3,
            'risco': 5,
            'dormente': 5,
        }
    if 'metas_alteradas' not in st.session_state:
        st.session_state.metas_alteradas = False
    if 'ultima_verificacao' not in st.session_state:
        st.session_state.ultima_verificacao = 0
    if 'clientes_excluir' not in st.session_state:
        st.session_state.clientes_excluir = set()

    st.title("✅ Check-in de Clientes")
    st.markdown("Selecione clientes para iniciar o fluxo de atendimento")
    st.markdown("---")

    # ---------------- PAINEL DE PLANEJAMENTO ----------------
    st.subheader("📊 Planejamento de Check-ins do Dia")

    with st.expander("🎯 Definir Metas de Check-in por Classificação", expanded=True):
        st.write("**Defina quantos clientes de cada grupo você quer contatar hoje:**")

        col_meta1, col_meta2, col_meta3 = st.columns(3)

        with col_meta1:
            meta_novo = st.number_input(
                "🆕 Novo", 0, 50, st.session_state.metas_checkin['novo'],
                1, key='input_meta_novo', help="Meta de clientes novos"
            )
            if meta_novo != st.session_state.metas_checkin['novo']:
                st.session_state.metas_checkin['novo'] = meta_novo
                st.session_state.metas_alteradas = True

            meta_promissor = st.number_input(
                "⭐ Promissor", 0, 50, st.session_state.metas_checkin['promissor'],
                1, key='input_meta_promissor', help="Meta de clientes promissores"
            )
            if meta_promissor != st.session_state.metas_checkin['promissor']:
                st.session_state.metas_checkin['promissor'] = meta_promissor
                st.session_state.metas_alteradas = True

        with col_meta2:
            meta_leal = st.number_input(
                "💙 Leal", 0, 50, st.session_state.metas_checkin['leal'],
                1, key='input_meta_leal', help="Meta de clientes leais"
            )
            if meta_leal != st.session_state.metas_checkin['leal']:
                st.session_state.metas_checkin['leal'] = meta_leal
                st.session_state.metas_alteradas = True

            meta_campeao = st.number_input(
                "🏆 Campeão", 0, 50, st.session_state.metas_checkin['campeao'],
                1, key='input_meta_campeao', help="Meta de clientes campeões"
            )
            if meta_campeao != st.session_state.metas_checkin['campeao']:
                st.session_state.metas_checkin['campeao'] = meta_campeao
                st.session_state.metas_alteradas = True

        with col_meta3:
            meta_risco = st.number_input(
                "⚠️ Em risco", 0, 50, st.session_state.metas_checkin['risco'],
                1, key='input_meta_risco', help="Meta de clientes em risco"
            )
            if meta_risco != st.session_state.metas_checkin['risco']:
                st.session_state.metas_checkin['risco'] = meta_risco
                st.session_state.metas_alteradas = True

            meta_dormente = st.number_input(
                "😴 Dormente", 0, 50, st.session_state.metas_checkin['dormente'],
                1, key='input_meta_dormente', help="Meta de clientes dormentes"
            )
            if meta_dormente != st.session_state.metas_checkin['dormente']:
                st.session_state.metas_checkin['dormente'] = meta_dormente
                st.session_state.metas_alteradas = True

        meta_total = (
            meta_novo + meta_promissor + meta_leal +
            meta_campeao + meta_risco + meta_dormente
        )

        col_info1, col_info2 = st.columns([2, 1])
        with col_info1:
            st.info(f"🎯 **Meta Total do Dia:** {meta_total} check-ins")
        with col_info2:
            if st.session_state.metas_alteradas:
                st.success("✅ Metas salvas!")
                st.session_state.metas_alteradas = False

    st.markdown("---")

        # ========== BARRA DE PROGRESSO (COMPLETA) ==========
    st.subheader("📈 Progresso do Dia")

    # 1) Meta total do dia (a partir das metas salvas)
    meta_total = (
        st.session_state.metas_checkin['novo']
        + st.session_state.metas_checkin['promissor']
        + st.session_state.metas_checkin['leal']
        + st.session_state.metas_checkin['campeao']
        + st.session_state.metas_checkin['risco']
        + st.session_state.metas_checkin['dormente']
    )

    # 2) Check-ins realizados hoje (AGENDAMENTOS_ATIVOS → Data de contato)
    df_agendamentos_hoje = carregar_dados("AGENDAMENTOS_ATIVOS")
    hoje_str = datetime.now().strftime('%d/%m/%Y')

    if (
        not df_agendamentos_hoje.empty
        and 'Data de contato' in df_agendamentos_hoje.columns
    ):
        datas_contato = df_agendamentos_hoje['Data de contato'].astype(str)
        checkins_hoje = int((datas_contato == hoje_str).sum())
    else:
        checkins_hoje = 0

    # 3) Cálculo de progresso
    if meta_total > 0:
        progresso = min(checkins_hoje / meta_total, 1.0)
        percentual = int(progresso * 100)
    else:
        progresso = 0.0
        percentual = 0

    # 4) Texto motivacional
    frases_motivacao = {
        0: "🚀 Vamos começar! Todo grande resultado começa com o primeiro passo!",
        25: "💪 Ótimo começo! Continue assim e você vai longe!",
        50: "🔥 Você está no meio do caminho! Não pare agora!",
        75: "⭐ Incrível! Você está quase lá, finalize com chave de ouro!",
        100: "🎉 PARABÉNS! Meta do dia alcançada! Você é CAMPEÃO! 🏆",
    }
    chave_frase = min((percentual // 25) * 25, 100)
    frase = frases_motivacao.get(chave_frase, frases_motivacao[0])

    # 5) UI
    col_prog1, col_prog2, col_prog3 = st.columns([1, 2, 1])

    with col_prog1:
        st.metric(
            label="✅ Check-ins Hoje",
            value=checkins_hoje,
            delta=f"{checkins_hoje}/{meta_total}" if meta_total > 0 else None,
        )

    with col_prog2:
        st.progress(progresso)
        st.markdown(f"**{percentual}% da meta alcançada**")
        if percentual >= 100:
            st.success(frase)
        elif percentual >= 50:
            st.info(frase)
        else:
            st.warning(frase)

    with col_prog3:
        faltam = max(0, meta_total - checkins_hoje)
        st.metric("🎯 Meta do Dia", meta_total, f"Faltam {faltam}")

    # ---------------- CONFIGURAÇÕES DE FILTRO ----------------
    col_config1, col_config2 = st.columns([2, 1])
    with col_config1:
        classificacoes = ["Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"]
        classificacao_selecionada = st.selectbox(
            "📂 Escolha a classificação:",
            classificacoes,
            index=0
        )
    with col_config2:
        metas_por_classificacao = {
            "Novo": st.session_state.metas_checkin['novo'],
            "Promissor": st.session_state.metas_checkin['promissor'],
            "Leal": st.session_state.metas_checkin['leal'],
            "Campeão": st.session_state.metas_checkin['campeao'],
            "Em risco": st.session_state.metas_checkin['risco'],
            "Dormente": st.session_state.metas_checkin['dormente'],
        }
        meta_classificacao = metas_por_classificacao.get(classificacao_selecionada, 0)
        st.info(
            f"📊 Meta para '{classificacao_selecionada}': "
            f"**{meta_classificacao}** check-ins hoje"
        )

    st.markdown("---")

    # ---------------- VERIFICAÇÃO 1x POR MINUTO ----------------
    agora_ts = time.time()
    if agora_ts - st.session_state.ultima_verificacao > 60:
        with st.status("🔄 Atualizando filtros...", expanded=False):
            df_agendamentos_ativos = carregar_dados("AGENDAMENTOS_ATIVOS")
            df_log_checkins = carregar_dados("LOG_CHECKINS")
            hoje_br = datetime.now(pytz.timezone('America/Sao_Paulo')).strftime('%d/%m/%Y')

            st.session_state.clientes_excluir = set()

            if not df_agendamentos_ativos.empty and 'Nome' in df_agendamentos_ativos.columns:
                st.session_state.clientes_excluir.update(
                    df_agendamentos_ativos['Nome'].tolist()
                )

            if (
                not df_log_checkins.empty
                and 'Nome_Cliente' in df_log_checkins.columns
                and 'Data_Checkin' in df_log_checkins.columns
            ):
                hoje_checkins = df_log_checkins[
                    df_log_checkins['Data_Checkin'] == hoje_br
                ]['Nome_Cliente'].tolist()
                st.session_state.clientes_excluir.update(hoje_checkins)

            st.session_state.ultima_verificacao = agora_ts
            st.toast("✅ Filtros atualizados!", icon="🔄")

    # ---------------- CARREGAR CLIENTES DA CLASSIFICAÇÃO ----------------
    df_clientes = carregar_dados(classificacao_selecionada)
    if df_clientes.empty:
        st.warning(f"⚠️ Nenhum cliente em '{classificacao_selecionada}'")
        return

    # limitar lista de trabalho pela meta da classificação
    if meta_classificacao > 0:
        df_clientes = df_clientes.head(meta_classificacao)

    # remover já processados (em atendimento ou já fizeram check-in hoje)
    df_filtrado = df_clientes[
        ~df_clientes['Nome'].isin(st.session_state.clientes_excluir)
    ]

    if len(df_filtrado) == 0:
        st.success(f"✅ Todos os clientes de '{classificacao_selecionada}' já foram check-in!")
        st.info("👉 Vá para '📞 Em Atendimento'")
        return

    # ---------------- FILTROS RÁPIDOS ----------------
    col_info, col_busca, col_dias = st.columns([1, 2, 2])

    with col_info:
        st.metric("✅ Disponíveis", len(df_filtrado))

    with col_busca:
        busca_nome = st.text_input(
            "🔍 Buscar:",
            placeholder="Nome...",
            label_visibility="collapsed"
        )

    with col_dias:
        if 'Dias desde a compra' in df_filtrado.columns:
            max_bruto = pd.to_numeric(
                df_filtrado['Dias desde a compra'],
                errors='coerce'
            ).max()
            if pd.isna(max_bruto):
                max_bruto = 0

            if classificacao_selecionada in ["Em risco", "Dormente"]:
                dias_min = 0
                dias_max = max(730, int(max_bruto))
            else:
                dias_min = 0
                dias_max = int(max_bruto)
                if dias_max <= 0:
                    dias_max = 365

            filtro_dias = st.slider(
                "📅 Dias:",
                dias_min,
                dias_max,
                (dias_min, dias_max),
                label_visibility="collapsed"
            )
        else:
            filtro_dias = None

    if busca_nome and 'Nome' in df_filtrado.columns:
        df_filtrado = df_filtrado[
            df_filtrado['Nome'].str.contains(busca_nome, case=False, na=False)
        ]

    if (
        filtro_dias
        and 'Dias desde a compra' in df_filtrado.columns
        and classificacao_selecionada not in ["Em risco", "Dormente"]
    ):
        dias_num = pd.to_numeric(
            df_filtrado['Dias desde a compra'],
            errors='coerce'
        )
        df_filtrado = df_filtrado[
            (dias_num >= filtro_dias[0]) &
            (dias_num <= filtro_dias[1])
        ]

    st.markdown("---")
    st.subheader(f"📋 Clientes para Check-in ({len(df_filtrado)})")

    # ---------------- CARDS DE CLIENTES ----------------
    for index, cliente in df_filtrado.iterrows():
        nome_cliente = cliente.get('Nome', 'N/D')
        try:
            valor_formatado = f"R$ {float(cliente.get('Valor', 0)):.2f}"
        except Exception:
            valor_formatado = "R$ 0,00"

        with st.expander(f"👤 {nome_cliente} | 💰 {valor_formatado}", expanded=False):
            col_info_card, col_form = st.columns([1, 1])

            with col_info_card:
                st.markdown("### 📊 Informações do Cliente")
                st.write(f"**📱** {cliente.get('Telefone', 'N/D')}")
                st.write(f"**📧** {cliente.get('Email', 'N/D')}")
                st.write(f"**🏷️** {classificacao_selecionada}")

            with col_form:
                if st.button(
                    "❌ Não Respondeu",
                    key=f"nao_{index}",
                    type="secondary",
                    use_container_width=True
                ):
                    id_checkin = registrar_log_checkin(
                        cliente,
                        classificacao_selecionada,
                        "NÃO RESPONDEU",
                        "Cliente não respondeu",
                        "CRM"
                    )
                    st.session_state.clientes_excluir.add(nome_cliente)
                    st.success(f"✅ {id_checkin} registrado!")
                    st.toast("Card removido ➡️", icon="✅")
                    st.rerun()

                with st.form(key=f"checkin_{index}"):
                    conversa = st.text_area("📝 Conversa:", height=100)
                    proximo = st.text_input("🎯 Próximo:")
                    data_prox = st.date_input("📅 Data:")

                    if st.form_submit_button(
                        "✅ Check-in",
                        type="primary",
                        use_container_width=True
                    ):
                        if conversa and proximo:
                            with st.status("💾 Salvando...", expanded=False):
                                conn = get_gsheets_connection()
                                df_agend = conn.read(
                                    worksheet="AGENDAMENTOS_ATIVOS",
                                    ttl=0
                                )
                                nova_linha = {
                                    'Data de contato': datetime.now().strftime('%d/%m/%Y'),
                                    'Nome': nome_cliente,
                                    'Classificação': classificacao_selecionada,
                                    'Valor': cliente.get('Valor', ''),
                                    'Telefone': cliente.get('Telefone', ''),
                                    'Relato da conversa': conversa,
                                    'Follow up': proximo,
                                    'Data de chamada': data_prox.strftime('%d/%m/%Y') if data_prox else '',
                                    'Observação': 'Check-in via CRM'
                                }
                                df_novo = pd.concat(
                                    [df_agend, pd.DataFrame([nova_linha])],
                                    ignore_index=True
                                )
                                conn.update(
                                    worksheet="AGENDAMENTOS_ATIVOS",
                                    data=df_novo
                                )

                                id_checkin = registrar_log_checkin(
                                    cliente,
                                    classificacao_selecionada,
                                    "SIM",
                                    conversa[:200],
                                    "CRM"
                                )

                                st.session_state.clientes_excluir.add(nome_cliente)
                                st.success(
                                    f"✅ Check-in #{id_checkin} ➡️ AGENDAMENTOS_ATIVOS"
                                )
                                st.toast(
                                    "Cliente em '📞 Em Atendimento' ➡️",
                                    icon="✅"
                                )
                                st.rerun()
                        else:
                            st.error("❌ Preencha conversa + próximo contato!")


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
        st.metric(
            "🔥 Vencidos",
            total_vencidos,
            delta=f"-{total_vencidos}" if total_vencidos > 0 else "0",
            delta_color="inverse",
            help="Atendimentos de dias anteriores não concluídos"
        )

    # Alerta de vencidos
    if total_vencidos > 0:
        st.error(
            f"⚠️ **ATENÇÃO:** Você tem {total_vencidos} atendimento(s) vencido(s) de dias anteriores! Priorize-os."
        )

    st.markdown("---")

    # ========== FILTROS ==========
    st.subheader("🔍 Filtros")

    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
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

    # Aplicar filtros (fora do with col_f3)
    df_filt = df_trabalho.copy()

    if busca and 'Nome' in df_filt.columns:
        df_filt = df_filt[df_filt['Nome'].str.contains(busca, case=False, na=False)]

    if filtro_class != 'Todos' and 'Classificação' in df_filt.columns:
        df_filt = df_filt[df_filt['Classificação'] == filtro_class]

    # ATENÇÃO: filtro_prioridade precisa existir nessa função, senão dá NameError (variável não definida) [web:71].
    # Se você não tiver o selectbox de prioridade aqui, defina um default:
    # filtro_prioridade = 'Todas'
    if filtro_prioridade != 'Todas' and 'Prioridade' in df_filt.columns:
        df_filt = df_filt[df_filt['Prioridade'] == filtro_prioridade]

    st.markdown("---")



    # ====== AGRUPAR POR CLIENTE (1 CARD POR PESSOA) ======
    if not df_filt.empty:
        # se existir coluna de data, ordenar para pegar a última atualização
        if 'Data de atualização' in df_filt.columns:
            df_filt = df_filt.sort_values('Data de atualização')
        # agrupar por telefone (mais seguro)
        if 'Telefone' in df_filt.columns:
            df_filt = df_filt.drop_duplicates(subset=['Telefone'], keep='last')
        # fallback: se por acaso não tiver telefone, agrupa por nome
        elif 'Nome' in df_filt.columns:
            df_filt = df_filt.drop_duplicates(subset=['Nome'], keep='last')

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
                data_chamada_dt = None
                try:
                    data_chamada_dt = datetime.strptime(data_chamada_str, '%d/%m/%Y')
                except:
                    pass
                if not data_chamada_dt:
                    try:
                        data_chamada_dt = datetime.strptime(data_chamada_str, '%Y/%m/%d')
                    except:
                        pass
                if not data_chamada_dt:
                    try:
                        data_chamada_dt = datetime.strptime(data_chamada_str, '%Y-%m-%d')
                    except:
                        pass
                
                if data_chamada_dt and data_chamada_dt.date() < hoje_dt.date():
                    esta_vencido = True
            except:
                pass
        
        nome_cliente = agend.get('Nome', 'N/D')
        classificacao = agend.get('Classificação', 'N/D')
        status_badge = "🔥 VENCIDO" if esta_vencido else "📅 HOJE"
        titulo_card = f"{status_badge} | 👤 {nome_cliente} | 🏷️ {classificacao}"
        
        with st.expander(titulo_card, expanded=False):
            col_esq, col_dir = st.columns([1, 1])
            
            # ========== COLUNA ESQUERDA: INFORMAÇÕES ==========
            with col_esq:
                st.markdown("### 📊 Dados do Cliente")
                
                st.write(f"**👤 Nome:** {nome_cliente}")
                st.write(f"**📱 Telefone:** {agend.get('Telefone', 'N/D')}")
                st.write(f"**🏷️ Classificação:** {classificacao}")
                
                val = agend.get('Valor', 0)
                if pd.notna(val) and val != '':
                    try:
                        st.write(f"**💰 Valor Total:** R$ {float(val):,.2f}")
                    except:
                        st.write(f"**💰 Valor Total:** {val}")
                else:
                    st.write("**💰 Valor Total:** R$ 0,00")
                
                st.markdown("---")
                
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
                    
                    btn_novo_agendamento = st.form_submit_button(
                        "✅ Realizar Novo Agendamento",
                        type="primary",
                        use_container_width=True
                    )
                    
                    if btn_novo_agendamento:
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
                                    
                                    df_historico = conn.read(worksheet="HISTORICO", ttl=0)
                                    linha_historico = agend.to_dict()
                                    linha_historico['Data de conclusão'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                                    
                                    df_historico_novo = pd.concat(
                                        [df_historico, pd.DataFrame([linha_historico])],
                                        ignore_index=True
                                    )
                                    conn.update(worksheet="HISTORICO", data=df_historico_novo)
                                    
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
                                    
                                    df_agendamentos_atualizado = df_agendamentos_atual.drop(idx).reset_index(drop=True)
                                    df_agendamentos_final = pd.concat(
                                        [df_agendamentos_atualizado, pd.DataFrame([novo_agendamento])],
                                        ignore_index=True
                                    )
                                    
                                    conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_agendamentos_final)
                                    
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
    
    # Inicializar session_state para controle de operações
    if 'operacao_suporte_concluida' not in st.session_state:
        st.session_state.operacao_suporte_concluida = False
    
    # Carregar dados uma única vez
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
    
    prioridades = {'Urgente': 0, 'Alta': 0, 'Média': 0, 'Baixa': 0}
    if 'Prioridade' in df_suporte.columns:
        for p in prioridades.keys():
            prioridades[p] = len(df_suporte[df_suporte['Prioridade'] == p])
    
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
    
    if visualizar == "Hoje":
        df_trabalho = df_hoje.copy()
    else:
        df_trabalho = df_suporte.copy()
    
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
    
    ordem_prioridade = {'Urgente': 0, 'Alta': 1, 'Média': 2, 'Baixa': 3}
    if 'Prioridade' in df_filt.columns:
        df_filt['_ordem'] = df_filt['Prioridade'].map(ordem_prioridade).fillna(4)
        df_filt = df_filt.sort_values('_ordem')
    
    # Cards de tickets
    for idx, ticket in df_filt.iterrows():
        nome_cliente = ticket.get('Nome', 'N/D')
        telefone_cliente = ticket.get('Telefone', '')
        prioridade = ticket.get('Prioridade', 'Média')
        progresso = ticket.get('Progresso', 0)
        
        icones_prioridade = {
            'Urgente': '🔴',
            'Alta': '🟠',
            'Média': '🟡',
            'Baixa': '🟢'
        }
        icone = icones_prioridade.get(prioridade, '⚪')
        titulo_card = f"{icone} {prioridade.upper()} | 👤 {nome_cliente} | 📊 {progresso}% concluído"
        
        with st.expander(titulo_card, expanded=(prioridade in ['Urgente', 'Alta'])):
            col_esq, col_dir = st.columns([1, 1])
            
            # ========== COLUNA ESQUERDA ==========
            with col_esq:
                st.markdown("### 📋 Dados do Ticket")
                st.write(f"**👤 Nome:** {nome_cliente}")
                st.write(f"**📱 Telefone:** {telefone_cliente}")
                st.write(f"**🏷️ Classificação:** {ticket.get('Classificação', 'N/D')}")
                st.write(f"**{icone} Prioridade:** {prioridade}")
                st.markdown("---")
                
                # PROGRESSO
                st.markdown("### 📊 Progresso do Atendimento")
                try:
                    progresso_num = 0
                    if pd.notna(progresso) and str(progresso).strip() != '':
                        progresso_num = float(str(progresso).strip())
                    progresso_decimal = max(0, min(1.0, progresso_num / 100))
                    progresso_display = int(progresso_num)
                except (ValueError, TypeError):
                    progresso_decimal = 0.0
                    progresso_display = 0
                st.progress(progresso_decimal)
                st.write(f"**{progresso_display}% concluído**")
                
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
                
                # DESCRIÇÃO
                st.markdown("### 🔍 Descrição do Problema")
                descricao = ticket.get('Descrição do problema', '')
                if descricao and descricao != '':
                    st.error(f"**Problema relatado:**\n\n{descricao}")
                else:
                    st.caption("_Sem descrição registrada_")
                
                st.markdown("---")
                
                # ========== HISTÓRICO (USA SEMPRE A ÚLTIMA LINHA DESSE TELEFONE) ==========
                st.markdown("### 📝 Histórico de Acompanhamento")
                
                data_abertura = ticket.get('Data de abertura', 'N/D')
                st.write(f"**📅 Aberto em:** {data_abertura}")
                
                try:
                    conn_hist = get_gsheets_connection()
                    df_suporte_full = conn_hist.read(worksheet="SUPORTE", ttl=0)
                except Exception:
                    df_suporte_full = df_suporte.copy()
                
                if 'Telefone' in df_suporte_full.columns and telefone_cliente != '':
                    df_cli = df_suporte_full[df_suporte_full['Telefone'] == telefone_cliente].copy()
                else:
                    df_cli = pd.DataFrame()
                
                if not df_cli.empty:
                    if 'Data de atualização' in df_cli.columns:
                        df_cli = df_cli.sort_values('Data de atualização')
                    else:
                        df_cli = df_cli.reset_index(drop=True)
                    ultimo_registro = df_cli.iloc[-1]
                    ultimo_contato = ultimo_registro.get('Último contato', '')
                    obs = ultimo_registro.get('Observações', '')
                    proximo_contato_data = ultimo_registro.get('Próximo contato', '')
                else:
                    ultimo_contato = ''
                    obs = ''
                    proximo_contato_data = ticket.get('Próximo contato', '')
                
                if ultimo_contato and ultimo_contato != '':
                    st.info(f"**Último acompanhamento:**\n\n{ultimo_contato}")
                else:
                    st.caption("_Nenhum acompanhamento registrado ainda_")
                
                if proximo_contato_data and proximo_contato_data != '':
                    if proximo_contato_data == hoje_str_br:
                        st.success(f"**📅 Próximo contato:** {proximo_contato_data} ✅ HOJE")
                    else:
                        st.info(f"**📅 Próximo contato:** {proximo_contato_data}")
                
                if obs and obs != '':
                    st.info(f"**💬 Observações:** {obs}")
            
            # ========== COLUNA DIREITA: NOVO ACOMPANHAMENTO ==========
            with col_dir:
                st.markdown("### ✏️ Registrar Acompanhamento")
                
                form_key = f"form_suporte_{telefone_cliente}_{idx}"
                
                with st.form(key=form_key):
                    st.info("💡 Registre o acompanhamento e atualize o status do ticket")
                    
                    novo_acompanhamento = st.text_area(
                        "📝 Como foi o contato de hoje?",
                        height=120,
                        placeholder="Descreva o que foi conversado e as ações tomadas...",
                        help="Registre o acompanhamento realizado",
                        key=f"acomp_{form_key}"
                    )
                    
                    nova_data_contato = st.date_input(
                        "📅 Próximo Contato:",
                        value=None,
                        help="Quando será o próximo acompanhamento?",
                        key=f"data_{form_key}"
                    )
                    
                    novo_progresso = st.selectbox(
                        "📊 Atualizar Progresso:",
                        [0, 25, 50, 75, 100],
                        index=[0, 25, 50, 75, 100].index(progresso) if progresso in [0, 25, 50, 75, 100] else 0,
                        help="Atualize o percentual de conclusão do ticket",
                        key=f"prog_{form_key}"
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
                        "💬 Observações Adicionais:",
                        height=60,
                        placeholder="Informações extras relevantes...",
                        key=f"obs_{form_key}"
                    )
                    
                    st.markdown("---")
                    
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
                            help="Move para LOG_RESOLVIDOS + AGENDAMENTOS_ATIVOS + HISTORICO"
                        )
                    
                    # ========== ATUALIZAR: CRIA NOVA LINHA ==========
                    if btn_atualizar:
                        if not novo_acompanhamento:
                            st.error("❌ Preencha como foi o contato de hoje!")
                        elif not nova_data_contato:
                            st.error("❌ Selecione a data do próximo contato!")
                        else:
                            with st.spinner("Criando novo registro de acompanhamento..."):
                                try:
                                    conn = get_gsheets_connection()
                                    df_suporte_atual = conn.read(worksheet="SUPORTE", ttl=0)
                                    
                                    novo_registro = ticket.to_dict().copy()
                                    novo_registro.update({
                                        'Nome': nome_cliente,
                                        'Telefone': telefone_cliente,
                                        'Assunto': ticket.get('Assunto', 'N/D'),
                                        'Prioridade': ticket.get('Prioridade', 'Média'),
                                        'Status': f'Aberto - Acompanhamento #{len(df_suporte_atual)+1}',
                                        'Descrição': ticket.get('Descrição do problema', ''),
                                        'Último contato': novo_acompanhamento,
                                        'Próximo contato': nova_data_contato.strftime('%d/%m/%Y'),
                                        'Progresso': novo_progresso,
                                        'Data de atualização': datetime.now().strftime('%d/%m/%Y %H:%M'),
                                        'Observações': novas_obs if novas_obs else ticket.get('Observações', ''),
                                        'Data de abertura': ticket.get('Data de abertura', 'N/D')
                                    })
                                    
                                    df_novo = pd.concat([df_suporte_atual, pd.DataFrame([novo_registro])], ignore_index=True)
                                    conn.update(worksheet="SUPORTE", data=df_novo)
                                    
                                    carregar_dados.clear()
                                    st.session_state.operacao_suporte_concluida = True
                                    st.success(f"✅ Novo acompanhamento criado! Progresso: {novo_progresso}%")
                                    st.rerun()
                                
                                except Exception as e:
                                    st.error(f"❌ Erro ao criar acompanhamento: {str(e)}")
                    
                    # ========== FINALIZAR SUPORTE - FLUXO COMPLETO ==========
                    if btn_finalizar:
                        if novo_progresso < 100:
                            st.warning("⚠️ Recomendamos marcar o progresso como 100% antes de finalizar")
                        else:
                            with st.spinner("Finalizando suporte e movendo histórico completo..."):
                                try:
                                    conn = get_gsheets_connection()
                                    
                                    # 1. CRIAR LOG TICKET RESOLVIDO
                                    registrar_ticket_resolvido(
                                        dados_cliente={
                                            'Nome': nome_cliente,
                                            'Telefone': telefone_cliente,
                                            'Classificação': ticket.get('Classificação', 'N/D')
                                        },
                                        tipo_problema=ticket.get('Assunto', 'N/D'),
                                        data_abertura=ticket.get('Data de abertura', 'N/D'),
                                        data_resolucao=datetime.now().strftime('%d/%m/%Y %H:%M'),
                                        solucao=novo_acompanhamento if novo_acompanhamento else 'Suporte finalizado sem relato adicional',
                                        resolvido_por="CRM - Suporte"
                                    )
                                    
                                    # 2. CRIAR AGENDAMENTO ATIVO
                                    df_agendamentos = conn.read(worksheet="AGENDAMENTOS_ATIVOS", ttl=0)
                                    novo_agendamento = {
                                        'Data de contato': datetime.now().strftime('%d/%m/%Y'),
                                        'Nome': nome_cliente,
                                        'Classificação': ticket.get('Classificação', ''),
                                        'Valor': '',
                                        'Telefone': telefone_cliente,
                                        'Relato da conversa': f"[SUPORTE CONCLUÍDO] {novo_acompanhamento if novo_acompanhamento else 'Ticket finalizado'}",
                                        'Follow up': 'Acompanhamento pós-suporte',
                                        'Data de chamada': nova_data_contato.strftime('%d/%m/%Y') if nova_data_contato else '',
                                        'Observação': f"Cliente retornando do suporte. Problema: {ticket.get('Descrição do problema', 'N/D')}"
                                    }
                                    
                                    df_agendamentos_novo = pd.concat([df_agendamentos, pd.DataFrame([novo_agendamento])], ignore_index=True)
                                    conn.update(worksheet="AGENDAMENTOS_ATIVOS", data=df_agendamentos_novo)
                                    
                                    # 3. MOVER TODAS LINHAS DO CLIENTE PARA HISTORICO
                                    df_suporte_full = conn.read(worksheet="SUPORTE", ttl=0)
                                    
                                    if telefone_cliente and 'Telefone' in df_suporte_full.columns:
                                        # Pegar TODAS as linhas desse telefone
                                        df_cliente_completo = df_suporte_full[df_suporte_full['Telefone'] == telefone_cliente].copy()
                                        
                                        # Carregar HISTORICO atual
                                        df_historico = conn.read(worksheet="HISTORICO", ttl=0)
                                        
                                        # Adicionar prefixo para identificar origem do suporte
                                        df_cliente_completo['Origem'] = 'SUPORTE - Histórico Completo'
                                        df_cliente_completo['Data de migração'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                                        
                                        # Concatenar com HISTORICO
                                        df_historico_novo = pd.concat([df_historico, df_cliente_completo], ignore_index=True)
                                        conn.update(worksheet="HISTORICO", data=df_historico_novo)
                                        
                                        # REMOVER APENAS as linhas desse cliente da aba SUPORTE
                                        df_suporte_limpo = df_suporte_full[df_suporte_full['Telefone'] != telefone_cliente].reset_index(drop=True)
                                        conn.update(worksheet="SUPORTE", data=df_suporte_limpo)
                                        
                                        qtd_linhas_movidas = len(df_cliente_completo)
                                    else:
                                        qtd_linhas_movidas = 0
                                    
                                    carregar_dados.clear()
                                    st.session_state.operacao_suporte_concluida = True
                                    st.success(f"🎉 **Suporte finalizado com sucesso!**\n\n"
                                              f"✅ **{nome_cliente}** movido para:\n"
                                              f"• 📚 **LOG_TICKETS_RESOLVIDOS**\n"
                                              f"• 📅 **AGENDAMENTOS_ATIVOS**\n"
                                              f"• 📖 **HISTORICO** ({qtd_linhas_movidas} linhas preservadas)")
                                    st.balloons()
                                    time.sleep(2)
                                    st.rerun()
                                
                                except Exception as e:
                                    st.error(f"❌ Erro ao finalizar suporte: {str(e)}")
        
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
                            
                            # ========== REGISTRAR NO LOG_TICKETS_ABERTOS ==========
                            id_ticket = registrar_ticket_aberto(
                                dados_cliente={
                                    'Nome': novo_ticket.get('Nome', ''),
                                    'Telefone': novo_ticket.get('Telefone', ''),
                                    'Classificação': cliente.get('Classificação ', 'N/D')  # não tem classificação aqui
                                },
                                tipo_problema=novo_ticket.get('Assunto', ''),
                                prioridade=novo_ticket.get('Prioridade', ''),
                                descricao=novo_ticket.get('Descrição', ''),
                                aberto_por="CRM"
                            )
                            
                            carregar_dados.clear()
                            st.success(f"✅ Ticket {id_ticket} criado com sucesso!")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Erro ao criar ticket: {e}")
    
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

        # =====================================================================
    # SNAPSHOT DIÁRIO - GERAR LINHA NA ABA HISTORICO_METRICAS
    # =====================================================================
    st.subheader("📸 Snapshot diário de métricas")
    
    col_snap1, col_snap2 = st.columns([2, 1])
    
    with col_snap1:
        st.write(
            "Gere o resumo completo do dia (check-ins, agendamentos, suporte, conversões) "
            "e salve uma linha na aba HISTORICO_METRICAS."
        )
    
    with col_snap2:
        if st.button("📸 Gerar snapshot de hoje", use_container_width=True, type="primary"):
            gerar_snapshot_diario()
            carregar_dados.clear()
            time.sleep(2)
            st.rerun()
    
    st.markdown("---")
    
    # Abaixo disso, futuramente entrarão os gráficos do dashboard
    st.subheader("📈 Análises (em construção)")
    st.info("Os gráficos serão construídos usando os dados da aba HISTORICO_METRICAS.")

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
