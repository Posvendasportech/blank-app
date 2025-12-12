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
    
    # Listas de opções
    VENDEDORES = ["João", "Maria", "Patrick", "Outro"]
    CLASSIFICACOES = ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"]
    
    # Cache e Performance
    CACHE_TTL = 60  # segundos
    
    # Valores padrão
    DIAS_MINIMO_NOVOS = 15  # Novos só aparecem após X dias

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
        v = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return f"R$ {float(v):.2f}"
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

@st.cache_data(ttl=Config.CACHE_TTL)
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

@st.cache_data(ttl=Config.CACHE_TTL)
def load_agendamentos_ativos():
    try:
        client = get_gsheet_client()
        ws = client.open(Config.SHEET_AGENDAMENTOS).worksheet("AGENDAMENTOS_ATIVOS")
        telefones = set(ws.col_values(5)[1:])
        logger.info(f"✅ Agendamentos ativos carregados: {len(telefones)}")
        return telefones
    except Exception as e:
        logger.error(f"Erro ao carregar agendamentos ativos: {e}", exc_info=True)
        return set()

@st.cache_data(ttl=Config.CACHE_TTL)
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

@st.cache_data(ttl=Config.CACHE_TTL)
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

def card_component(id_fix, row):
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)

        dias_txt = f"{row['Dias_num']} dias desde compra" if pd.notna(row["Dias_num"]) else "Sem informação"

        st.markdown(f"""
            <div class="card-header">
                <b>{row['Cliente']}</b><br>
                📱 {row['Telefone']}<br>
                🏷 {row['Classificação']}<br>
                💰 {safe_valor(row['Valor'])}<br>
                ⏳ {dias_txt}
            </div>
        """, unsafe_allow_html=True)

        vendedor = st.selectbox("Responsável", Config.VENDEDORES, key=f"vend_{id_fix}")
        motivo = st.text_input("Motivo do contato", key=f"mot_{id_fix}")
        resumo = st.text_area("Resumo da conversa", key=f"res_{id_fix}", height=80)
        proxima = st.date_input("Próxima data", key=f"dt_{id_fix}")

        col1, col2 = st.columns(2)
        acao = None

        if col1.button("✅ Registrar e concluir", key=f"ok_{id_fix}"):
            # Validar TODOS os campos obrigatórios
            if not motivo.strip():
                st.error("⚠️ O campo 'Motivo do contato' é obrigatório")
                acao = None
            elif not resumo.strip():
                st.error("⚠️ O campo 'Resumo da conversa' é obrigatório")
                acao = None
            elif not proxima:
                st.error("⚠️ Selecione uma data para o próximo contato")
                acao = None
            else:
                acao = "concluir"

        if col2.button("⏭ Pular cliente", key=f"skip_{id_fix}"):
            acao = "pular"

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
            
            cliente = row.get("Cliente") or row.get("Nome", "—")
            classificacao = row.get("Classificação", "—")
            valor = safe_valor(row.get("Valor", "—"))
            telefone = row.get("Telefone", "—")

            # Registrar no histórico
            ws_hist.append_row([
                agora, cliente, classificacao, valor, telefone,
                comentario, motivo, proxima_data, vendedor
            ], value_input_option="USER_ENTERED")

            # Registrar agendamento se houver próxima data
            if proxima_data:
                ws_ag.append_row([
                    agora, cliente, classificacao, valor, telefone,
                    comentario, motivo, proxima_data, vendedor
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
            st.stop()

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
            col_d1.write(f"TTL Cache: {Config.CACHE_TTL}s")
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

def build_daily_tasks_df(base, telefones_agendados, filtros, metas):
    base_ck = base[~base["Telefone"].isin(telefones_agendados)].copy()

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
    df_dia["ID"] = df_dia["Telefone_limpo"]

    # Filtrar concluídos/pulados
    ocultos = st.session_state["concluidos"].union(st.session_state["pulados"])
    df_dia = df_dia[~df_dia["Telefone"].isin(ocultos)]

    # Aplicar filtros
    df_dia = df_dia[df_dia["Dias_num"].fillna(0).between(filtros["min_dias"], filtros["max_dias"])]
    df_dia = df_dia[df_dia["Valor_num"].fillna(0).between(filtros["min_valor"], filtros["max_valor"])]

    # Filtro de telefone (normalizado)
    if filtros["telefone"]:
        clean = limpar_telefone(filtros["telefone"])
        df_dia = df_dia[df_dia["Telefone_limpo"].str.contains(clean, na=False)]

    logger.info(f"Tarefas do dia geradas: {len(df_dia)} clientes")
    return df_dia

# =========================================================
# (9) 🖥️ UI — ABAS PRINCIPAIS
# =========================================================

def render_aba1(aba, df_dia, metas):
    with aba:
        st.header("🎯 Tarefas do dia")

        # =========================================================
        # 🔍 Resumo geral: Check-in + Agendamentos ativos
        # =========================================================
        df_ag = load_df_agendamentos()

        # ✅ CORREÇÃO 1: Verificar qual coluna tem a data
        hoje = datetime.now().strftime("%d/%m/%Y")
        
        if not df_ag.empty:
            # Tentar múltiplas colunas de data
            colunas_data = ["Data de chamada", "Data de contato", "Próxima data", "Data"]
            df_ag_hoje = pd.DataFrame()
            
            for col in colunas_data:
                if col in df_ag.columns:
                    df_ag_hoje = df_ag[df_ag[col].astype(str).str.startswith(hoje)]
                    if not df_ag_hoje.empty:
                        logger.info(f"Agendamentos encontrados na coluna '{col}': {len(df_ag_hoje)}")
                        break
            
            if df_ag_hoje.empty:
                logger.warning(f"Nenhum agendamento encontrado para {hoje}")
        else:
            df_ag_hoje = pd.DataFrame()
            logger.warning("DataFrame de agendamentos está vazio")

        qtd_checkin = len(df_dia)
        qtd_agendamentos = len(df_ag_hoje)
        total_dia = qtd_checkin + qtd_agendamentos

        # ✅ CORREÇÃO 2: Contar apenas concluídos que estão no total_dia
        telefones_do_dia = set()
        if not df_dia.empty:
            telefones_do_dia.update(df_dia["Telefone"].astype(str).tolist())
        if not df_ag_hoje.empty:
            telefones_do_dia.update(df_ag_hoje["Telefone"].astype(str).tolist())
        
        # Contar apenas concluídos que fazem parte das tarefas do dia
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

        # ✅ CORREÇÃO 3: Balões aparecem apenas uma vez
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
            # Mostrar balões apenas uma vez quando atingir 100%
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
                    ac, mot, res, prox, vend = card_component(row1["ID"], row1)

                    if ac == "concluir":
                        registrar_agendamento(row1, res, mot, prox.strftime("%d/%m/%Y") if prox else "", vend)
                        remover_card(row1["Telefone"], True)
                        st.session_state.rerun_necessario = True
                    elif ac == "pular":
                        remover_card(row1["Telefone"], False)
                        st.session_state.rerun_necessario = True

                # CARD 2
                if i + 1 < len(df_checkin):
                    row2 = df_checkin.iloc[i + 1]
                    with col2:
                        ac2, mot2, res2, prox2, vend2 = card_component(row2["ID"], row2)

                        if ac2 == "concluir":
                            registrar_agendamento(row2, res2, mot2, prox2.strftime("%d/%m/%Y") if prox2 else "", vend2)
                            remover_card(row2["Telefone"], True)
                            st.session_state.rerun_necessario = True
                        elif ac2 == "pular":
                            remover_card(row2["Telefone"], False)
                            st.session_state.rerun_necessario = True


        # =========================================================
        # 🟧 MODO AGENDAMENTOS ATIVOS — EM CARD
        # =========================================================
        else:

            st.subheader("📂 Agendamentos Ativos (Hoje)")

            # ✅ CORREÇÃO 4: Debug para ver quais agendamentos existem
            if not df_ag.empty:
                with st.expander("🔍 Debug: Ver todos os agendamentos", expanded=False):
                    st.write(f"**Total de agendamentos na base:** {len(df_ag)}")
                    st.write(f"**Colunas disponíveis:** {', '.join(df_ag.columns.tolist())}")
                    st.write(f"**Buscando agendamentos para:** {hoje}")
                    
                    # Mostrar primeiras linhas
                    st.dataframe(df_ag.head(10))

            if df_ag_hoje.empty:
                st.info("📭 Nenhum agendamento encontrado para hoje.")
                st.write(f"💡 **Data de hoje:** {hoje}")
                st.write("💡 **Possíveis causas:**")
                st.write("- Os agendamentos foram criados com data diferente")
                st.write("- A coluna de data na planilha tem formato diferente")
                st.write("- Configure novos agendamentos na aba 'Check-in'")
                
                # Mostrar últimos agendamentos criados
                if not df_ag.empty:
                    st.write("---")
                    st.write("📋 **Últimos 5 agendamentos criados:**")
                    st.dataframe(df_ag.tail(5))
                
                return

            # Reset de índices
            df_ag_hoje = df_ag_hoje.reset_index(drop=True)

            # Renderizar cada agendamento como card
            for i in range(len(df_ag_hoje)):
                row = df_ag_hoje.iloc[i]
                id_card = str(row.get("Telefone", f"ag_{i}"))

                ac, motivo, resumo, proxima, vendedor = agendamento_card(id_card, row)

                if ac == "concluir":
                    registrar_agendamento(
                        row=row,
                        comentario=resumo,
                        motivo=motivo,
                        proxima_data=proxima.strftime("%d/%m/%Y") if proxima else "",
                        vendedor=vendedor
                    )
                    remover_card(row.get("Telefone", ""), True)
                    st.session_state.rerun_necessario = True

                elif ac == "pular":
                    remover_card(row.get("Telefone", ""), False)
                    st.session_state.rerun_necessario = True


def render_aba2(aba, base, total):
    with aba:
        st.header("📊 Indicadores")

        col1, col2 = st.columns(2)
        col1.metric("Concluídos na sessão", len(st.session_state["concluidos"]))
        col2.metric("Pulados na sessão", len(st.session_state["pulados"]))

        st.markdown("---")
        st.subheader("📥 Exportar Relatório")
        
        if st.button("Gerar Relatório do Dia"):
            relatorio = gerar_relatorio_diario()
            st.download_button(
                label="📄 Baixar Relatório (CSV)",
                data=relatorio,
                file_name=f"relatorio_crm_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

        st.markdown("---")
        st.subheader("Distribuição por Classificação")
        
        if not base.empty and "Classificação" in base.columns:
            dfcount = base["Classificação"].value_counts()
            st.bar_chart(dfcount)
        else:
            st.info("Sem dados para exibir")

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

    df = load_sheet(Config.SHEET_ID, Config.SHEET_NAME)

    telefones_ag = load_agendamentos_ativos()

    filtros, metas = render_sidebar()

    df_dia = build_daily_tasks_df(df, telefones_ag, filtros, metas)

    aba1, aba2, aba3 = st.tabs([
        "📅 Tarefas do dia",
        "📊 Indicadores",
        "🔎 Histórico"
    ])

    render_aba1(aba1, df_dia, metas)
    render_aba2(aba2, df, len(df_dia))
    render_aba3(aba3)

    # ✅ CONTROLE DE RERUN OTIMIZADO
    if st.session_state.rerun_necessario:
        st.session_state.rerun_necessario = False
        logger.info("Rerun executado")
        st.rerun()

if __name__ == "__main__":
    main()
