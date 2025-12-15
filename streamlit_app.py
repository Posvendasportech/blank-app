import streamlit as st
import pandas as pd
from urllib.parse import quote
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import time
import re
import logging
# ========== ADICIONAR APÓS: import logging ==========
# ✅ NOVO: Biblioteca para retry automático
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import gspread.exceptions

# =========================================================
# (0) 🔧 CONFIGURAÇÕES GLOBAIS
# =========================================================
class Config:
    """Centralize todas as constantes aqui para fácil manutenção"""
    
    # Google Sheets
    SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
    SHEET_NAME = "Total"
    SHEET_AGENDAMENTOS = "Agendamentos"
    SHEET_EM_ATENDIMENTO = "EM_ATENDIMENTO"  # ✅ NOVO - Controla locks multi-usuário
    
    # Listas de opções
    VENDEDORES = ["João", "Maria", "Patrick", "Outro"]
    CLASSIFICACOES = ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"]
    # ✅ ADICIONAR ESTAS LINHAS AQUI:
    TIPOS_ATENDIMENTO = ["Experiência", "Suporte", "Venda"]
    # Cache e Performance
    CACHE_BASE_TTL = 180  # ✅ ALTERADO: 60 → 300 (5 minutos para dados estáveis)
    CACHE_VOLATILE_TTL = 0  # ✅ NOVO: 10 segundos para dados que mudam frequentemente
    LOCK_TIMEOUT_MINUTES = 10  # ✅ NOVO: Timeout para locks de atendimento
    
    # Valores padrão
    DIAS_MINIMO_NOVOS = 15

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crm_sportech.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =========================================================
# (1) ⚙️ CONFIGURAÇÃO INICIAL + CSS (INTERFACE DO SISTEMA)
# =========================================================
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: #FFFFFF;
}

.streamlit-expanderHeader {
    background-color: #111 !important;
}

