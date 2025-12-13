import streamlit as st
import pandas as pd
from urllib.parse import quote
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import time
import re
import logging

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
    
    # Cache e Performance
    CACHE_BASE_TTL = 600  # ✅ ALTERADO: 60 → 300 (5 minutos para dados estáveis)
    CACHE_VOLATILE_TTL = 10  # ✅ NOVO: 10 segundos para dados que mudam frequentemente
    LOCK_TIMEOUT_MINUTES = 15  # ✅ NOVO: Timeout para locks de atendimento
    
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


def criar_lock(telefone, usuario, cliente):
    """Cria um lock quando um card é exibido (bloqueia para outros usuários)"""
    try:
        client = get_gsheet_client()
        sh = client.open_by_key(Config.SHEET_ID)
        
        try:
            ws = sh.worksheet("EM_ATENDIMENTO")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet("EM_ATENDIMENTO", rows=1000, cols=4)
            ws.append_row(["Telefone", "Usuario", "Timestamp", "Cliente"])
        
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([str(telefone), str(usuario), agora, str(cliente)])
        
        # Limpar cache para outros usuários verem imediatamente
        load_em_atendimento.clear()
        logger.info(f"🔒 Lock criado: {telefone} por {usuario}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar lock: {e}")


def remover_lock(telefone):
    """Remove o lock quando o atendimento é concluído ou pulado"""
    try:
        client = get_gsheet_client()
        sh = client.open_by_key(Config.SHEET_ID)
        ws = sh.worksheet("EM_ATENDIMENTO")
        
        # Buscar a linha do telefone
        try:
            cell = ws.find(str(telefone))
            if cell:
                ws.delete_rows(cell.row)
                load_em_atendimento.clear()
                logger.info(f"🔓 Lock removido: {telefone}")
        except gspread.exceptions.CellNotFound:
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

def limpar_telefone(v):
    try:
        return re.sub(r"\D", "", str(v))
    except (TypeError, AttributeError) as e:
        logger.warning(f"Erro ao limpar telefone '{v}': {e}")
        return ""

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

@st.cache_data(ttl=Config.CACHE_BASE_TTL)
@st.cache_data(ttl=Config.CACHE_VOLATILE_TTL)  # ✅ Mudou para 10 segundos (antes era 300)
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
def load_agendamentos_hoje():
    """Carrega APENAS os agendamentos para HOJE (filtrado pela 'Próxima data')"""
    try:
        client = get_gsheet_client()
        ws = client.open(Config.SHEET_AGENDAMENTOS).worksheet("AGENDAMENTOS_ATIVOS")
        df = pd.DataFrame(ws.get_all_records())
        
        if df.empty:
            logger.info("⚠️ Nenhum agendamento na base")
            return pd.DataFrame()
        
    
        
        # Detectar qual coluna usar
        if "Próxima data" in df.columns:
            col_data = "Próxima data"
        elif "Data de chamada" in df.columns:
            col_data = "Data de chamada"
        else:
            logger.error("❌ Nenhuma coluna de data encontrada")
            return pd.DataFrame()
        
        # Filtrar por hoje (aceita formato BR ou ISO)
        mask = (
            df[col_data].astype(str).str.contains(hoje_br, na=False) |
            df[col_data].astype(str).str.contains(hoje_iso, na=False)
        )
        
        df_hoje = df[mask].copy()
        
        if not df_hoje.empty:
            df_hoje["Telefone_limpo"] = df_hoje["Telefone"].apply(limpar_telefone)
        
        logger.info(f"✅ Agendamentos para hoje ({hoje_br}): {len(df_hoje)}")
        return df_hoje
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar agendamentos de hoje: {e}")
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

# =========================================================
# (5) 🎨 COMPONENTE CARD DE ATENDIMENTO
# =========================================================

def card_component(id_fix, row, usuario_atual):
    """Card de atendimento com formulário (evita reruns ao digitar)"""
    
    telefone = str(row.get("Telefone", ""))
    
    # Criar lock ao exibir card
    lock_key = f"lock_criado_{id_fix}"
    if lock_key not in st.session_state:
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

        # ✅ NOVO: Usar FORM para evitar reruns ao digitar
        with st.form(key=f"form_{id_fix}", clear_on_submit=False):
            vendedor = st.selectbox("Responsável", Config.VENDEDORES, key=f"vend_{id_fix}")
            motivo = st.text_input("Motivo do contato", key=f"mot_{id_fix}")
            resumo = st.text_area("Resumo da conversa", key=f"res_{id_fix}", height=80)
            proxima = st.date_input("Próxima data", key=f"dt_{id_fix}")

            col1, col2 = st.columns(2)
            
            # ✅ Botões dentro do form - só processa ao clicar
            concluir = col1.form_submit_button("✅ Registrar e concluir", use_container_width=True)
            pular = col2.form_submit_button("⏭ Pular cliente", use_container_width=True)
            
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

