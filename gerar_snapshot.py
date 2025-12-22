from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import pytz
import os
import json

def get_gsheets_connection():
    """Conexão com Google Sheets usando credenciais do GitHub Secrets"""
    credentials_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    if not credentials_json:
        raise Exception("❌ GOOGLE_SHEETS_CREDENTIALS não encontrado!")
    
    # Cria objeto de credenciais
    credentials_dict = json.loads(credentials_json)
    conn = GSheetsConnection("gsheets", {"credentials": credentials_dict})
    return conn

def gerar_snapshot_diario(data_especifica=None):
    """Gera snapshot de todas as métricas do dia e salva em HISTORICO_METRICAS"""
    try:
        timezone_brasilia = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(timezone_brasilia)
        
        if data_especifica:
            data_snapshot = data_especifica
        else:
            data_snapshot = agora.strftime('%d/%m/%Y')
        
        print(f"📅 Gerando snapshot para: {data_snapshot}")
        
        conn = get_gsheets_connection()
        
        # Carregar abas de clientes
        print("📊 Carregando dados das abas...")
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
        
        print(f"👥 Clientes: Novo={total_novo}, Promissor={total_promissor}, Leal={total_leal}")
        
        # Check-ins do dia
        checkins_realizados = 0
        if not df_log_checkins.empty and 'Data_Checkin' in df_log_checkins.columns:
            checkins_realizados = len(df_log_checkins[df_log_checkins['Data_Checkin'] == data_snapshot])
        
        # Meta do dia (simplificado, sem session_state)
        meta_dia = 0  # ajuste se tiver lógica específica
        
        # Agendamentos criados no dia
        agendamentos_criados = 0
        if not df_agendamentos.empty and 'Data de contato' in df_agendamentos.columns:
            agendamentos_criados = len(df_agendamentos[df_agendamentos['Data de contato'] == data_snapshot])
        
        # Agendamentos concluídos no dia
        agendamentos_concluidos = 0
        if not df_historico.empty and 'Data de conclusão' in df_historico.columns:
            df_hist_temp = df_historico.copy()
            df_hist_temp['Data_Simples'] = df_hist_temp['Data de conclusão'].astype(str).str[:10]
            agendamentos_concluidos = len(df_hist_temp[df_hist_temp['Data_Simples'] == data_snapshot])
        
        # Tickets abertos no dia
        tickets_abertos = 0
        if not df_suporte.empty and 'Data de abertura' in df_suporte.columns:
            tickets_abertos = len(df_suporte[df_suporte['Data de abertura'] == data_snapshot])
        
        # Tickets pendentes
        tickets_pendentes = len(df_suporte)
        tickets_resolvidos = 0  # ajuste conforme necessário
        
        # Conversões do dia
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
        
        # Salvar no HISTORICO_METRICAS
        df_metricas = conn.read(worksheet="HISTORICO_METRICAS", ttl=0)
        if not df_metricas.empty and 'Data' in df_metricas.columns:
            df_metricas = df_metricas[df_metricas['Data'] != data_snapshot]
        
        df_metricas_novo = pd.concat([df_metricas, pd.DataFrame([snapshot])], ignore_index=True)
        conn.update(worksheet="HISTORICO_METRICAS", data=df_metricas_novo)
        
        print(f"✅ Snapshot salvo com sucesso para {data_snapshot}!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao gerar snapshot: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    gerar_snapshot_diario()