[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

.card {
    background-color: #101010;
    border: 1px solid #222;
    border-radius: 16px;
    padding: 18px;
    color: white;
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    margin-bottom: 18px;
}

.card-header {
    background: linear-gradient(135deg, #0A40B0, #183b8c);
    padding: 14px;
    border-radius: 12px;
    font-size: 16px;
    margin-bottom: 14px;
    line-height: 1.5;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# (2) 🔑 CONEXÃO + FUNÇÕES UTILITÁRIAS (NÚCLEO)
# =========================================================

@st.cache_resource
def get_gsheet_client():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(credentials)

def obter_usuario_atual():
    """Identifica o usuário atual para evitar conflitos de atendimento"""
    if "usuario_nome" not in st.session_state:
        # Exibir input na sidebar para o usuário se identificar
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 👤 Identificação")
            nome = st.text_input(
                "Seu nome:", 
                key="nome_usuario_input",
                help="Necessário para evitar atendimentos duplicados",
                placeholder="Digite seu nome"
            )
            if nome:
                st.session_state["usuario_nome"] = nome
                st.success(f"✅ Logado como: {nome}")
            else:
                st.warning("⚠️ Identifique-se para continuar")
    
    return st.session_state.get("usuario_nome", "")
@st.cache_data(ttl=Config.CACHE_VOLATILE_TTL)
def load_em_atendimento():
    """Carrega lista de clientes que estão sendo atendidos agora"""
    try:
        client = get_gsheet_client()
        sh = client.open_by_key(Config.SHEET_ID)
        
        # Tentar abrir a aba, criar se não existir
        try:
            ws = sh.worksheet("EM_ATENDIMENTO")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet("EM_ATENDIMENTO", rows=1000, cols=4)
            ws.append_row(["Telefone", "Usuario", "Timestamp", "Cliente"])
            logger.info("✅ Aba EM_ATENDIMENTO criada automaticamente")
        
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame(columns=["Telefone", "Usuario", "Timestamp", "Cliente"])
        
        df = pd.DataFrame(records)
        
        # Limpar locks expirados (mais de 15 minutos)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        agora = datetime.now()
        tempo_limite = agora - pd.Timedelta(minutes=Config.LOCK_TIMEOUT_MINUTES)
        df = df[df["Timestamp"] > tempo_limite]
        
        logger.info(f"✅ Locks ativos carregados: {len(df)}")
        return df
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar EM_ATENDIMENTO: {e}")
        return pd.DataFrame(columns=["Telefone", "Usuario", "Timestamp", "Cliente"])


# ✅ NOVA VERSÃO COM VERIFICAÇÃO ATÔMICA
def criar_lock(telefone, usuario, cliente):
    """Cria um lock quando um card é exibido - com verificação atômica"""
    try:
        client = get_gsheet_client()
        sh = client.open_by_key(Config.SHEET_ID)
        
        try:
            ws = sh.worksheet("EM_ATENDIMENTO")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet("EM_ATENDIMENTO", rows=1000, cols=4)
            ws.append_row(["Telefone", "Usuario", "Timestamp", "Cliente"])
            logger.info("✅ Aba EM_ATENDIMENTO criada")
        
        # ✅ NOVO: Verificar se já existe lock ANTES de criar
        try:
            cell = ws.find(str(telefone))
            if cell:
                # Já existe lock - verificar se é de outro usuário
                usuario_existente = ws.cell(cell.row, 2).value
                
                if usuario_existente != usuario:
                    logger.warning(f"⚠️ Lock já existe para {telefone} por {usuario_existente}")
                    return False  # ✅ Retorna False = não conseguiu criar lock
                else:
                    logger.info(f"🔄 Atualizando lock existente de {usuario}")
                    # Atualizar timestamp
                    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ws.update_cell(cell.row, 3, agora)
                    return True
        except gspread.exceptions.CellNotFound:
            pass  # Não existe, pode criar
        
        # Criar novo lock
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([str(telefone), str(usuario), agora, str(cliente)])
        
        # Limpar cache
        load_em_atendimento.clear()
        logger.info(f"🔒 Lock criado: {telefone} por {usuario}")
        return True  # ✅ Retorna True = lock criado com sucesso
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar lock: {e}")
        return False


def remover_lock(telefone):
    """Remove o lock quando o atendimento é concluído ou pulado"""
    try:
        client = get_gsheet_client()
        sh = client.open_by_key(Config.SHEET_ID)
        ws = sh.worksheet("EM_ATENDIMENTO")
        
        # ✅ MELHORADO: Buscar por telefone limpo também
        telefone_limpo = limpar_telefone(str(telefone))
        
        # Buscar a linha do telefone
        try:
            cell = ws.find(str(telefone))
            if cell:
                ws.delete_rows(cell.row)
                load_em_atendimento.clear()
                logger.info(f"🔓 Lock removido: {telefone}")
                return
        except gspread.exceptions.CellNotFound:
            pass
        
        # ✅ NOVO: Se não encontrou, tentar buscar por telefone limpo
        try:
            all_phones = ws.col_values(1)[1:]  # Coluna 1 = Telefone, pula cabeçalho
            for i, phone in enumerate(all_phones, start=2):  # Start=2 pois linha 1 é cabeçalho
                if limpar_telefone(phone) == telefone_limpo:
                    ws.delete_rows(i)
                    load_em_atendimento.clear()
                    logger.info(f"🔓 Lock removido (busca limpa): {telefone}")
                    return
        except Exception as e_inner:
            logger.warning(f"⚠️ Erro na busca alternativa de lock: {e_inner}")
        
        logger.warning(f"⚠️ Lock não encontrado para remover: {telefone}")
            
    except Exception as e:
        logger.error(f"❌ Erro ao remover lock: {e}")



def converte_dias(v):
    try:
        return int(round(float(str(v).replace(",", "."))))
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Erro ao converter dias para '{v}': {e}")
        return None

def safe_valor(v):
    try:
        if pd.isna(v):
            return "—"
        
        # Converter para string e limpar
        v_str = str(v).replace("R$", "").strip()
        
        # ✅ CORREÇÃO: Detectar formato brasileiro vs americano
        # Formato BR: 1.234,56 → 1234.56
        # Formato US: 1,234.56 → 1234.56
        
        if "," in v_str and "." in v_str:
            # Tem ambos: determinar qual é decimal
            if v_str.rindex(",") > v_str.rindex("."):
                # Vírgula depois do ponto = formato BR
                v_str = v_str.replace(".", "").replace(",", ".")
            else:
                # Ponto depois da vírgula = formato US
                v_str = v_str.replace(",", "")
        elif "," in v_str:
            # Só vírgula: assumir que é decimal BR
            v_str = v_str.replace(",", ".")
        elif "." in v_str:
            # Só ponto: verificar posição
            partes = v_str.split(".")
            if len(partes[-1]) == 2:
                # Tem 2 dígitos após o ponto = decimal
                pass  # Já está correto
            else:
                # Mais de 2 dígitos = separador de milhar
                v_str = v_str.replace(".", "")
        
        return f"R$ {float(v_str):.2f}"
        
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Erro ao converter valor '{v}': {e}")
        return "—"


def valor_num(v):
    try:
        if pd.isna(v):
            return None
        v = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(v)
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning(f"Erro ao converter valor numérico '{v}': {e}")
        return None

def limpar_telefone(tel):
    """Limpa telefone removendo TUDO exceto dígitos, incluindo +55"""
    if pd.isna(tel):
        return ""
    
    tel_str = str(tel).strip()
    
    # Remover +55 do início
    if tel_str.startswith("+55"):
        tel_str = tel_str[3:]
    elif tel_str.startswith("55") and len(tel_str) > 11:
        tel_str = tel_str[2:]
    
    # Remover tudo exceto números
    numeros = re.sub(r'\D', '', tel_str)
    
    return numeros


# =========================================================
# (3) 💾 FUNÇÕES DE CARREGAMENTO (BASES)
# =========================================================

@st.cache_data(ttl=Config.CACHE_BASE_TTL)  # ✅ ALTERADO: Agora usa cache de 5 minutos
def load_sheet(sheet_id, sheet_name):
    logger.info(f"Carregando planilha: {sheet_name}")
    
    try:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
        df_raw = pd.read_csv(url)
        
        # Validação: Verificar colunas mínimas
        if len(df_raw.columns) < 9:
            st.error(f"❌ Planilha '{sheet_name}' inválida! Esperado 9 colunas, encontrado {len(df_raw.columns)}")
            logger.error(f"Planilha {sheet_name} com estrutura inválida")
            st.stop()
        
        # Validação: Verificar se tem dados
        if df_raw.empty:
            st.warning(f"⚠️ Planilha '{sheet_name}' está vazia!")
            logger.warning(f"Planilha {sheet_name} vazia")
            return pd.DataFrame()
        
        # Processar dentro do cache
        df = pd.DataFrame({
            "Data": pd.to_datetime(df_raw.iloc[:,0], errors="coerce"),
            "Cliente": df_raw.iloc[:,1],
            "Email": df_raw.iloc[:,2],
            "Valor": df_raw.iloc[:,3],
            "Telefone": df_raw.iloc[:,4].astype(str),
            "Compras": df_raw.iloc[:,5],
            "Classificação": df_raw.iloc[:,6],
            "Dias_num": df_raw.iloc[:,8].apply(converte_dias),
        })
        df["Valor_num"] = df["Valor"].apply(valor_num)
        df["Telefone_limpo"] = df["Telefone"].apply(limpar_telefone)
        
        logger.info(f"✅ Planilha {sheet_name} carregada: {len(df)} registros")
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar planilha '{sheet_name}': {e}")
        logger.error(f"Erro ao carregar {sheet_name}: {e}", exc_info=True)
        st.stop()

# ✅ Usar apenas CACHE_VOLATILE_TTL (sem cache para dados críticos)
@st.cache_data(ttl=Config.CACHE_VOLATILE_TTL)
def load_agendamentos_ativos():
    """Carrega TODOS os telefones que já têm agendamento (independente da data)"""
    try:
        client = get_gsheet_client()
        ws = client.open(Config.SHEET_AGENDAMENTOS).worksheet("AGENDAMENTOS_ATIVOS")
        
        # Pegar TODOS os telefones da coluna 5 (Telefone)
        telefones = set(ws.col_values(5)[1:])  # [1:] pula o cabeçalho
        
        # Limpar telefones vazios
        telefones = {t for t in telefones if t and str(t).strip()}
        
        logger.info(f"✅ Total de telefones com agendamento ativo: {len(telefones)}")
        return telefones
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar agendamentos ativos: {e}", exc_info=True)
        return set()


@st.cache_data(ttl=Config.CACHE_BASE_TTL)
def load_df_agendamentos():
    try:
        client = get_gsheet_client()
        ws = client.open(Config.SHEET_AGENDAMENTOS).worksheet("AGENDAMENTOS_ATIVOS")
        df = pd.DataFrame(ws.get_all_records())
        logger.info(f"✅ DataFrame agendamentos carregado: {len(df)} registros")
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar DataFrame agendamentos: {e}", exc_info=True)
        return pd.DataFrame()

@st.cache_data(ttl=Config.CACHE_BASE_TTL)
def load_historico():
    try:
        client = get_gsheet_client()
        ws = client.open(Config.SHEET_AGENDAMENTOS).worksheet("HISTORICO")
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [c.replace(" ", "_") for c in df.columns]
        logger.info(f"✅ Histórico carregado: {len(df)} registros")
        return df
    except Exception as e:
        logger.error(f"Erro ao carregar histórico: {e}", exc_info=True)
        return pd.DataFrame()

@st.cache_data(ttl=Config.CACHE_VOLATILE_TTL)  # Cache de 10 segundos (muda frequentemente)
@st.cache_data(ttl=Config.CACHE_VOLATILE_TTL)
def load_agendamentos_hoje():
    """Carrega APENAS os agendamentos para HOJE (filtrado pela 'Próxima data')"""
    try:
        client = get_gsheet_client()
        ws = client.open(Config.SHEET_AGENDAMENTOS).worksheet("AGENDAMENTOS_ATIVOS")
        df = pd.DataFrame(ws.get_all_records())
        
        if df.empty:
            logger.info("⚠️ Nenhum agendamento na base")
            return pd.DataFrame()
        
        logger.info(f"📊 Total de agendamentos na base: {len(df)}")
        
        # Detectar qual coluna usar
        if "Próxima data" in df.columns:
            col_data = "Próxima data"
        elif "Data de chamada" in df.columns:
            col_data = "Data de chamada"
        else:
            logger.error("❌ Nenhuma coluna de data encontrada")
            logger.error(f"Colunas disponíveis: {df.columns.tolist()}")
            return pd.DataFrame()
        
        # ✅ MELHORADO: Tentar múltiplos formatos de data
        df['data_convertida'] = None
        
        # Formato 1: YYYY/MM/DD (seu caso: 2025/12/24)
        df['data_convertida'] = pd.to_datetime(df[col_data], format='%Y/%m/%d', errors='coerce')
        
        # Formato 2: DD/MM/YYYY (se o primeiro falhar)
        mascara_nulas = df['data_convertida'].isna()
        if mascara_nulas.any():
            df.loc[mascara_nulas, 'data_convertida'] = pd.to_datetime(
                df.loc[mascara_nulas, col_data], 
                format='%d/%m/%Y', 
                errors='coerce'
            )
        
        # Formato 3: ISO padrão (último recurso)
        mascara_nulas = df['data_convertida'].isna()
        if mascara_nulas.any():
            df.loc[mascara_nulas, 'data_convertida'] = pd.to_datetime(
                df.loc[mascara_nulas, col_data], 
                errors='coerce'
            )
        
        # Data de hoje (sem hora)
        hoje = datetime.now().date()
        
        # Filtrar por hoje
        df_hoje = df[df['data_convertida'].dt.date == hoje].copy()
        
        logger.info(f"✅ Agendamentos para hoje ({hoje.strftime('%Y/%m/%d')}): {len(df_hoje)}")
        
        if not df_hoje.empty:
            df_hoje["Telefone_limpo"] = df_hoje["Telefone"].apply(limpar_telefone)
            logger.info(f"📞 Telefones: {df_hoje['Telefone'].tolist()}")
        else:
            # ✅ DEBUG: Mostrar quais datas estão na base
            datas_unicas = df['data_convertida'].dropna().dt.date.unique()
            logger.warning(f"⚠️ Datas encontradas na base: {sorted(datas_unicas)}")
            logger.warning(f"⚠️ Procurando por: {hoje}")
        
        return df_hoje
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar agendamentos de hoje: {e}", exc_info=True)
        return pd.DataFrame()

@st.cache_data(ttl=Config.CACHE_VOLATILE_TTL)
def load_casos_suporte():
    """Carrega APENAS casos marcados como 'Suporte'"""
    try:
        client = get_gsheet_client()
        ws = client.open(Config.SHEET_AGENDAMENTOS).worksheet("AGENDAMENTOS_ATIVOS")
        df = pd.DataFrame(ws.get_all_records())
        
        if df.empty:
            logger.info("⚠️ Nenhum agendamento na base")
            return pd.DataFrame()
        
        # Filtrar apenas "Suporte"
        if "Tipo de atendimento" in df.columns:
            df_suporte = df[df["Tipo de atendimento"] == "Suporte"].copy()
            
            if not df_suporte.empty:
                df_suporte["Telefone_limpo"] = df_suporte["Telefone"].apply(limpar_telefone)
            
            logger.info(f"🛠️ Casos de suporte: {len(df_suporte)}")
            return df_suporte
        else:
            logger.warning("⚠️ Coluna 'Tipo de atendimento' não encontrada")
            return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"❌ Erro ao carregar suporte: {e}", exc_info=True)
        return pd.DataFrame()

# =========================================================
# (4) 🧠 ESTADO DA SESSÃO
# =========================================================

def init_session_state():
    if "concluidos" not in st.session_state:
        st.session_state["concluidos"] = set()
    
    if "pulados" not in st.session_state:
        st.session_state["pulados"] = set()
    
    if "historico_stack" not in st.session_state:
        st.session_state["historico_stack"] = []
    
    if "rerun_necessario" not in st.session_state:
        st.session_state["rerun_necessario"] = False
    
    # ✅ ADICIONAR ESTA LINHA:
    if "aba_ativa" not in st.session_state:
        st.session_state["aba_ativa"] = 0  # 0 = primeira aba por padrão

def limpar_caches_volateis():
    """Limpa apenas caches de dados que mudam frequentemente"""
    load_em_atendimento.clear()
    load_agendamentos_ativos.clear()
    load_agendamentos_hoje.clear()
    load_df_agendamentos.clear()
    load_casos_suporte.clear()  # ✅ ADICIONAR ESTA LINHA
    logger.info("🔄 Caches voláteis limpos")


# =========================================================
# (5) 🎨 COMPONENTE CARD DE ATENDIMENTO
# =========================================================

def card_component(id_fix, row, usuario_atual):
    """Card de atendimento com formulário (evita reruns ao digitar)"""
    
    telefone = str(row.get("Telefone", ""))
    
    # ✅ VERSÃO CORRIGIDA: Só bloqueia se REALMENTE tiver outro usuário
    lock_key = f"lock_criado_{id_fix}"
    if lock_key not in st.session_state:
        # Verificar se OUTRO usuário já está com este cliente
        df_locks = load_em_atendimento()
        telefone_limpo = limpar_telefone(telefone)
        
        lock_existente = df_locks[
            (df_locks["Telefone"].astype(str) == str(telefone)) | 
            (df_locks["Telefone"].apply(limpar_telefone) == telefone_limpo)
        ]
        
        if not lock_existente.empty:
            usuario_lock = lock_existente.iloc[0]["Usuario"]
            
            # Só bloqueia se for OUTRO usuário
            if usuario_lock != usuario_atual:
                st.warning(f"⚠️ Este cliente está sendo atendido por **{usuario_lock}** agora!")
                st.info("🔄 Aguarde ou escolha outro cliente")
                return None, "", "", None, ""  # ✅ Retorna valores vazios
        
        # Criar lock para o usuário atual
        criar_lock(telefone, usuario_atual, row.get("Cliente", "—"))
        st.session_state[lock_key] = True
        logger.info(f"🔒 Card exibido e travado para {usuario_atual}: {telefone}")

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)

        dias_txt = f"{row['Dias_num']} dias desde compra" if pd.notna(row.get("Dias_num")) else "Sem informação"
        motivo_anterior = row.get("Follow up", row.get("Motivo", row.get("Relato da conversa", "")))
        
        header_html = f"""
            <div class="card-header">
                <b>{row.get('Cliente', '—')}</b><br>
                📱 {row.get('Telefone', '—')}<br>
                🏷 {row.get('Classificação', '—')}<br>
                💰 {safe_valor(row.get('Valor', '—'))}<br>
                ⏳ {dias_txt}
        """
        
        if motivo_anterior and str(motivo_anterior).strip() and str(motivo_anterior) != "—":
            header_html += f"""<br><br>
                📋 <b>Direcionamento anterior:</b><br>
                <i style="color:#a0d8ff;">{motivo_anterior}</i>
            """
        
        header_html += "</div>"
        st.markdown(header_html, unsafe_allow_html=True)

        # Usar FORM para evitar reruns ao digitar
        with st.form(key=f"form_{id_fix}", clear_on_submit=False):
            vendedor = st.selectbox("Responsável", Config.VENDEDORES, key=f"vend_{id_fix}")
            motivo = st.text_input("Motivo do contato", key=f"mot_{id_fix}")
            resumo = st.text_area("Resumo da conversa", key=f"res_{id_fix}", height=80)
            proxima = st.date_input("Próxima data", key=f"dt_{id_fix}")

            col1, col2 = st.columns(2)
            
            # Botões dentro do form
            concluir = col1.form_submit_button("✅ Registrar e concluir", use_container_width=True)
            pular = col2.form_submit_button("⏭ Pular cliente", use_container_width=True)
            
            # ✅ INICIALIZAR acao SEMPRE
            acao = None
            
            if concluir:
                if not motivo.strip():
                    st.error("⚠️ O campo 'Motivo do contato' é obrigatório")
                elif not resumo.strip():
                    st.error("⚠️ O campo 'Resumo da conversa' é obrigatório")
                elif not proxima:
                    st.error("⚠️ Selecione uma data para o próximo contato")
                else:
                    acao = "concluir"
                    remover_lock(telefone)
            
            if pular:
                acao = "pular"
                remover_lock(telefone)

        st.markdown("</div>", unsafe_allow_html=True)

    # ✅ GARANTIR QUE SEMPRE RETORNA 5 VALORES
    return acao, motivo, resumo, proxima, vendedor



def agendamento_card(id_fix, row):
    """Card completo para agendamentos ativos"""
    
    nome = row.get("Cliente") or row.get("Nome", "—")
    telefone = row.get("Telefone", "—")
    ultima_compra = row.get("Data", "—")
    valor_gasto = safe_valor(row.get("Valor", "—"))
    num_compras = row.get("Compras", "—")
    ultimo_contato = row.get("Data de contato", "—")
    dias_ult_contato = row.get("Dias_desde_contato", "—")
    followup = row.get("Follow up", "—")

    cabecalho_html = f"""
    <div style="
        background:#111827;
        border: 1px solid #1e3a8a;
        padding:15px;
        border-radius:10px;
        margin-bottom:20px;
        color:white;
        font-size:15px;
        line-height:1.5;
    ">
        <b>{nome}</b><br>
        📱 {telefone}<br><br>
        🕓 <b>Último contato:</b> {ultimo_contato}<br>
        ⏳ <b>Dias desde o último contato:</b> {dias_ult_contato}<br><br>
        🛒 <b>Data da última compra:</b> {ultima_compra}<br>
        💵 <b>Valor gasto:</b> {valor_gasto}<br>
        📦 <b>Nº de compras:</b> {num_compras}<br><br>
        📝 <b>Direcionamento anterior:</b> {followup}
    </div>
    """

    st.markdown(cabecalho_html, unsafe_allow_html=True)

    vendedor = st.selectbox("Responsável", Config.VENDEDORES, key=f"vend_ag_{id_fix}")
    resumo = st.text_area("Resumo da conversa", key=f"res_ag_{id_fix}", height=80)
    novo_motivo = st.text_input("Novo direcionamento", key=f"mot_ag_{id_fix}")
    proxima = st.date_input("Próxima data", key=f"prox_ag_{id_fix}")

    colA, colB = st.columns(2)
    acao = None

    with colA:
        if st.button("📩 Registrar conversa", key=f"ok_ag_{id_fix}"):
            # Validar campos
            if not resumo.strip():
                st.error("⚠️ O campo 'Resumo da conversa' é obrigatório")
            elif not novo_motivo.strip():
                st.error("⚠️ O campo 'Novo direcionamento' é obrigatório")
            else:
                acao = "concluir"

    with colB:
        if st.button("⏭ Pular", key=f"skip_ag_{id_fix}"):
            acao = "pular"

    return acao, novo_motivo, resumo, proxima, vendedor

def card_suporte(id_fix, row, usuario_atual):
    """Card específico para casos de SUPORTE"""
    
    telefone = str(row.get("Telefone", ""))
    
    # Sistema de lock
    lock_key = f"lock_criado_{id_fix}"
    if lock_key not in st.session_state:
        df_locks = load_em_atendimento()
        telefone_limpo = limpar_telefone(telefone)
        
        lock_existente = df_locks[
            (df_locks["Telefone"].astype(str) == str(telefone)) | 
            (df_locks["Telefone"].apply(limpar_telefone) == telefone_limpo)
        ]
        
        if not lock_existente.empty:
            usuario_lock = lock_existente.iloc[0]["Usuario"]
            if usuario_lock != usuario_atual:
                st.warning(f"⚠️ Este caso está sendo atendido por **{usuario_lock}**")
                return None, "", "", None, ""
        
        criar_lock(telefone, usuario_atual, row.get("Cliente", "—"))
        st.session_state[lock_key] = True

    with st.container():
        # Card com cor diferenciada (vermelho para suporte)
        st.markdown("""
            <style>
            .card-suporte {
                background: linear-gradient(135deg, #8B0000, #DC143C);
                border: 2px solid #FF6347;
                border-radius: 16px;
                padding: 18px;
                color: white;
                box-shadow: 0 8px 24px rgba(220, 20, 60, 0.3);
                margin-bottom: 18px;
            }
            </style>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="card-suporte">', unsafe_allow_html=True)
        
        # Header com informações do problema
        header_html = f"""
            <div style="background: rgba(0,0,0,0.3); padding: 14px; border-radius: 12px; margin-bottom: 14px;">
                <b>🛠️ SUPORTE - {row.get('Cliente', '—')}</b><br>
                📱 {row.get('Telefone', '—')}<br>
                💰 {safe_valor(row.get('Valor', '—'))}<br>
        """
        
        # Mostrar o problema reportado
        follow_up = row.get("Follow up", row.get("Motivo", ""))
        if follow_up and str(follow_up).strip():
            header_html += f"""
                <br><b style="color:#FFD700;">⚠️ Problema reportado:</b><br>
                <i style="color:#FFA07A;">{follow_up}</i>
            """
        
        header_html += "</div>"
        st.markdown(header_html, unsafe_allow_html=True)
        
        # Formulário específico para suporte
        with st.form(key=f"form_suporte_{id_fix}", clear_on_submit=False):
            vendedor = st.selectbox("Responsável", Config.VENDEDORES, key=f"vend_sup_{id_fix}")
            
            status = st.selectbox(
                "Status do problema",
                ["Aguardando fornecedor", "Em análise", "Resolvido", "Escalado"],
                key=f"status_{id_fix}"
            )
            
            resumo = st.text_area(
                "Atualização do caso",
                key=f"res_sup_{id_fix}",
                height=100,
                placeholder="Descreva o andamento do problema..."
            )
            
            # Se resolvido, não precisa de próxima data
            if status != "Resolvido":
                proxima = st.date_input("Próximo acompanhamento", key=f"dt_sup_{id_fix}")
                motivo = f"[{status}] Acompanhamento de suporte"
            else:
                proxima = None
                motivo = "[Resolvido] Caso encerrado"
                st.success("✅ Caso será marcado como resolvido")
            
            col1, col2 = st.columns(2)
            
            concluir = col1.form_submit_button("✅ Atualizar", use_container_width=True)
            pular = col2.form_submit_button("⏭ Pular", use_container_width=True)
            
            acao = None
            
            if concluir:
                if not resumo.strip():
                    st.error("⚠️ Descreva a atualização do caso")
                else:
                    acao = "concluir"
                    remover_lock(telefone)
            
            if pular:
                acao = "pular"
                remover_lock(telefone)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    return acao, motivo, resumo, proxima, vendedor

# =========================================================
# (6) 🧾 AÇÕES — SALVAR, REMOVER, REGISTRAR
# =========================================================

def remover_card(telefone, concluido=True):
    telefone = str(telefone)
    if concluido:
        st.session_state["concluidos"].add(telefone)
        logger.info(f"Cliente concluído: {telefone}")
    else:
        st.session_state["pulados"].add(telefone)
        logger.info(f"Cliente pulado: {telefone}")
    
    st.session_state["historico_stack"].append(telefone)

# ✅ NOVO: Decorador de retry - tenta até 3x com espera exponencial
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((gspread.exceptions.APIError, TimeoutError)),
    reraise=True
)
def _salvar_no_sheets_com_retry(ws_hist, ws_ag, dados, proxima_data):
    """Função interna que faz o salvamento real (com retry)"""
    # Registrar no histórico
    ws_hist.append_row(dados, value_input_option="USER_ENTERED")
    logger.info(f"✅ Histórico salvo")
    
    # Registrar agendamento se houver próxima data
    if proxima_data:
        ws_ag.append_row(dados, value_input_option="USER_ENTERED")
        logger.info(f"✅ Agendamento salvo")


def registrar_agendamento(row, comentario, motivo, proxima_data, vendedor, tipo_atendimento="Experiência"):
    """Registra agendamento com tipo de atendimento"""
    logger.info(f"Iniciando registro para: {row.get('Cliente', 'N/A')} - Tel: {row.get('Telefone', 'N/A')}")
    
    with st.spinner("💾 Salvando no Google Sheets..."):
        try:
            client = get_gsheet_client()
            sh = client.open(Config.SHEET_AGENDAMENTOS)
            ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
            ws_hist = sh.worksheet("HISTORICO")

            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            

            # Converter valores para tipos nativos
            dados = [
                agora,
                str(row.get("Cliente", "—")),
                str(row.get("Classificação", "—")),
                safe_valor(row.get("Valor", "—")),
                str(row.get("Telefone", "—")),
                str(comentario) if comentario else "",
                str(motivo) if motivo else "",
                str(proxima_data) if proxima_data else "",
                str(vendedor) if vendedor else "",
                str(tipo_atendimento)  # ✅ ADICIONAR ESTA LINHA
            ]

            
            # ✅ USAR FUNÇÃO COM RETRY
            _salvar_no_sheets_com_retry(ws_hist, ws_ag, dados, proxima_data)

            # Limpar caches
            load_agendamentos_ativos.clear()
            load_df_agendamentos.clear()
            load_historico.clear()

            st.success("✅ Agendamento registrado com sucesso!")
            logger.info(f"✅ Registro concluído: {row.get('Cliente')}")
            time.sleep(0.5)
            
        except Exception as e:
            st.error(f"❌ Erro ao salvar após 3 tentativas: {e}")
            logger.error(f"❌ ERRO CRÍTICO ao registrar: {e}", exc_info=True)
            
            with st.expander("🔍 Detalhes do erro (para debug)", expanded=False):
                st.write("**Tipo de erro:**", type(e).__name__)
                st.write("**Mensagem:**", str(e))


def gerar_relatorio_diario():
    """Gera CSV com estatísticas da sessão atual"""
    
    total_concluidos = len(st.session_state["concluidos"])
    total_pulados = len(st.session_state["pulados"])
    total_processado = total_concluidos + total_pulados
    taxa_conclusao = (total_concluidos / max(1, total_processado)) * 100
    
    df_relatorio = pd.DataFrame({
        "Métrica": [
            "Total concluídos",
            "Total pulados",
            "Total processado",
            "Taxa de conclusão (%)",
            "Data/Hora"
        ],
        "Valor": [
            total_concluidos,
            total_pulados,
            total_processado,
            f"{taxa_conclusao:.1f}%",
            datetime.now().strftime("%d/%m/%Y %H:%M")
        ]
    })
    
    return df_relatorio.to_csv(index=False).encode("utf-8-sig")

# =========================================================
# (7) 🧱 SIDEBAR — FILTROS + METAS + CONTROLES DE SESSÃO
# =========================================================

def render_sidebar():
    with st.sidebar:
        
        # ===========================
        # BLOCO 1 — FILTROS AVANÇADOS
        # ===========================
        st.markdown("""
            <div style="font-size:18px; font-weight:700; margin-bottom:4px;">
                ⚙️ Filtros avançados
            </div>
            <p style="font-size:12px; color:#bbbbbb; margin-top:0;">
                Ajuste quem aparece na lista de tarefas do dia.
            </p>
        """, unsafe_allow_html=True)

        min_dias = st.number_input("Mínimo de dias desde a última compra", min_value=0, value=0)
        max_dias = st.number_input("Máximo de dias desde a última compra", min_value=0, value=365)
        min_val = st.number_input("Valor mínimo (R$)", value=0.0, min_value=0.0, step=10.0)
        max_val = st.number_input("Valor máximo (R$)", value=1000.0, min_value=0.0, step=10.0)
        telefone = st.text_input("Buscar por telefone (qualquer parte)").strip()

        st.markdown("<hr>", unsafe_allow_html=True)
        
        # ===========================
        # BLOCO ATUALIZAÇÃO MANUAL
        # ===========================
        st.markdown("""
            <div style="font-size:16px; font-weight:600; margin-bottom:4px;">
                🔄 Atualizar Dados
            </div>
            <p style="font-size:12px; color:#bbbbbb; margin-top:0;">
                Clique para sincronizar com mudanças de outros usuários.
            </p>
        """, unsafe_allow_html=True)
        
        if st.button("🔄 Atualizar agora", use_container_width=True):
            # ✅ Usar função otimizada
            limpar_caches_volateis()
            st.success("✅ Dados sincronizados!")
            time.sleep(0.5)  # Pequena pausa para garantir que o cache foi limpo
            st.rerun()



        # ===========================
        # BLOCO 2 — CONTROLES DA SESSÃO
        # ===========================
        st.markdown("""
            <div style="font-size:16px; font-weight:600; margin-bottom:4px;">
                🔁 Controles da sessão
            </div>
            <p style="font-size:12px; color:#bbbbbb; margin-top:0;">
                Use estes botões para desfazer o último atendimento ou reiniciar a lista.
            </p>
        """, unsafe_allow_html=True)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("↩ Voltar último cliente"):
                if st.session_state["historico_stack"]:
                    ultimo = st.session_state["historico_stack"].pop()
                    st.session_state["concluidos"].discard(ultimo)
                    st.session_state["pulados"].discard(ultimo)
                    logger.info(f"Cliente restaurado: {ultimo}")
                st.rerun()

        with col_s2:
            if st.button("🧹 Resetar sessão"):
                st.session_state["concluidos"] = set()
                st.session_state["pulados"] = set()
                st.session_state["historico_stack"] = []
                logger.info("Sessão resetada")
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)

        # ===========================
        # BLOCO DEBUG (NOVO)
        # ===========================
        with st.expander("🧪 Modo Debug (Desenvolvedores)", expanded=False):
            st.markdown("**Estado da Sessão:**")
            st.json({
                "concluidos": list(st.session_state.get("concluidos", set())),
                "pulados": list(st.session_state.get("pulados", set())),
                "stack_size": len(st.session_state.get("historico_stack", []))
            })
            
            st.markdown("**Cache Status:**")
            col_d1, col_d2 = st.columns(2)
            col_d1.write(f"TTL Base: {Config.CACHE_BASE_TTL}s / Volátil: {Config.CACHE_VOLATILE_TTL}s")
            col_d2.write(f"Sheets ID: {Config.SHEET_ID[:20]}...")
            
            if st.button("🗑️ Limpar TODOS os caches"):
                st.cache_data.clear()
                st.cache_resource.clear()
                logger.info("Caches limpos manualmente")
                st.success("Caches limpos!")
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)

        # ===========================
        # BLOCO 3 — METAS DO DIA
        # ===========================
        st.markdown("""
            <div style="font-size:16px; font-weight:600; margin-bottom:4px;">
                🎯 Metas do dia
            </div>
            <p style="font-size:12px; color:#bbbbbb; margin-top:0;">
                Defina quantos contatos de cada grupo você quer trabalhar hoje.
            </p>
        """, unsafe_allow_html=True)

        meta_novos = st.number_input("Meta: Novos", value=0, min_value=0, step=1)
        meta_prom = st.number_input("Meta: Promissores", value=0, min_value=0, step=1)
        meta_leais = st.number_input("Meta: Leais/Campeões", value=0, min_value=0, step=1)
        meta_risco = st.number_input("Meta: Em risco", value=0, min_value=0, step=1)

    filtros = {
        "min_dias": min_dias,
        "max_dias": max_dias,
        "min_valor": min_val,
        "max_valor": max_val,
        "telefone": telefone,
    }

    metas = {
        "meta_novos": meta_novos,
        "meta_prom": meta_prom,
        "meta_leais": meta_leais,
        "meta_risco": meta_risco,
    }

    return filtros, metas

# =========================================================
# (8) 🔍 BUILDER — MONTAR df_dia
# =========================================================

def build_daily_tasks_df(base, telefones_agendados, filtros, metas, usuario_atual):
    # ✅ DEBUG - ADICIONAR TEMPORARIAMENTE
    logger.info(f"🔍 DEBUG - Iniciando build_daily_tasks_df")
    logger.info(f"🔍 DEBUG - Tipo de 'base': {type(base)}, Tamanho: {len(base) if base is not None else 'None'}")
    logger.info(f"🔍 DEBUG - Colunas: {base.columns.tolist() if base is not None else 'None'}")
    
    if base is None or len(base) == 0:
        logger.error("❌ ERRO: 'base' está vazio!")
        return pd.DataFrame()
    
    # ✅ PRIMEIRO: Carregar locks
    df_locks = load_em_atendimento()
    telefones_bloqueados = set()
    
    if not df_locks.empty:
        df_locks_outros = df_locks[df_locks["Usuario"] != usuario_atual]
        telefones_bloqueados = set(df_locks_outros["Telefone"].astype(str))
        logger.info(f"🔒 {len(telefones_bloqueados)} clientes bloqueados")
    
    # ✅ SEGUNDO: Definir base_ck
    logger.info(f"🔍 DEBUG - Criando base_ck...")
    base_ck = base[
        (~base["Telefone"].isin(telefones_agendados)) &
        (~base["Telefone"].isin(telefones_bloqueados))
    ].copy()
    logger.info(f"🔍 DEBUG - base_ck criado com {len(base_ck)} registros")
    # ✅ SEGUNDO: Definir base_ck
    logger.info(f"🔍 DEBUG - Criando base_ck...")
    logger.info(f"🔍 Base original: {len(base)} clientes")
    logger.info(f"🔍 Telefones agendados: {len(telefones_agendados)}")
    logger.info(f"🔍 Telefones bloqueados (em atendimento): {len(telefones_bloqueados)}")
    
   # ✅ NOVO: Normalizar telefones para comparação correta
    telefones_agendados_limpo = {limpar_telefone(str(t)) for t in telefones_agendados if t}

# Filtrar base de check-in (remove quem já tem agendamento)
    base_ck = base[
        (~base["Telefone"].isin(telefones_agendados)) &
        (~base["Telefone_limpo"].isin(telefones_agendados_limpo)) &
        (~base["Telefone"].isin(telefones_bloqueados))
    ].copy()

    
    logger.info(f"✅ base_ck após filtrar: {len(base_ck)} clientes disponíveis para checkin")

    
    logger.info(f"✅ base_ck após filtrar: {len(base_ck)} clientes disponíveis para checkin")

    # ✅ TERCEIRO: Filtrar por classificação
    novos = base_ck[
        (base_ck["Classificação"] == "Novo") &
        (base_ck["Dias_num"].fillna(0) >= Config.DIAS_MINIMO_NOVOS)
    ].sort_values("Dias_num").head(metas["meta_novos"])

    prom = base_ck[
        base_ck["Classificação"] == "Promissor"
    ].sort_values("Dias_num", ascending=False).head(metas["meta_prom"])

    leais = base_ck[
        base_ck["Classificação"].isin(["Leal","Campeão"])
    ].sort_values("Dias_num", ascending=False).head(metas["meta_leais"])

    risco = base_ck[
        base_ck["Classificação"] == "Em risco"
    ].sort_values("Dias_num").head(metas["meta_risco"])

    frames = [df for df in [novos, prom, leais, risco] if not df.empty]
    df_dia = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=base.columns)

    # Normalizar telefone para ID
    if not df_dia.empty:
        df_dia["ID"] = df_dia["Telefone_limpo"]

    # Filtrar concluídos/pulados
    ocultos = st.session_state["concluidos"].union(st.session_state["pulados"])
    df_dia = df_dia[~df_dia["Telefone"].isin(ocultos)]

    # Aplicar filtros
    df_dia = df_dia[df_dia["Dias_num"].fillna(0).between(filtros["min_dias"], filtros["max_dias"])]
    df_dia = df_dia[df_dia["Valor_num"].fillna(0).between(filtros["min_valor"], filtros["max_valor"])]

    # Filtro de telefone
    if filtros["telefone"]:
        clean = limpar_telefone(filtros["telefone"])
        df_dia = df_dia[df_dia["Telefone_limpo"].str.contains(clean, na=False)]

    # Indicador visual na sidebar
    if not df_locks.empty and len(df_locks) > 0:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 👥 Em atendimento agora:")
        for _, lock in df_locks.iterrows():
            emoji = "🟢" if lock["Usuario"] == usuario_atual else "🔴"
            tempo_lock = pd.to_datetime(lock["Timestamp"])
            minutos_ago = int((datetime.now() - tempo_lock).total_seconds() / 60)
            st.sidebar.write(f"{emoji} **{lock['Usuario']}**: {lock['Cliente']} ({minutos_ago}min atrás)")

    logger.info(f"✅ Tarefas do dia geradas: {len(df_dia)} clientes")
    return df_dia



# =========================================================
# (9) 🖥️ UI — ABAS PRINCIPAIS
# =========================================================
def render_aba1(aba, df_dia, metas):
    with aba:
        # ✅ NOVO: Obter e validar usuário atual
        usuario_atual = obter_usuario_atual()
        
        if not usuario_atual or usuario_atual.strip() == "":
            st.warning("⚠️ **Por favor, identifique-se na barra lateral antes de continuar**")
            st.info("👈 Digite seu nome no campo 'Seu nome' na sidebar")
            st.stop()
        # ==========================================
        # SEÇÃO 1: ACOMPANHAMENTO DE SUPORTE
        # ==========================================
        st.markdown("## 🛠️ Acompanhamento de Suporte")
        st.markdown("---")
        
        df_suporte = load_casos_suporte()
        
        if df_suporte.empty:
            st.info("✅ Nenhum caso de suporte pendente")
        else:
            total_suporte = len(df_suporte)
            concluidos_suporte = len([t for t in df_suporte["Telefone"] if str(t) in st.session_state["concluidos"]])
            
            st.markdown(f"**📊 Casos pendentes:** {total_suporte - concluidos_suporte}/{total_suporte}")
            
            if total_suporte > 0:
                progresso = concluidos_suporte / total_suporte
                st.progress(progresso)
            
            st.markdown("---")
            
            # Exibir cards de suporte
            for idx, row in df_suporte.iterrows():
                telefone = str(row.get("Telefone", ""))
                
                if telefone in st.session_state["concluidos"] or telefone in st.session_state["pulados"]:
                    continue
                
                id_fix = f"suporte_{limpar_telefone(telefone)}"
                
                acao, motivo, resumo, proxima, vendedor = card_suporte(id_fix, row, usuario_atual)
                
                if acao == "concluir":
                    registrar_agendamento(row, resumo, motivo, proxima.strftime("%d/%m/%Y") if proxima else "", vendedor, tipo_atendimento="Suporte")
                    remover_card(telefone, concluido=True)
                    limpar_caches_volateis()
                    st.session_state["aba_ativa"] = 0
                    st.rerun()
                
                elif acao == "pular":
                    remover_card(telefone, concluido=False)
                    st.session_state["aba_ativa"] = 0
                    st.rerun()
        
        st.markdown("<br><br>", unsafe_allow_html=True)

        
        # ✅ NOVO: Auto-refresh suave a cada 30 segundos
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        
        tempo_decorrido = (datetime.now() - st.session_state.last_refresh).total_seconds()
        
        if tempo_decorrido > 30:
            load_em_atendimento.clear()
            load_agendamentos_hoje.clear()
            st.session_state.last_refresh = datetime.now()
            logger.info("🔄 Auto-refresh de dados executado (30s)")

        st.header("🎯 Tarefas do dia")

        # =========================================================
        # 🔍 Carregar agendamentos e fazer JOIN com base principal
        # =========================================================
        df_ag_hoje = load_agendamentos_hoje()
        df_base_completa = load_sheet(Config.SHEET_ID, Config.SHEET_NAME)

    
        if not df_ag_hoje.empty and not df_base_completa.empty:
            df_ag_hoje["Telefone_limpo"] = df_ag_hoje["Telefone"].apply(limpar_telefone)
            df_ag_hoje = df_ag_hoje.merge(
                df_base_completa[["Telefone_limpo", "Dias_num", "Compras", "Data"]],
                on="Telefone_limpo",
                how="left",
                suffixes=("", "_base")
            )
            logger.info(f"✅ Join realizado: {len(df_ag_hoje)} agendamentos com dados da base")

        qtd_checkin = len(df_dia)
        qtd_agendamentos = len(df_ag_hoje)
        total_dia = qtd_checkin + qtd_agendamentos

        # Contar concluídos
        telefones_do_dia = set()
        if not df_dia.empty:
            telefones_do_dia.update(df_dia["Telefone"].astype(str).tolist())
        if not df_ag_hoje.empty:
            telefones_do_dia.update(df_ag_hoje["Telefone"].astype(str).tolist())
        
        concluidos_hoje = len(st.session_state["concluidos"].intersection(telefones_do_dia))

        # Progresso
        if total_dia > 0:
            progresso = min(concluidos_hoje / total_dia, 1.0)
        else:
            progresso = 0.0

        # Barra de progresso
        st.markdown("### Progresso do Dia")
        st.progress(progresso)
        st.write(f"**{concluidos_hoje} de {total_dia} contatos concluídos** ({progresso*100:.1f}%)")

        if "baloes_mostrados" not in st.session_state:
            st.session_state["baloes_mostrados"] = False

        if progresso == 0:
            st.info("🚀 Começando agora! Vamos iniciar os atendimentos.")
        elif progresso < 0.25:
            st.info("🔥 Bom começo! Continue nesse ritmo.")
        elif progresso < 0.50:
            st.success("💪 Rumo à metade!")
        elif progresso < 0.75:
            st.success("🟩 Ótimo! Mais da metade concluída!")
        elif progresso < 1:
            st.success("🏁 Quase lá!")
        else:
            if not st.session_state["baloes_mostrados"]:
                st.balloons()
                st.session_state["baloes_mostrados"] = True
            st.success("🎉 Dia concluído!")

        colA, colB, colC = st.columns(3)

        with colA:
            st.metric("📅 Total do Dia", total_dia, f"{qtd_checkin} Check-in + {qtd_agendamentos} Agend.")

        with colB:
            st.metric(
                "🟦 Check-in Programados",
                qtd_checkin,
                f"Meta: {metas['meta_novos'] + metas['meta_prom'] + metas['meta_leais'] + metas['meta_risco']}"
            )

        with colC:
            st.metric("🟧 Agendamentos de Hoje", qtd_agendamentos)

        st.markdown("---")

        # =========================================================
        # 🟣 SELETOR DE MODO
        # =========================================================
        modo = st.selectbox(
            "Modo de atendimento",
            ["Clientes para Check-in (Base de Leitura)", "Agendamentos Ativos"],
            key="modo_filtro_aba1"
        )

        # =========================================================
        # 🟦 MODO CHECK-IN
        # =========================================================
        if modo == "Clientes para Check-in (Base de Leitura)":

            class_filter = st.radio(
                "Filtrar por classificação:",
                Config.CLASSIFICACOES,
                horizontal=True,
            )

            df_checkin = df_dia.copy()
            if class_filter != "Todos":
                df_checkin = df_checkin[df_checkin["Classificação"] == class_filter]

            df_checkin = df_checkin.reset_index(drop=True)

            if df_checkin.empty:
                st.balloons()
                st.success("🎉 **Parabéns!** Todos os check-ins foram concluídos!")
                st.info("💡 **Próximos passos:**")
                st.write("- Ajuste os filtros na barra lateral para ver mais clientes")
                st.write("- Verifique a aba 'Agendamentos Ativos'")
                st.write("- Confira os indicadores na aba 'Indicadores'")
                        
                col1, col2 = st.columns(2)
                col1.metric("✅ Concluídos hoje", concluidos_hoje)
                col2.metric("⏭ Pulados hoje", len(st.session_state["pulados"]))
            else:
                st.subheader("📌 Atendimentos do dia (Check-in)")

                # CSV
                csv = df_checkin.drop(columns=["Telefone_limpo", "ID"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
                st.download_button("📥 Baixar lista (CSV)", csv, "checkin_dia.csv")

                st.markdown("---")

                # Cards (2 por linha)
                for i in range(0, len(df_checkin), 2):
                    col1, col2 = st.columns(2)

                    # CARD 1
                    row1 = df_checkin.iloc[i]
                    with col1:
                        ac, mot, res, prox, vend = card_component(row1["ID"], row1, usuario_atual)

                        if ac == "concluir":
                            registrar_agendamento(row1, res, mot, prox.strftime("%d/%m/%Y") if prox else "", vend)
                            remover_card(row1["Telefone"], True)
                            st.session_state["aba_ativa"] = 0
                            st.rerun()
                        elif ac == "pular":
                            remover_card(row1["Telefone"], False)
                            st.session_state["aba_ativa"] = 0
                            st.rerun()

                    # CARD 2
                    if i + 1 < len(df_checkin):
                        row2 = df_checkin.iloc[i + 1]
                        with col2:
                            ac2, mot2, res2, prox2, vend2 = card_component(row2["ID"], row2, usuario_atual)

                            if ac2 == "concluir":
                                registrar_agendamento(row2, res2, mot2, prox2.strftime("%d/%m/%Y") if prox2 else "", vend2)
                                remover_card(row2["Telefone"], True)
                                st.session_state["aba_ativa"] = 0
                                st.rerun()
                            elif ac2 == "pular":
                                remover_card(row2["Telefone"], False)
                                st.session_state["aba_ativa"] = 0
                                st.rerun()

        # =========================================================
        # 🟧 MODO AGENDAMENTOS ATIVOS
        # =========================================================
        elif modo == "Agendamentos Ativos":
            
            st.subheader("📂 Agendamentos Ativos (Hoje)")

            # Debug expandido
            with st.expander("🔍 Debug: Ver agendamentos de hoje", expanded=False):
                st.write(f"**Agendamentos para hoje:** {len(df_ag_hoje)}")
                
                if not df_ag_hoje.empty:
                    st.write(f"**Colunas disponíveis:** {', '.join(df_ag_hoje.columns.tolist())}")
                    st.write("**Primeiros 10 registros:**")
                    st.dataframe(df_ag_hoje.head(10))

            if df_ag_hoje.empty:
                st.warning("📭 Nenhum agendamento encontrado para hoje.")
                st.info("💡 **Possíveis razões:**")
                st.write("1. Não há agendamentos programados para hoje")
                st.write("2. Verifique se a 'Próxima data' nos agendamentos está correta")
                st.write("3. Crie novos agendamentos na aba 'Check-in'")
            else:
                # ✅ NORMALIZAR para formato igual ao check-in
                df_ag_normalizado = df_ag_hoje.copy()
                
                # Mapear colunas
                if "Nome" in df_ag_normalizado.columns and "Cliente" not in df_ag_normalizado.columns:
                    df_ag_normalizado["Cliente"] = df_ag_normalizado["Nome"]
                
                # Garantir colunas necessárias
                colunas_obrigatorias = {
                    "Cliente": "—",
                    "Telefone": "—",
                    "Classificação": "—",
                    "Valor": "—",
                    "Dias_num": None
                }
                
                for col, default in colunas_obrigatorias.items():
                    if col not in df_ag_normalizado.columns:
                        df_ag_normalizado[col] = default
                
                # Criar ID
                df_ag_normalizado["ID"] = df_ag_normalizado["Telefone"].astype(str).apply(limpar_telefone)
                df_ag_normalizado = df_ag_normalizado.reset_index(drop=True)
                
                # Filtrar concluídos/pulados
                ocultos = st.session_state["concluidos"].union(st.session_state["pulados"])

                if "Telefone_limpo" in df_ag_normalizado.columns:
                    df_ag_normalizado = df_ag_normalizado[
                        (~df_ag_normalizado["Telefone"].isin(ocultos)) &
                        (~df_ag_normalizado["Telefone_limpo"].isin(ocultos))
                    ]
                else:
                    df_ag_normalizado = df_ag_normalizado[~df_ag_normalizado["Telefone"].isin(ocultos)]

                logger.info(f"Agendamentos após filtrar ocultos: {len(df_ag_normalizado)}")

                if df_ag_normalizado.empty:
                    st.success("🎉 Todos os agendamentos de hoje foram concluídos!")
                else:
                    # CSV para download
                    csv_ag = df_ag_normalizado.drop(columns=["ID", "Telefone_limpo"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
                    st.download_button("📥 Baixar agendamentos (CSV)", csv_ag, "agendamentos_hoje.csv")

                    st.markdown("---")

                    # Cards (2 por linha)
                    for i in range(0, len(df_ag_normalizado), 2):
                        col1, col2 = st.columns(2)

                        # CARD 1
                        row1 = df_ag_normalizado.iloc[i]
                        with col1:
                            st.markdown("🔔 **AGENDAMENTO ATIVO**")
                            
                            ac, mot, res, prox, vend = card_component(row1["ID"], row1, usuario_atual)

                            if ac == "concluir":
                                registrar_agendamento(row1, res, mot, prox.strftime("%d/%m/%Y") if prox else "", vend)
                                remover_card(row1["Telefone"], True)
                                st.session_state["aba_ativa"] = 0
                                st.rerun()
                            elif ac == "pular":
                                remover_card(row1["Telefone"], False)
                                st.session_state["aba_ativa"] = 0
                                st.rerun()

                        # CARD 2
                        if i + 1 < len(df_ag_normalizado):
                            row2 = df_ag_normalizado.iloc[i + 1]
                            with col2:
                                st.markdown("🔔 **AGENDAMENTO ATIVO**")
                                
                                ac2, mot2, res2, prox2, vend2 = card_component(row2["ID"], row2, usuario_atual)

                                if ac2 == "concluir":
                                    registrar_agendamento(row2, res2, mot2, prox2.strftime("%d/%m/%Y") if prox2 else "", vend2)
                                    remover_card(row2["Telefone"], True)
                                    st.session_state["aba_ativa"] = 0
                                    st.rerun()
                                elif ac2 == "pular":
                                    remover_card(row2["Telefone"], False)
                                    st.session_state["aba_ativa"] = 0
                                    st.rerun()

def render_aba2(aba, base, total_tarefas):
    """Aba de Indicadores e Análises com filtros de data"""
    
    with aba:
        # ✅ Força manter na aba 2 durante interações
        if "forcar_aba2" not in st.session_state:
            st.session_state.forcar_aba2 = False
        
        st.session_state.forcar_aba2 = True
        
        st.header("📊 Indicadores & Performance")
        
        # =========================================================
        # 🎛️ SEÇÃO 1: FILTROS DE DATA
        # =========================================================
        st.markdown("### 🎛️ Filtros de Período e Classificações")
        
        # ✅ USAR FORM para evitar reruns constantes
        with st.form(key="filtros_aba2", clear_on_submit=False):
            col_filtro1, col_filtro2, col_filtro3 = st.columns([2, 2, 2])


            
            with col_filtro1:
                periodo = st.selectbox(
                    "Selecione o período:",
                    ["Hoje", "Últimos 7 dias", "Últimos 30 dias", "Este mês", "Personalizado"],
                    key="periodo_filtro"
                )
            
            # Calcular datas baseado no período selecionado
            hoje = datetime.now()
            
            # Mostrar date pickers se for personalizado
            mostrar_custom = (periodo == "Personalizado")
            
            if mostrar_custom:
                with col_filtro2:
                    data_inicio = st.date_input(
                        "Data inicial:",
                        value=hoje - pd.Timedelta(days=30),
                        key="data_inicio_custom"
                    )
                
                with col_filtro3:
                    data_fim = st.date_input(
                        "Data final:",
                        value=hoje,
                        key="data_fim_custom"
                    )
            
            st.markdown("---")
            
            # Filtro de classificações
            if not base.empty:
                todas_classificacoes = base["Classificação"].dropna().unique().tolist()
                todas_classificacoes = [c for c in todas_classificacoes if c and str(c).strip()]
                todas_classificacoes = sorted(todas_classificacoes)
            else:
                todas_classificacoes = []
            
            classificacoes_padrao = [c for c in todas_classificacoes if c != "Dormente"]
            
            classificacoes_selecionadas = st.multiselect(
                "🏷️ Selecione as classificações:",
                options=todas_classificacoes,
                default=classificacoes_padrao,
                key="filtro_classificacoes"
            )
            
            # ✅ BOTÃO APLICAR (só recarrega quando clicar)
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
            
            with col_btn1:
                aplicar = st.form_submit_button("🔍 Aplicar Filtros", use_container_width=True, type="primary")
            
            with col_btn2:
                limpar = st.form_submit_button("🔄 Resetar", use_container_width=True)
        
        # ✅ Processar filtros APÓS o form
        if limpar:
            st.session_state.filtro_classificacoes = classificacoes_padrao
            st.session_state.periodo_filtro = "Últimos 30 dias"
            st.rerun()
        
        # Calcular datas finais
        if periodo == "Hoje":
            data_inicio = hoje.replace(hour=0, minute=0, second=0)
            data_fim = hoje.replace(hour=23, minute=59, second=59)
        elif periodo == "Últimos 7 dias":
            data_inicio = hoje - pd.Timedelta(days=7)
            data_fim = hoje
        elif periodo == "Últimos 30 dias":
            data_inicio = hoje - pd.Timedelta(days=30)
            data_fim = hoje
        elif periodo == "Este mês":
            data_inicio = hoje.replace(day=1, hour=0, minute=0, second=0)
            data_fim = hoje
        else:  # Personalizado
            if mostrar_custom:
                data_inicio = datetime.combine(data_inicio, datetime.min.time())
                data_fim = datetime.combine(data_fim, datetime.max.time())
            else:
                data_inicio = hoje - pd.Timedelta(days=30)
                data_fim = hoje
        
        st.info(f"📅 **Período:** {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}")
        
        # Validar classificações
        if not classificacoes_selecionadas:
            st.warning("⚠️ Selecione pelo menos uma classificação")
            st.stop()
        
        # Aplicar filtro
        base_filtrada = base[base["Classificação"].isin(classificacoes_selecionadas)].copy()
        
        total_selecionado = len(base_filtrada)
        total_geral = len(base)
        percentual = (total_selecionado / total_geral * 100) if total_geral > 0 else 0
        
        col_info1, col_info2, col_info3 = st.columns([2, 1, 1])
        
        with col_info1:
            st.info(f"🔍 **Analisando:** {', '.join(classificacoes_selecionadas)}")
        
        st.markdown("---")

        
        # =========================================================
        # 📊 SEÇÃO 2: MÉTRICAS PRINCIPAIS (COM FILTRO)
        # =========================================================
        st.markdown("### 📈 Resumo do Período")
        
        # Carregar histórico
        df_historico = load_historico()
        
        # Filtrar histórico por data
        if not df_historico.empty and "Data_de_contato" in df_historico.columns:
            # Converter data de contato
            df_historico["Data_convertida"] = pd.to_datetime(
                df_historico["Data_de_contato"], 
                format="%d/%m/%Y %H:%M",
                errors="coerce"
            )
            
            # Filtrar pelo período
            df_historico_filtrado = df_historico[
                (df_historico["Data_convertida"] >= data_inicio) &
                (df_historico["Data_convertida"] <= data_fim)
            ]
            
            total_checkins = len(df_historico_filtrado)
        else:
            df_historico_filtrado = pd.DataFrame()
            total_checkins = 0
        
        # Carregar agendamentos
        df_agendamentos = load_df_agendamentos()
        
        # Filtrar agendamentos por data
        if not df_agendamentos.empty:
            # Tentar converter data de contato
            if "Data_de_contato" in df_agendamentos.columns:
                df_agendamentos["Data_convertida"] = pd.to_datetime(
                    df_agendamentos["Data_de_contato"],
                    format="%d/%m/%Y %H:%M",
                    errors="coerce"
                )
                
                df_agendamentos_filtrado = df_agendamentos[
                    (df_agendamentos["Data_convertida"] >= data_inicio) &
                    (df_agendamentos["Data_convertida"] <= data_fim)
                ]
                
                total_agendamentos = len(df_agendamentos_filtrado)
            else:
                df_agendamentos_filtrado = df_agendamentos
                total_agendamentos = len(df_agendamentos)
        else:
            df_agendamentos_filtrado = pd.DataFrame()
            total_agendamentos = 0
        
        # Exibir métricas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "✅ Check-ins Realizados",
                total_checkins,
                help=f"Total de check-ins no período selecionado"
            )
        
        with col2:
            st.metric(
                "📅 Agendamentos Criados",
                total_agendamentos,
                help=f"Agendamentos criados no período"
            )
        
        with col3:
            # Calcular receita do período (histórico)
            if not df_historico_filtrado.empty and "Valor" in df_historico_filtrado.columns:
                # Converter valores
                def extrair_valor(v):
                    try:
                        v_str = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
                        return float(v_str)
                    except:
                        return 0
                
                df_historico_filtrado["Valor_num"] = df_historico_filtrado["Valor"].apply(extrair_valor)
                receita_periodo = df_historico_filtrado["Valor_num"].sum()
            else:
                receita_periodo = 0
            
            st.metric(
                "💰 Receita do Período",
                f"R$ {receita_periodo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                help="Soma dos valores de check-ins realizados"
            )
        
        with col4:
            # Ticket médio do período
            if total_checkins > 0 and receita_periodo > 0:
                ticket_medio_periodo = receita_periodo / total_checkins
            else:
                ticket_medio_periodo = 0
            
            st.metric(
                "🎯 Ticket Médio",
                f"R$ {ticket_medio_periodo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                help="Receita média por check-in"
            )
        
        st.markdown("---")
        
               # =========================================================
        # 📊 SEÇÃO 3: GRÁFICO DE BARRAS - PESSOAS POR CLASSIFICAÇÃO
        # =========================================================
        st.markdown("### 📊 Distribuição de Clientes por Classificação")
        
        if not base_filtrada.empty:  # ✅ Usar base_filtrada
            # ✅ LIMPEZA DE DADOS - Remover duplicados e vazios
            base_limpa = base_filtrada.copy()  # ✅ Usar base_filtrada

            
            # Remover linhas onde Cliente está vazio
            base_limpa = base_limpa[base_limpa["Cliente"].notna()]
            base_limpa = base_limpa[base_limpa["Cliente"].astype(str).str.strip() != ""]
            
            # Remover linhas onde Telefone está vazio
            if "Telefone" in base_limpa.columns:
                base_limpa = base_limpa[base_limpa["Telefone"].notna()]
                base_limpa = base_limpa[base_limpa["Telefone"].astype(str).str.strip() != ""]
            
            # ✅ REMOVER DUPLICADOS por telefone (cliente único)
            if "Telefone_limpo" in base_limpa.columns:
                base_limpa = base_limpa.drop_duplicates(subset=["Telefone_limpo"], keep="first")
            elif "Telefone" in base_limpa.columns:
                base_limpa = base_limpa.drop_duplicates(subset=["Telefone"], keep="first")
            
            logger.info(f"🔍 Base original: {len(base)} | Base limpa: {len(base_limpa)}")
            
            col_grafico, col_tabela = st.columns([2, 1])
            
            with col_grafico:
                # Contar por classificação (usando base limpa)
                dist_class = base_limpa["Classificação"].value_counts().sort_values(ascending=True)
                
                # Criar DataFrame para o gráfico
                df_grafico = pd.DataFrame({
                    "Classificação": dist_class.index,
                    "Quantidade": dist_class.values
                })
                
                # Gráfico de barras horizontal
                st.bar_chart(
                    df_grafico.set_index("Classificação"),
                    height=400,
                    use_container_width=True
                )
            
            with col_tabela:
                st.markdown("**📋 Detalhamento:**")
                
                # Criar tabela com percentuais
                df_tabela = pd.DataFrame({
                    "Classificação": dist_class.index,
                    "Qtd": dist_class.values
                })
                
                total_clientes = df_tabela["Qtd"].sum()
                df_tabela["Percentual"] = (df_tabela["Qtd"] / total_clientes * 100).round(1).astype(str) + "%"
                
                st.dataframe(
                    df_tabela,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Mostrar total
                st.info(f"📊 **Total de clientes únicos:** {total_clientes:,}".replace(",", "."))
                
                # Destaques
                st.markdown("**🎯 Destaques:**")
                maior_grupo = df_tabela.iloc[0]
                st.success(f"**{maior_grupo['Classificação']}**: {maior_grupo['Qtd']} clientes ({maior_grupo['Percentual']})")
                
                # ✅ DEBUG: Mostrar contagem de duplicados removidos
                duplicados_removidos = len(base_filtrada) - len(base_limpa)
                if duplicados_removidos > 0:
                    st.warning(f"⚠️ {duplicados_removidos} duplicados removidos da análise")
        else:
            st.warning("⚠️ Nenhum dado disponível na base")
        
            st.markdown("---")
        
        # =========================================================
        # 📈 SEÇÃO 3.5: ANÁLISE DE CRESCIMENTO POR CLASSIFICAÇÃO
        # =========================================================
        st.markdown("### 📈 Evolução das Classificações")
        
        if not base.empty:
            # Calcular período anterior (mesmo tamanho do período selecionado)
            duracao_periodo = (data_fim - data_inicio).days
            data_inicio_anterior = data_inicio - pd.Timedelta(days=duracao_periodo)
            data_fim_anterior = data_inicio - pd.Timedelta(days=1)
            
            st.info(f"📊 **Comparando:** Período atual vs período anterior ({duracao_periodo} dias)")
            
            # Carregar histórico completo
            df_historico_completo = load_historico()
            
            if not df_historico_completo.empty and "Data_de_contato" in df_historico_completo.columns:
                # Converter datas
                df_historico_completo["Data_convertida"] = pd.to_datetime(
                    df_historico_completo["Data_de_contato"],
                    format="%d/%m/%Y %H:%M",
                    errors="coerce"
                )
                
                # Filtrar período atual
                df_periodo_atual = df_historico_completo[
                    (df_historico_completo["Data_convertida"] >= data_inicio) &
                    (df_historico_completo["Data_convertida"] <= data_fim)
                ].copy()
                
                # Filtrar período anterior
                df_periodo_anterior = df_historico_completo[
                    (df_historico_completo["Data_convertida"] >= data_inicio_anterior) &
                    (df_historico_completo["Data_convertida"] <= data_fim_anterior)
                ].copy()
                
                # Contar por classificação
                if not df_periodo_atual.empty and not df_periodo_anterior.empty:
                    # Contar classificações no período atual
                    contagem_atual = df_periodo_atual["Classificação"].value_counts()
                    
                    # Contar classificações no período anterior
                    contagem_anterior = df_periodo_anterior["Classificação"].value_counts()
                    
                    # Criar DataFrame de comparação
                    df_comparacao = pd.DataFrame({
                        "Período Anterior": contagem_anterior,
                        "Período Atual": contagem_atual
                    }).fillna(0)
                    
                    # Calcular variação
                    df_comparacao["Variação Absoluta"] = df_comparacao["Período Atual"] - df_comparacao["Período Anterior"]
                    df_comparacao["Variação %"] = (
                        (df_comparacao["Variação Absoluta"] / df_comparacao["Período Anterior"]) * 100
                    ).replace([float('inf'), -float('inf')], 0).fillna(0).round(1)
                    
                    # Filtrar apenas classificações selecionadas
                    df_comparacao = df_comparacao[df_comparacao.index.isin(classificacoes_selecionadas)]
                    
                    # Ordenar por variação percentual
                    df_comparacao = df_comparacao.sort_values("Variação %", ascending=False)
                    
                    col_graficos, col_tabela = st.columns([2, 1])
                    
                    with col_graficos:
                        st.markdown("**📊 Variação Percentual por Classificação:**")
                        
                        # Criar gráfico de barras
                        import plotly.graph_objects as go
                        
                        cores_variacao = [
                            '#00C851' if v > 0 else '#ff4444' if v < 0 else '#33b5e5'
                            for v in df_comparacao["Variação %"]
                        ]
                        
                        fig = go.Figure(data=[
                            go.Bar(
                                x=df_comparacao.index,
                                y=df_comparacao["Variação %"],
                                marker_color=cores_variacao,
                                text=[f"{v:+.1f}%" for v in df_comparacao["Variação %"]],
                                textposition='outside'
                            )
                        ])
                        
                        fig.update_layout(
                            title="Crescimento/Redução por Classificação (%)",
                            xaxis_title="Classificação",
                            yaxis_title="Variação (%)",
                            height=400,
                            showlegend=False,
                            hovermode='x'
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col_tabela:
                        st.markdown("**📋 Detalhamento:**")
                        
                        # Formatar tabela para exibição
                        df_exibir = df_comparacao.copy()
                        df_exibir["Período Anterior"] = df_exibir["Período Anterior"].astype(int)
                        df_exibir["Período Atual"] = df_exibir["Período Atual"].astype(int)
                        df_exibir["Variação Absoluta"] = df_exibir["Variação Absoluta"].apply(
                            lambda x: f"+{int(x)}" if x > 0 else str(int(x))
                        )
                        df_exibir["Variação %"] = df_exibir["Variação %"].apply(
                            lambda x: f"+{x:.1f}%" if x > 0 else f"{x:.1f}%"
                        )
                        
                        st.dataframe(
                            df_exibir,
                            use_container_width=True
                        )
                    
                    # Cards de destaques
                    st.markdown("---")
                    st.markdown("**🎯 Destaques de Crescimento:**")
                    
                    col_d1, col_d2, col_d3 = st.columns(3)
                    
                    # Maior crescimento percentual
                    if len(df_comparacao) > 0:
                        maior_crescimento = df_comparacao["Variação %"].idxmax()
                        valor_crescimento = df_comparacao.loc[maior_crescimento, "Variação %"]
                        
                        with col_d1:
                            if valor_crescimento > 0:
                                st.success(f"📈 **Maior Crescimento**\n\n{maior_crescimento}\n\n+{valor_crescimento:.1f}%")
                            else:
                                st.info(f"📊 **Crescimento**\n\nSem crescimentos positivos")
                        
                        # Maior redução
                        menor_crescimento = df_comparacao["Variação %"].idxmin()
                        valor_reducao = df_comparacao.loc[menor_crescimento, "Variação %"]
                        
                        with col_d2:
                            if valor_reducao < 0:
                                st.error(f"📉 **Maior Redução**\n\n{menor_crescimento}\n\n{valor_reducao:.1f}%")
                            else:
                                st.success(f"✅ **Redução**\n\nSem reduções negativas")
                        
                        # Mais estável
                        mais_estavel = df_comparacao["Variação %"].abs().idxmin()
                        valor_estavel = df_comparacao.loc[mais_estavel, "Variação %"]
                        
                        with col_d3:
                            st.info(f"🔄 **Mais Estável**\n\n{mais_estavel}\n\n{valor_estavel:+.1f}%")
                    
                    # Download
                    csv_crescimento = df_comparacao.to_csv().encode("utf-8-sig")
                    st.download_button(
                        "📥 Baixar Análise de Crescimento (CSV)",
                        csv_crescimento,
                        "crescimento_classificacoes.csv",
                        use_container_width=True
                    )
                
                else:
                    st.warning("⚠️ Não há dados suficientes para comparar os períodos")
                    
                    if df_periodo_atual.empty:
                        st.info(f"📭 Período atual ({data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}): Sem registros")
                    
                    if df_periodo_anterior.empty:
                        st.info(f"📭 Período anterior ({data_inicio_anterior.strftime('%d/%m/%Y')} a {data_fim_anterior.strftime('%d/%m/%Y')}): Sem registros")
            
            else:
                st.warning("⚠️ Histórico não disponível para análise de crescimento")
                st.info("💡 Para ver a evolução, é necessário ter check-ins registrados no histórico")
        
        else:
            st.warning("⚠️ Nenhum dado disponível")


        
        # =========================================================
        # 🍰 SEÇÃO 4: GRÁFICO DE PIZZA - CLASSIFICAÇÕES
        # =========================================================
        st.markdown("### 🍰 Proporção de Classificações Selecionadas")
        
        if not base_filtrada.empty:
            # ✅ LIMPEZA: Remover duplicados antes de contar
            base_pizza = base_filtrada.copy()
            
            # Remover linhas vazias
            base_pizza = base_pizza[base_pizza["Cliente"].notna()]
            base_pizza = base_pizza[base_pizza["Cliente"].astype(str).str.strip() != ""]
            
            # Remover duplicados por telefone (garantir clientes únicos)
            if "Telefone_limpo" in base_pizza.columns:
                base_pizza = base_pizza.drop_duplicates(subset=["Telefone_limpo"], keep="first")
            elif "Telefone" in base_pizza.columns:
                base_pizza = base_pizza.drop_duplicates(subset=["Telefone"], keep="first")
            
            logger.info(f"🍰 Pizza - Base filtrada: {len(base_filtrada)} | Após limpeza: {len(base_pizza)}")
            
            col_pizza, col_legenda = st.columns([2, 1])
            
            with col_pizza:
                # Contar classificações (usando base limpa)
                dist_pizza = base_pizza["Classificação"].value_counts()
                
                # Calcular percentuais
                total = dist_pizza.sum()
                percentuais = (dist_pizza / total * 100).round(1)
                
                # Criar visualização de pizza em texto
                st.markdown("**📊 Distribuição percentual:**")
                
                # Cores para cada classificação
                cores_map = {
                    "Novo": "🟦",
                    "Promissor": "🟩",
                    "Leal": "🟨",
                    "Campeão": "🟧",
                    "Em risco": "🟥",
                    "Dormente": "⚫"
                }
                
                # Criar barras de progresso
                for classificacao, qtd in dist_pizza.items():
                    perc = percentuais[classificacao]
                    emoji = cores_map.get(classificacao, "⬜")
                    
                    st.markdown(f"{emoji} **{classificacao}**: {perc}%")
                    st.progress(perc / 100)
            
            with col_legenda:
                st.markdown("**📋 Valores absolutos:**")
                
                for classificacao, qtd in dist_pizza.items():
                    perc = percentuais[classificacao]
                    emoji = cores_map.get(classificacao, "⬜")
                    st.write(f"{emoji} **{classificacao}**")
                    st.write(f"   {qtd:,} clientes ({perc}%)".replace(",", "."))
                    st.write("")
                
                st.markdown("---")
                st.info(f"**Total analisado:** {total:,} clientes únicos".replace(",", "."))
                
                # Mostrar se houve duplicados
                duplicados_pizza = len(base_filtrada) - len(base_pizza)
                if duplicados_pizza > 0:
                    st.warning(f"⚠️ {duplicados_pizza} duplicados removidos")
        else:
            st.warning("⚠️ Nenhuma classificação selecionada")
        
        st.markdown("---")


        
        # =========================================================
        # 💰 SEÇÃO 5: RECEITA E TICKET MÉDIO POR CLASSIFICAÇÃO
        # =========================================================
        st.markdown("### 💰 Análise Financeira por Classificação")
        
        if not base.empty:
            # Agrupar por classificação
            analise_financeira = base.groupby("Classificação").agg({
                "Valor_num": ["sum", "mean", "count"]
            }).reset_index()
            
            analise_financeira.columns = ["Classificação", "Receita Total", "Ticket Médio", "Quantidade"]
            
            # Ordenar por receita
            analise_financeira = analise_financeira.sort_values("Receita Total", ascending=False)
            
            # Adicionar percentual da receita
            receita_total_geral = analise_financeira["Receita Total"].sum()
            analise_financeira["% Receita"] = (
                analise_financeira["Receita Total"] / receita_total_geral * 100
            ).round(1)
            
            # Formatar valores para exibição
            df_exibir = analise_financeira.copy()
            df_exibir["Receita Total"] = df_exibir["Receita Total"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            df_exibir["Ticket Médio"] = df_exibir["Ticket Médio"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            df_exibir["% Receita"] = df_exibir["% Receita"].astype(str) + "%"
            
            st.dataframe(
                df_exibir,
                use_container_width=True,
                hide_index=True
            )
            
            # Destaques
            col_dest1, col_dest2, col_dest3 = st.columns(3)
            
            maior_receita = analise_financeira.iloc[0]
            maior_ticket = analise_financeira.loc[analise_financeira["Ticket Médio"].idxmax()]
            maior_volume = analise_financeira.loc[analise_financeira["Quantidade"].idxmax()]
            
            with col_dest1:
                st.success(f"**💰 Maior Receita:**\n\n{maior_receita['Classificação']}\n\nR$ {maior_receita['Receita Total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            with col_dest2:
                st.info(f"**🎯 Maior Ticket:**\n\n{maior_ticket['Classificação']}\n\nR$ {maior_ticket['Ticket Médio']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            with col_dest3:
                st.warning(f"**📊 Maior Volume:**\n\n{maior_volume['Classificação']}\n\n{int(maior_volume['Quantidade'])} clientes")
            
            # Download CSV
            csv_financeiro = df_exibir.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 Baixar Análise Financeira (CSV)",
                csv_financeiro,
                "analise_financeira.csv",
                use_container_width=True
            )
        else:
            st.warning("⚠️ Nenhum dado disponível")
        
        st.markdown("---")
        
        # =========================================================
        # ⚠️ SEÇÃO 6: ALERTAS E RISCOS
        # =========================================================
        st.markdown("### ⚠️ Alertas de Clientes em Risco")
        
        if not base_filtrada.empty:  # ✅ Usar base_filtrada
            col_alerta1, col_alerta2 = st.columns(2)
            
            with col_alerta1:
                st.markdown("#### 🚨 **Clientes em Risco**")
                
                clientes_risco = base_filtrada[base_filtrada["Classificação"] == "Em risco"].copy()

                clientes_risco = clientes_risco.sort_values("Dias_num", ascending=False).head(10)
                
                if not clientes_risco.empty:
                    st.error(f"⚠️ **{len(base_filtrada[base_filtrada['Classificação'] == 'Em risco'])} clientes** precisam de atenção!")
                    
                    df_risco = clientes_risco[["Cliente", "Dias_num", "Valor", "Telefone"]].copy()
                    df_risco.columns = ["Cliente", "Dias sem comprar", "Último valor", "Telefone"]
                    
                    st.dataframe(
                        df_risco,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.success("✅ Nenhum cliente em risco!")
            
            with col_alerta2:
                st.markdown("#### 😴 **Prestes a Ficar Dormentes**")
                
                # Clientes que não são dormentes mas estão há muito tempo sem comprar
                prestes_dormentes = base_filtrada[
                    (base["Classificação"] != "Dormente") &
                    (base["Dias_num"].fillna(0) > 120)  # Mais de 120 dias
                ].copy()
                
                prestes_dormentes = prestes_dormentes.sort_values("Dias_num", ascending=False).head(10)
                
                if not prestes_dormentes.empty:
                    st.warning(f"😴 **{len(prestes_dormentes)} clientes** prestes a ficar dormentes!")
                    
                    df_dormentes = prestes_dormentes[["Cliente", "Classificação", "Dias_num", "Telefone"]].copy()
                    df_dormentes.columns = ["Cliente", "Status Atual", "Dias inativos", "Telefone"]
                    
                    st.dataframe(
                        df_dormentes,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.success("✅ Nenhum cliente em risco de ficar dormente!")


def render_aba3(aba):
    """Aba de Histórico e Pesquisa de Clientes"""
    
    with aba:
        st.header("🔍 Histórico e Pesquisa")
        st.markdown("---")
        
        # ==========================================
        # SEÇÃO 1: BUSCAR CLIENTE POR TELEFONE
        # ==========================================
        st.subheader("📞 Buscar Cliente")
        
        col_busca1, col_busca2 = st.columns([3, 1])
        
        with col_busca1:
            telefone_para_buscar = st.text_input(
                "Digite o telefone (com ou sem formatação)",
                key="buscar_telefone",
                placeholder="Ex: (11) 98765-4321 ou 11987654321"
            )
        
        # ✅ BUSCAR AUTOMATICAMENTE quando tiver pelo menos 8 dígitos
        if telefone_para_buscar.strip() and len(limpar_telefone(telefone_para_buscar)) >= 8:
            telefone_limpo = limpar_telefone(telefone_para_buscar)
            
            # Carregar base de dados
            base = load_sheet(Config.SHEET_ID, Config.SHEET_NAME)
            base["Telefone_limpo"] = base["Telefone"].apply(limpar_telefone)
            
            # Buscar cliente
            cliente_encontrado = base[base["Telefone_limpo"] == telefone_limpo]
            
            if not cliente_encontrado.empty:
                row = cliente_encontrado.iloc[0]
                
                # ✅ SALVAR NO SESSION STATE
                st.session_state["cliente_selecionado"] = {
                    "nome": row["Cliente"],
                    "telefone": str(row["Telefone"]),
                    "classificacao": row.get("Classificação", "Novo"),
                    "valor": row.get("Valor", 0)
                }
                
                # Exibir informações do cliente
                st.success(f"✅ Cliente encontrado: **{row['Cliente']}**")
                
                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    st.metric("Classificação", row.get("Classificação", "—"))
                with col_info2:
                    st.metric("Total Gasto", safe_valor(row.get("Valor", 0)))
                with col_info3:
                    st.metric("Nº Compras", row.get("Compras", 0))
                
                st.markdown("---")

                
                # ==========================================
                # SEÇÃO 2: HISTÓRICO DO CLIENTE
                # ==========================================
                st.subheader("📋 Histórico de Atendimentos")
                
                df_historico = load_historico()
                
                if not df_historico.empty:
                    # Limpar telefones no histórico
                    df_historico["Telefone_limpo"] = df_historico["Telefone"].apply(limpar_telefone)
                    
                    historico_cliente = df_historico[
                        df_historico["Telefone_limpo"] == telefone_limpo
                    ].sort_values("Data_de_contato", ascending=False)
                    
                    if not historico_cliente.empty:
                        st.write(f"**Total de atendimentos:** {len(historico_cliente)}")
                        
                        # Exibir em tabela formatada
                        colunas_exibir = []
                        mapeamento_colunas = {
                            "Data_de_contato": "Data/Hora",
                            "Classificação": "Classificação",
                            "Relato_da_conversa": "Resumo",
                            "Follow_up": "Próximos Passos",
                            "Vendedor": "Atendente",
                            "Valor": "Valor"
                        }
                        
                        for col_original, col_nova in mapeamento_colunas.items():
                            if col_original in historico_cliente.columns:
                                colunas_exibir.append((col_original, col_nova))
                        
                        df_exibir = historico_cliente[[c[0] for c in colunas_exibir]].copy()
                        df_exibir.columns = [c[1] for c in colunas_exibir]
                        
                        st.dataframe(df_exibir, use_container_width=True, hide_index=True)
                        
                        # Download do histórico
                        csv_historico = df_exibir.to_csv(index=False).encode("utf-8-sig")
                        st.download_button(
                            "📥 Baixar Histórico (CSV)",
                            csv_historico,
                            f"historico_{telefone_limpo}.csv",
                            use_container_width=True
                        )
                    else:
                        st.info("ℹ️ Nenhum atendimento registrado para este cliente")
                else:
                    st.info("ℹ️ Histórico vazio")
                
                st.markdown("---")
                
                # ==========================================
                # SEÇÃO 3: AGENDAMENTOS FUTUROS
                # ==========================================
                st.subheader("📅 Agendamentos Futuros")
                
                df_agendamentos = load_df_agendamentos()
                
                if not df_agendamentos.empty:
                    df_agendamentos["Telefone_limpo"] = df_agendamentos["Telefone"].apply(limpar_telefone)
                    
                    agendamentos_cliente = df_agendamentos[
                        df_agendamentos["Telefone_limpo"] == telefone_limpo
                    ].copy()
                    
                    if not agendamentos_cliente.empty:
                        # Detectar coluna de data
                        colunas_data_possiveis = ["Próxima data", "Data de chamada", "Proxima data", "Data"]
                        coluna_data = None
                        
                        for col in colunas_data_possiveis:
                            if col in agendamentos_cliente.columns:
                                coluna_data = col
                                break
                        
                        if coluna_data:
                            # Converter data
                            agendamentos_cliente["Data_convertida"] = pd.to_datetime(
                                agendamentos_cliente[coluna_data],
                                format="%d/%m/%Y",
                                errors="coerce"
                            )
                            
                            hoje = datetime.now()
                            agendamentos_futuros = agendamentos_cliente[
                                agendamentos_cliente["Data_convertida"] >= hoje
                            ].sort_values("Data_convertida")
                            
                            if not agendamentos_futuros.empty:
                                st.success(f"✅ {len(agendamentos_futuros)} agendamento(s) futuro(s)")
                                
                                for idx, agd in agendamentos_futuros.head(5).iterrows():
                                    data_agd = agd.get(coluna_data, "—")
                                    motivo = agd.get("Follow up", agd.get("Motivo", "—"))
                                    vendedor = agd.get("Vendedor", "—")
                                    st.info(f"📅 {data_agd} • {motivo} • 👤 {vendedor}")
                            else:
                                st.warning("⚠️ Nenhum agendamento futuro")
                        else:
                            st.warning("⚠️ Não foi possível identificar a coluna de data")
                    else:
                        st.info("ℹ️ Nenhum agendamento encontrado para este cliente")
                else:
                    st.info("ℹ️ Nenhum agendamento na base")
                
            else:
                st.warning(f"❌ Nenhum cliente encontrado com o telefone **{telefone_para_buscar}**")
                st.info("**Dicas:**")
                st.write("- Verifique se o telefone está correto")
                st.write("- Tente sem formatação (apenas números)")
                st.write("- Verifique se o cliente está cadastrado na base")
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("---")

        # ==========================================
# PREPARAR DADOS PARA O FORMULÁRIO
# ==========================================

# ✅ NOVO: Se encontrou cliente, salvar no session_state
if buscar and not cliente_encontrado.empty:
    st.session_state["cliente_selecionado"] = {
        "nome": row["Cliente"],
        "telefone": row["Telefone"],
        "classificacao": row.get("Classificação", "Novo"),
        "valor": row.get("Valor", 0)
    }
else:
    # Se não buscou, verificar se já tem no session_state
    if "cliente_selecionado" not in st.session_state:
        st.session_state["cliente_selecionado"] = None


    
        # ==========================================
        # SEÇÃO 4: CRIAR NOVO AGENDAMENTO
        # ==========================================
        st.subheader("➕ Criar Novo Agendamento")
        
        # ✅ MOSTRAR SE TEM CLIENTE SELECIONADO
        dados_cliente = st.session_state.get("cliente_selecionado", None)
        
        if dados_cliente:
            col_aviso, col_limpar = st.columns([3, 1])
            with col_aviso:
                st.info(f"📌 **Cliente selecionado:** {dados_cliente['nome']} • {dados_cliente['telefone']}")
            with col_limpar:
                if st.button("🗑️ Limpar seleção"):
                    st.session_state["cliente_selecionado"] = None
                    st.rerun()
        else:
            st.info("💡 Busque um cliente acima OU preencha manualmente abaixo")
        
        st.markdown("---")
        
        with st.form(key="form_criar_agendamento", clear_on_submit=False):
            col_form1, col_form2 = st.columns(2)
            
            with col_form1:
                # ✅ PEGAR VALORES DO SESSION STATE (se tiver)
                cliente_novo = st.text_input(
                    "Nome do Cliente *",
                    value=dados_cliente["nome"] if dados_cliente else "",
                    key="cliente_novo",
                    placeholder="Digite o nome completo",
                    disabled=dados_cliente is not None
                )
                
                telefone_novo = st.text_input(
                    "Telefone *",
                    value=dados_cliente["telefone"] if dados_cliente else "",
                    key="telefone_novo",
                    placeholder="(11) 98765-4321",
                    disabled=dados_cliente is not None
                )
                
                # ✅ SELECTBOX COM ÍNDICE CORRETO
                opcoes_class = ["Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"]
                
                if dados_cliente:
                    try:
                        indice_class = opcoes_class.index(dados_cliente["classificacao"])
                    except ValueError:
                        indice_class = 0
                else:
                    indice_class = 0
                
                classificacao_nova = st.selectbox(
                    "Classificação",
                    opcoes_class,
                    index=indice_class,
                    key="classificacao_nova"
                )
            
            with col_form2:
                vendedor_novo = st.selectbox(
                    "Responsável *",
                    Config.VENDEDORES,
                    key="vendedor_novo"
                )
                
                proxima_data_novo = st.date_input(
                    "Próxima Data de Contato *",
                    key="proxima_data_novo",
                    min_value=datetime.now().date()
                )
                
                # ✅ SELETOR DE TIPO DE ATENDIMENTO
                tipo_atendimento = st.selectbox(
                    "Tipo de Atendimento *",
                    Config.TIPOS_ATENDIMENTO,
                    key="tipo_novo_agendamento",
                    help="Selecione o tipo adequado para organizar a fila de atendimento"
                )
            
            # ✅ AVISO VISUAL PARA SUPORTE
            if tipo_atendimento == "Suporte":
                st.warning("⚠️ **ATENÇÃO:** Este agendamento será marcado como **CASO DE SUPORTE**")
            elif tipo_atendimento == "Venda":
                st.info("💰 Este agendamento será marcado como **oportunidade de venda**")
            elif tipo_atendimento == "Experiência":
                st.success("✨ Este agendamento será marcado como **melhoria de experiência**")
            
            motivo_novo = st.text_input(
                "Motivo do Contato *",
                key="motivo_novo",
                placeholder="Ex: Acompanhamento de pedido, Follow-up de proposta..."
            )
            
            resumo_novo = st.text_area(
                "Observações/Contexto",
                key="resumo_novo",
                height=100,
                placeholder="Digite aqui o contexto ou observações importantes..."
            )
            
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
            
            with col_btn1:
                criar_agendamento = st.form_submit_button(
                    "💾 Criar Agendamento",
                    use_container_width=True,
                    type="primary"
                )
            
            with col_btn2:
                limpar_form = st.form_submit_button(
                    "🧹 Limpar",
                    use_container_width=True
                )
            
            # ✅ PROCESSAR CRIAÇÃO (SEM ST.RERUN)
            if criar_agendamento:
                if not cliente_novo.strip():
                    st.error("❌ O campo 'Nome do Cliente' é obrigatório")
                elif not telefone_novo.strip():
                    st.error("❌ O campo 'Telefone' é obrigatório")
                elif not motivo_novo.strip():
                    st.error("❌ O campo 'Motivo do Contato' é obrigatório")
                else:
                    # ✅ Criar row fictícia com dados corretos
                    row_ficticia = {
                        "Cliente": cliente_novo,
                        "Classificação": classificacao_nova,
                        "Valor": dados_cliente["valor"] if dados_cliente else 0,
                        "Telefone": telefone_novo,
                        "Compras": 0
                    }
                    try:
                        registrar_agendamento(
                            row_ficticia,
                            resumo_novo if resumo_novo.strip() else "Agendamento criado via pesquisa",
                            motivo_novo,
                            proxima_data_novo.strftime("%d/%m/%Y"),
                            vendedor_novo,
                            tipo_atendimento=tipo_atendimento
                        )  # ✅ FALTAVA ESTE PARÊNTESE
                        
                        # Limpar caches
                        load_agendamentos_ativos.clear()
                        load_df_agendamentos.clear()
                        load_casos_suporte.clear()

# =========================================================
# (10) 🚀 MAIN FLOW
# =========================================================

def main():
    st.title("📅 CRM Sportech – Tarefas do Dia")

    init_session_state()
    
    # ✅ Obter usuário ANTES de tudo
    usuario_atual = obter_usuario_atual()
    
    if not usuario_atual or usuario_atual.strip() == "":
        st.warning("⚠️ **Por favor, identifique-se na barra lateral antes de continuar**")
        st.info("👈 Digite seu nome no campo 'Seu nome' na sidebar")
        st.stop()

    # ✅ Carregar dados
    base = load_sheet(Config.SHEET_ID, Config.SHEET_NAME)
    telefones_agendados = load_agendamentos_ativos()
    
    # ✅ Garantir que todos telefones sejam strings
    telefones_agendados = {str(t).strip() for t in telefones_agendados}
    
    logger.info(f"✅ Telefones com agendamento ativo: {len(telefones_agendados)}")

    # ✅ Renderizar sidebar e obter filtros/metas
    filtros, metas = render_sidebar()

    # ✅ Construir dataframe do dia
    df_dia = build_daily_tasks_df(base, telefones_agendados, filtros, metas, usuario_atual)

    # ✅ CRIAR ABAS - Método tradicional do Streamlit
    aba1, aba2, aba3 = st.tabs(["📋 Tarefas do dia", "📊 Indicadores", "🔍 Histórico/Pesquisa"])

    # ✅ RENDERIZAR CADA ABA
    render_aba1(aba1, df_dia, metas)
    render_aba2(aba2, base, len(df_dia))
    render_aba3(aba3)


if __name__ == "__main__":
    main()