def registrar_agendamento(row, comentario, motivo, proxima_data, vendedor):
    logger.info(f"Iniciando registro para: {row.get('Cliente', 'N/A')} - Tel: {row.get('Telefone', 'N/A')}")
    
    with st.spinner("💾 Salvando no Google Sheets..."):
        try:
            client = get_gsheet_client()
            sh = client.open(Config.SHEET_AGENDAMENTOS)
            ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
            ws_hist = sh.worksheet("HISTORICO")

            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            
            # ✅ CORREÇÃO: Converter TODOS os valores para tipos nativos do Python
            cliente = str(row.get("Cliente", "—"))
            classificacao = str(row.get("Classificação", "—"))
            valor = safe_valor(row.get("Valor", "—"))
            telefone = str(row.get("Telefone", "—"))
            comentario_str = str(comentario) if comentario else ""
            motivo_str = str(motivo) if motivo else ""
            proxima_str = str(proxima_data) if proxima_data else ""
            vendedor_str = str(vendedor) if vendedor else ""

            # Registrar no histórico
            ws_hist.append_row([
                agora,
                cliente,
                classificacao,
                valor,
                telefone,
                comentario_str,
                motivo_str,
                proxima_str,
                vendedor_str
            ], value_input_option="USER_ENTERED")

            # Registrar agendamento se houver próxima data
            if proxima_data:
                ws_ag.append_row([
                    agora,
                    cliente,
                    classificacao,
                    valor,
                    telefone,
                    comentario_str,
                    motivo_str,
                    proxima_str,
                    vendedor_str
                ], value_input_option="USER_ENTERED")

            # Limpar caches
            load_agendamentos_ativos.clear()
            load_df_agendamentos.clear()
            load_historico.clear()

            st.success("✅ Agendamento registrado com sucesso!")
            logger.info(f"✅ Registro concluído: {cliente}")
            time.sleep(0.5)
            
        except Exception as e:
            st.error(f"❌ Erro ao salvar: {e}")
            logger.error(f"❌ ERRO ao registrar: {e}", exc_info=True)
            
            # ✅ ADICIONAR: Mostrar detalhes do erro para debug
            with st.expander("🔍 Detalhes do erro (para debug)", expanded=False):
                st.write("**Tipo de erro:**", type(e).__name__)
                st.write("**Mensagem:**", str(e))
                st.write("**Dados que tentamos salvar:**")
                st.json({
                    "Cliente": cliente,
                    "Classificação": classificacao,
                    "Valor": valor,
                    "Telefone": telefone,
                    "Comentário": comentario_str[:50] + "..." if len(comentario_str) > 50 else comentario_str,
                    "Motivo": motivo_str,
                    "Próxima data": proxima_str,
                    "Vendedor": vendedor_str
                })


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
            # Limpar todos os caches voláteis
            load_em_atendimento.clear()
            load_agendamentos_hoje.clear()
            load_agendamentos_ativos.clear()
            st.success("✅ Dados atualizados!")
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
    
       # ✅ Normalizar telefones para comparação correta
    # Converter telefones_agendados para formato limpo
    telefones_agendados_limpo = {limpar_telefone(t) for t in telefones_agendados}
    
    # Filtrar usando telefone limpo E telefone normal
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
        # ✅ NOVO: Auto-refresh suave a cada 30 segundos (só recarrega dados, não a página)
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        
        tempo_decorrido = (datetime.now() - st.session_state.last_refresh).total_seconds()
        
        if tempo_decorrido > 30:  # 30 segundos
            # Limpar apenas caches voláteis (não perde o que está digitando)
            load_em_atendimento.clear()
            load_agendamentos_hoje.clear()
            st.session_state.last_refresh = datetime.now()
            logger.info("🔄 Auto-refresh de dados executado (30s)")

        st.header("🎯 Tarefas do dia")

        # =========================================================
        # 🔍 Carregar agendamentos e fazer JOIN com base principal
        # =========================================================
        # ✅ NOVO: Usar função otimizada que já filtra por hoje
        df_ag_hoje = load_agendamentos_hoje()
        
        # Carregar base completa para join
        df_base_completa = load_sheet(Config.SHEET_ID, Config.SHEET_NAME)
        
        # ✅ FAZER JOIN COM BASE PRINCIPAL PARA PEGAR DADOS COMPLETOS
        if not df_ag_hoje.empty and not df_base_completa.empty:
            # Limpar telefones para join
            df_ag_hoje["Telefone_limpo"] = df_ag_hoje["Telefone"].apply(limpar_telefone)
            
            # Fazer merge com base principal
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

        # Contar apenas concluídos que estão no total_dia
        telefones_do_dia = set()
        if not df_dia.empty:
            telefones_do_dia.update(df_dia["Telefone"].astype(str).tolist())
        if not df_ag_hoje.empty:
            telefones_do_dia.update(df_ag_hoje["Telefone"].astype(str).tolist())
        
        concluidos_hoje = len(st.session_state["concluidos"].intersection(telefones_do_dia))

        # Garantir progresso entre 0.0 e 1.0
        if total_dia > 0:
            progresso = min(concluidos_hoje / total_dia, 1.0)
        else:
            progresso = 0.0

        # ---------------------------------------------------------
        # Barra de progresso
        # ---------------------------------------------------------
        st.markdown("### Progresso do Dia")
        st.progress(progresso)
        st.write(f"**{concluidos_hoje} de {total_dia} contatos concluídos** ({progresso*100:.1f}%)")

        # Balões aparecem apenas uma vez
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

        st.markdown("---")

        # =========================================================
        # 🟦 MODO CHECK-IN — EXIBE CARDS
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

            # Reset de índices para evitar problemas
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
                return

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
                        # ✅ Rerun direto (mais rápido que usar flag)
                        st.rerun()
                    elif ac == "pular":
                        remover_card(row1["Telefone"], False)
                        st.rerun()

                # CARD 2
                if i + 1 < len(df_checkin):
                    row2 = df_checkin.iloc[i + 1]
                    with col2:
                        ac2, mot2, res2, prox2, vend2 = card_component(row2["ID"], row2, usuario_atual)

                        if ac2 == "concluir":
                            registrar_agendamento(row2, res2, mot2, prox2.strftime("%d/%m/%Y") if prox2 else "", vend2)
                            remover_card(row2["Telefone"], True)
                            st.rerun()
                        elif ac2 == "pular":
                            remover_card(row2["Telefone"], False)
                            st.rerun()
        # =========================================================
        # 🟧 MODO AGENDAMENTOS ATIVOS — MESMO FORMATO DO CHECK-IN
        # =========================================================
        else:

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
                return

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
            
            # Reset índices
            df_ag_normalizado = df_ag_normalizado.reset_index(drop=True)
            
            # ✅ Filtrar concluídos/pulados usando telefone limpo
            ocultos = st.session_state["concluidos"].union(st.session_state["pulados"])

            # Filtrar por Telefone normal E por Telefone_limpo
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
                return

            # CSV para download
            csv_ag = df_ag_normalizado.drop(columns=["ID", "Telefone_limpo"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 Baixar agendamentos (CSV)", csv_ag, "agendamentos_hoje.csv")

            st.markdown("---")

            # ✅ CARDS (2 por linha) - FORMATO IDÊNTICO AO CHECK-IN
            for i in range(0, len(df_ag_normalizado), 2):
                col1, col2 = st.columns(2)

                # CARD 1
                row1 = df_ag_normalizado.iloc[i]
                with col1:
                    # Badge
                    st.markdown("🔔 **AGENDAMENTO ATIVO**")
                    
                    ac, mot, res, prox, vend = card_component(row1["ID"], row1, usuario_atual)

                    if ac == "concluir":
                        registrar_agendamento(row1, res, mot, prox.strftime("%d/%m/%Y") if prox else "", vend)
                        remover_card(row1["Telefone"], True)
                        st.rerun()
                    elif ac == "pular":
                        remover_card(row1["Telefone"], False)
                        st.rerun()

                # CARD 2
                if i + 1 < len(df_ag_normalizado):
                    row2 = df_ag_normalizado.iloc[i + 1]
                    with col2:
                        # Badge
                        st.markdown("🔔 **AGENDAMENTO ATIVO**")
                        
                        ac2, mot2, res2, prox2, vend2 = card_component(row2["ID"], row2, usuario_atual)

                        if ac2 == "concluir":
                            registrar_agendamento(row2, res2, mot2, prox2.strftime("%d/%m/%Y") if prox2 else "", vend2)
                            remover_card(row2["Telefone"], True)
                            st.rerun()
                        elif ac2 == "pular":
                            remover_card(row2["Telefone"], False)
                            st.rerun()



def render_aba2(aba, base, total_tarefas):
    with aba:
        st.header("📊 Indicadores & Performance")
        
        # Obter dados do histórico
        df_historico = load_historico()
        
        # =========================================================
        # 📊 BLOCO 1: RESUMO EXECUTIVO
        # =========================================================
        st.markdown("### 📈 Resumo Executivo")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Métricas principais
        total_clientes = len(base)
        atendidos_hoje = len(st.session_state.get("concluidos", set()))
        ticket_medio = base["Valor_num"].mean() if not base.empty else 0
        valor_total = base["Valor_num"].sum() if not base.empty else 0
        
        with col1:
            st.metric(
                "👥 Total de Clientes",
                f"{total_clientes:,}".replace(",", "."),
                help="Total de clientes na base"
            )
        
        with col2:
            st.metric(
                "✅ Atendidos Hoje",
                atendidos_hoje,
                delta=f"{(atendidos_hoje/max(total_tarefas, 1)*100):.1f}% da meta" if total_tarefas > 0 else "0%",
                help="Clientes contatados hoje"
            )
        
        with col3:
            st.metric(
                "💰 Ticket Médio",
                f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                help="Valor médio de compra"
            )
        
        with col4:
            st.metric(
                "💵 Valor Total Base",
                f"R$ {valor_total:,.0f}".replace(",", "X").replace(".", ",").replace("X", "."),
                help="Soma total de vendas da base"
            )
        
        st.markdown("---")
        
        # =========================================================
        # 🏷️ BLOCO 2: DISTRIBUIÇÃO POR CLASSIFICAÇÃO
        # =========================================================
        st.markdown("### 🏷️ Distribuição por Classificação")
        
        col_a, col_b = st.columns([2, 1])
        
        with col_a:
            if not base.empty:
                # Contar por classificação
                dist_class = base["Classificação"].value_counts().reset_index()
                dist_class.columns = ["Classificação", "Quantidade"]
                
                # Adicionar percentual
                dist_class["Percentual"] = (dist_class["Quantidade"] / dist_class["Quantidade"].sum() * 100).round(1)
                
                st.dataframe(
                    dist_class,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Nenhum dado disponível")
        
        with col_b:
            if not base.empty:
                # Métricas por classificação
                st.markdown("**📌 Destaques:**")
                
                novos = len(base[base["Classificação"] == "Novo"])
                risco = len(base[base["Classificação"] == "Em risco"])
                campeoes = len(base[base["Classificação"] == "Campeão"])
                
                st.metric("🆕 Novos", novos)
                st.metric("⚠️ Em Risco", risco, delta=f"{(risco/total_clientes*100):.1f}%", delta_color="inverse")
                st.metric("🏆 Campeões", campeoes, delta=f"{(campeoes/total_clientes*100):.1f}%")
        
        st.markdown("---")
        
        # =========================================================
        # 👥 BLOCO 3: PERFORMANCE POR VENDEDOR
        # =========================================================
        st.markdown("### 👥 Performance por Vendedor (Hoje)")
        
        if not df_historico.empty:
            # Filtrar registros de hoje
            hoje = datetime.now().strftime("%d/%m/%Y")
            df_hoje = df_historico[df_historico["Data_de_contato"].astype(str).str.contains(hoje, na=False)]
            
            if not df_hoje.empty:
                # Agrupar por vendedor
                perf_vendedor = df_hoje.groupby("Vendedor").agg({
                    "Cliente": "count",
                    "Classificação": lambda x: x.mode()[0] if len(x) > 0 else "—"
                }).reset_index()
                
                perf_vendedor.columns = ["Vendedor", "Atendimentos", "Classificação Mais Comum"]
                perf_vendedor = perf_vendedor.sort_values("Atendimentos", ascending=False)
                
                col_c, col_d = st.columns([3, 2])
                
                with col_c:
                    st.dataframe(
                        perf_vendedor,
                        use_container_width=True,
                        hide_index=True
                    )
                
                with col_d:
                    st.markdown("**🏆 Ranking do Dia:**")
                    for idx, row in perf_vendedor.iterrows():
                        emoji = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else "📍"
                        st.write(f"{emoji} **{row['Vendedor']}**: {row['Atendimentos']} atendimentos")
            else:
                st.info("📭 Nenhum atendimento registrado hoje")
        else:
            st.info("📭 Nenhum histórico disponível")
        
        st.markdown("---")
        
               # =========================================================
        # 📅 BLOCO 4: PRÓXIMOS AGENDAMENTOS
        # =========================================================
        st.markdown("### 📅 Agendamentos dos Próximos 7 Dias")
        
        # Carregar todos agendamentos
        df_agendamentos_todos = load_df_agendamentos()
        
        if not df_agendamentos_todos.empty:
            # ✅ VERIFICAR qual coluna de data existe
            colunas_data_possiveis = [
                "Próxima data", 
                "Data de chamada", 
                "Proxima data",
                "próxima data",
                "Data",
                "Data de contato"
            ]
            
            coluna_data_encontrada = None
            for col in colunas_data_possiveis:
                if col in df_agendamentos_todos.columns:
                    coluna_data_encontrada = col
                    logger.info(f"✅ Coluna de data encontrada: '{col}'")
                    break
            
            if coluna_data_encontrada:
                try:
                    # Converter próxima data
                    df_agendamentos_todos["Próxima_data_dt"] = pd.to_datetime(
                        df_agendamentos_todos[coluna_data_encontrada], 
                        format="%d/%m/%Y", 
                        errors="coerce"
                    )
                    
                    # Filtrar próximos 7 dias
                    hoje = datetime.now()
                    proximos_7 = hoje + pd.Timedelta(days=7)
                    
                    df_proximos = df_agendamentos_todos[
                        (df_agendamentos_todos["Próxima_data_dt"] >= hoje) &
                        (df_agendamentos_todos["Próxima_data_dt"] <= proximos_7)
                    ].copy()
                    
                    if not df_proximos.empty:
                        # Ordenar por data
                        df_proximos = df_proximos.sort_values("Próxima_data_dt")
                        
                        # Selecionar colunas existentes
                        colunas_exibir = []
                        mapeamento = {
                            "Cliente": "Cliente",
                            "Nome": "Cliente",
                            coluna_data_encontrada: "Data",
                            "Follow up": "Motivo",
                            "Motivo": "Motivo",
                            "Vendedor": "Responsável",
                            "Responsavel": "Responsável"
                        }
                        
                        # Construir lista de colunas disponíveis
                        for col_original, col_nova in mapeamento.items():
                            if col_original in df_proximos.columns and col_nova not in colunas_exibir:
                                colunas_exibir.append((col_original, col_nova))
                        
                        # Criar DataFrame para exibição
                        df_exibir = df_proximos[[c[0] for c in colunas_exibir]].copy()
                        df_exibir.columns = [c[1] for c in colunas_exibir]
                        
                        st.dataframe(
                            df_exibir,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Resumo por dia
                        st.markdown("**📊 Resumo por Dia:**")
                        resumo_dias = df_proximos["Próxima_data_dt"].dt.date.value_counts().sort_index()
                        
                        if len(resumo_dias) > 0:
                            col_e, col_f, col_g = st.columns(3)
                            
                            dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
                            
                            for i, (data, qtd) in enumerate(list(resumo_dias.items())[:7]):
                                dia_semana = dias_semana[data.weekday()]
                                col = [col_e, col_f, col_g][i % 3]
                                
                                with col:
                                    st.metric(
                                        f"{dia_semana} {data.strftime('%d/%m')}",
                                        f"{qtd} agendamento(s)"
                                    )
                        else:
                            st.info("📭 Nenhum agendamento nos próximos 7 dias")
                    else:
                        st.info("📭 Nenhum agendamento nos próximos 7 dias")
                
                except Exception as e:
                    logger.error(f"❌ Erro ao processar datas de agendamento: {e}")
                    st.error(f"⚠️ Erro ao processar datas. Verifique o formato na planilha.")
                    
                    # Debug: Mostrar estrutura
                    with st.expander("🔍 Debug - Ver estrutura dos dados"):
                        st.write("**Colunas disponíveis:**")
                        st.write(df_agendamentos_todos.columns.tolist())
                        st.write("**Primeiros registros:**")
                        st.dataframe(df_agendamentos_todos.head(3))
            else:
                st.warning("⚠️ Nenhuma coluna de data encontrada na planilha de agendamentos")
                
                # Debug: Mostrar colunas disponíveis
                with st.expander("🔍 Colunas disponíveis na planilha"):
                    st.write(df_agendamentos_todos.columns.tolist())
        else:
            st.info("📭 Nenhum agendamento cadastrado")
        
        st.markdown("---")

        
        # =========================================================
        # 📉 BLOCO 5: CLIENTES EM RISCO
        # =========================================================
        st.markdown("### ⚠️ Clientes em Risco de Churn")
        
        if not base.empty:
            # Filtrar em risco ou sem compra há muito tempo
            clientes_risco = base[
                (base["Classificação"] == "Em risco") |
                (base["Dias_num"].fillna(0) > 90)
            ].copy()
            
            clientes_risco = clientes_risco.sort_values("Dias_num", ascending=False).head(10)
            
            if not clientes_risco.empty:
                st.warning(f"⚠️ **{len(clientes_risco)} clientes** precisam de atenção urgente!")
                
                df_risco_exibir = clientes_risco[["Cliente", "Classificação", "Dias_num", "Valor", "Telefone"]].copy()
                df_risco_exibir.columns = ["Cliente", "Status", "Dias sem comprar", "Último valor", "Telefone"]
                
                st.dataframe(
                    df_risco_exibir,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success("✅ Nenhum cliente em risco crítico!")
        
        st.markdown("---")
        
        # =========================================================
        # 💰 BLOCO 6: ANÁLISE FINANCEIRA
        # =========================================================
        st.markdown("### 💰 Análise Financeira por Classificação")
        
        if not base.empty:
            analise_financeira = base.groupby("Classificação").agg({
                "Valor_num": ["sum", "mean", "count"]
            }).reset_index()
            
            analise_financeira.columns = ["Classificação", "Valor Total", "Ticket Médio", "Quantidade"]
            analise_financeira = analise_financeira.sort_values("Valor Total", ascending=False)
            
            # Formatar valores
            analise_financeira["Valor Total"] = analise_financeira["Valor Total"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            analise_financeira["Ticket Médio"] = analise_financeira["Ticket Médio"].apply(
                lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            
            st.dataframe(
                analise_financeira,
                use_container_width=True,
                hide_index=True
            )
            
            # Download CSV
            csv_financeiro = analise_financeira.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 Baixar Análise Financeira (CSV)",
                csv_financeiro,
                "analise_financeira.csv",
                use_container_width=True
            )


def render_aba3(aba):
    with aba:
        st.header("🔎 Pesquisa no Histórico")

        df = load_historico()
        termo = st.text_input("Buscar no histórico")

        if termo:
            filt = df[df.apply(lambda x: termo.lower() in str(x).lower(), axis=1)]
            if not filt.empty:
                st.dataframe(filt, use_container_width=True)
            else:
                st.warning("Nenhum resultado encontrado")
        else:
            st.info("Digite um termo para pesquisar no histórico de atendimentos")

# =========================================================
# (10) 🚀 MAIN FLOW
# =========================================================

def main():
    st.title("📅 CRM Sportech – Tarefas do Dia")

    init_session_state()
    
    # ✅ NOVO: Obter usuário ANTES de tudo
    usuario_atual = obter_usuario_atual()
    
    if not usuario_atual or usuario_atual.strip() == "":
        st.warning("⚠️ **Por favor, identifique-se na barra lateral antes de continuar**")
        st.info("👈 Digite seu nome no campo 'Seu nome' na sidebar")
        st.stop()

    # ✅ Carregar dados (nomes corretos das variáveis)
    base = load_sheet(Config.SHEET_ID, Config.SHEET_NAME)
    telefones_agendados = load_agendamentos_ativos()
    
    # ✅ NOVO: Garantir que todos telefones sejam strings para comparação correta
    telefones_agendados = {str(t).strip() for t in telefones_agendados}
    
    logger.info(f"✅ Telefones com agendamento ativo: {len(telefones_agendados)}")

    filtros, metas = render_sidebar()

    # ✅ Agora as variáveis correspondem aos parâmetros esperados
    df_dia = build_daily_tasks_df(base, telefones_agendados, filtros, metas, usuario_atual)

    aba1, aba2, aba3 = st.tabs([
        "📅 Tarefas do dia",
        "📊 Indicadores",
        "🔎 Histórico"
    ])

    render_aba1(aba1, df_dia, metas)
    render_aba2(aba2, base, len(df_dia))
    render_aba3(aba3)


if __name__ == "__main__":
    main()
