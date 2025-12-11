import streamlit as st
import pandas as pd
from urllib.parse import quote
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# =========================================================
# ⚙️ 1. CONFIGURAÇÃO INICIAL E CSS
# =========================================================
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

st.markdown("""
<style>
/* ... SEU CSS INTACTO ... */
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: #FFFFFF;
}

/* Remove bordas padrão de expander */
.streamlit-expanderHeader {
    background-color: #111 !important;
}

/* Ajuste tabelas */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* Cards */
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

.card-title {
    margin-top: 8px;
    color: #cccccc;
    font-size: 14px;
    font-weight: 600;
}

.input-box {
    width: 100%;
    padding: 8px;
    border-radius: 8px;
    border: 1px solid #444;
    background-color: #1b1b1b;
    color: white;
    margin-top: 4px;
}

.submit-btn {
    margin-top: 12px;
    width: 100%;
    background-color: #0A40B0;
    color: blue;
    padding: 10px;
    border-radius: 8px;
    text-align: center;
    font-weight: bold;
    cursor: pointer;
}

.submit-btn:hover {
    filter: brightness(1.15);
}

.small-label {
    font-size: 12px;
    color: #bbbbbb;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 🔑 2. FUNÇÕES DE CONEXÃO E CONVERSÃO
# =========================================================
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
    except:
        return None

def safe_valor(v):
    try:
        if pd.isna(v):
            return "—"
        v = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return f"R$ {float(v):.2f}"
    except:
        return "—"

def valor_num(v):
    try:
        if pd.isna(v):
            return None
        v = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(v)
    except:
        return None

# Funções de Ação e Geração de Cards
def remover_card(telefone, concluido=True):
    tel = str(telefone)
    if concluido:
        st.session_state["concluidos"].add(tel)
    else:
        st.session_state["pulados"].add(tel)
    st.session_state["historico_stack"].append(tel)

def registrar_agendamento(row, comentario, motivo, proxima_data, vendedor):
    client = get_gsheet_client()
    sh = client.open("Agendamentos")
    ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
    ws_hist = sh.worksheet("HISTORICO")

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    # HISTORICO (A → I)
    ws_hist.append_row([
        agora,
        row["Cliente"],
        row["Classificação"],
        safe_valor(row["Valor"]),
        row["Telefone"],
        comentario,
        motivo,
        proxima_data,
        vendedor
    ], value_input_option="USER_ENTERED")

    # AGENDAMENTOS_ATIVOS (A → I)
    if proxima_data:
        ws_ag.append_row([
            agora,
            row["Cliente"],
            row["Classificação"],
            safe_valor(row["Valor"]),
            row["Telefone"],
            comentario,
            motivo,
            proxima_data,
            vendedor
        ], value_input_option="USER_ENTERED")


# =========================================================
# 🔥 3. FUNÇÃO DO COMPONENTE CARD (Centralizada)
# =========================================================
def card_component(id_fix, row):
    # Nota: Esta é a versão final do card_component que você enviou
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)

        dias_txt = f"{row['Dias_num']} dias desde compra" if pd.notna(row["Dias_num"]) else "Sem informação de dias"

        st.markdown(
            f"""
            <div class="card-header">
                <b>{row['Cliente']}</b><br>
                📱 {row['Telefone']}<br>
                🏷 {row['Classificação']}<br>
                💰 {safe_valor(row['Valor'])}<br>
                ⏳ {dias_txt}
            </div>
            """,
            unsafe_allow_html=True
        )

        vendedor = st.selectbox(
            "Responsável",
            ["João", "Maria", "Patrick", "Outro"],
            key=f"vend_{id_fix}"
        )

        motivo = st.text_input("Motivo do contato", key=f"mot_{id_fix}")
        resumo = st.text_area("Resumo da conversa", key=f"res_{id_fix}", height=80)
        proxima = st.date_input("Próxima data", key=f"dt_{id_fix}")

        colA, colB = st.columns(2)
        acao = None

        with colA:
            if st.button("✅ Registrar e concluir", key=f"ok_{id_fix}"):
                acao = "concluir"

        with colB:
            if st.button("⏭ Pular cliente", key=f"skip_{id_fix}"):
                acao = "pular"

        st.markdown("</div>", unsafe_allow_html=True)

    return acao, motivo, resumo, proxima, vendedor


# =========================================================
# 💾 4. CARREGAMENTO E PREPARAÇÃO DOS DADOS
# =========================================================
@st.cache_data(ttl=60)
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)

SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"
df = load_sheet(SHEET_ID, SHEET_NAME)

# Mapeamento de colunas (mantido por índice, como estava no original)
col_data = df.iloc[:, 0]
col_nome = df.iloc[:, 1]
col_email = df.iloc[:, 2]
col_valor = df.iloc[:, 3]
col_tel = df.iloc[:, 4]
col_compras = df.iloc[:, 5]
col_class = df.iloc[:, 6]
col_dias = df.iloc[:, 8]

# Base final
base = pd.DataFrame({
    "Data": pd.to_datetime(col_data, errors="coerce"),
    "Cliente": col_nome,
    "Email": col_email,
    "Valor": col_valor,
    "Telefone": col_tel.astype(str),
    "Compras": col_compras,
    "Classificação": col_class,
    "Dias_num": col_dias.apply(converte_dias)
})

base["Valor_num"] = base["Valor"].apply(valor_num)

# =========================================================
# 5. ESTADO DA SESSÃO
# =========================================================
if "concluidos" not in st.session_state:
    st.session_state["concluidos"] = set()

if "pulados" not in st.session_state:
    st.session_state["pulados"] = set()

if "historico_stack" not in st.session_state:
    st.session_state["historico_stack"] = []


# =========================================================
# 6. HEADER E SIDEBAR (DEFINIÇÃO DE VARIÁVEIS DE FILTRO)
# =========================================================
st.title("📅 CRM Sportech – Tarefas do Dia")

# Sidebar – Filtros avançados & busca (Definem min_dias, max_valor, etc.)
with st.sidebar:
    st.header("⚙️ Filtros avançados")

    min_dias = st.number_input("Mínimo de dias desde a última compra", min_value=0, value=0)
    max_dias = st.number_input("Máximo de dias desde a última compra", min_value=0, value=365)

    min_valor = st.number_input("Valor mínimo (R$)", min_value=0.0, value=0.0, step=10.0)
    max_valor = st.number_input("Valor máximo (R$)", min_value=0.0, value=1000.0, step=10.0)

    telefone_busca = st.text_input("Buscar por telefone (qualquer parte)")

    st.markdown("---")
    st.markdown("### 🔁 Controles da sessão")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("↩ Voltar último cliente"):
            if st.session_state["historico_stack"]:
                ultimo = st.session_state["historico_stack"].pop()
                st.session_state["concluidos"].discard(ultimo)
                st.session_state["pulados"].discard(ultimo)
            st.rerun() # Adicionado rerun para atualização
    with col_s2:
        if st.button("🧹 Resetar sessão"):
            st.session_state["concluidos"] = set()
            st.session_state["pulados"] = set()
            st.session_state["historico_stack"] = []
            st.rerun() # Adicionado rerun para atualização


# Configurações & metas do dia (Definem meta_novos, etc.)
st.markdown("## 🎯 Configurações & Metas do Dia")

colA, colB_resumo = st.columns([2, 2])
with colA:
    c1, c2, c3, c4 = st.columns(4)
    meta_novos = c1.number_input("Novos", value=10, min_value=0)
    meta_prom = c2.number_input("Promissores", value=20, min_value=0)
    meta_leais = c3.number_input("Leais/Campeões", value=10, min_value=0)
    meta_risco = c4.number_input("Em risco", value=10, min_value=0)


# =========================================================
# 7. FILTRAGEM E CÁLCULO DE TAREFAS (Definem df_dia, total_tarefas, etc.)
#    ESTE BLOCO É CRÍTICO E DEVE FICAR ANTES DAS ABAS!
# =========================================================

# Seleção das tarefas por meta (RFM)
novos = base[(base["Classificação"] == "Novo") & (base["Dias_num"].fillna(0) >= 15)].copy()
novos = novos.sort_values("Dias_num", ascending=True).head(meta_novos)

prom = base[base["Classificação"] == "Promissor"].copy()
prom = prom.sort_values("Dias_num", ascending=False).head(meta_prom)

leal_camp = base[base["Classificação"].isin(["Leal", "Campeão"])].copy()
leal_camp = leal_camp.sort_values("Dias_num", ascending=False).head(meta_leais)

risco = base[base["Classificação"] == "Em risco"].copy()
risco = risco.sort_values("Dias_num", ascending=True).head(meta_risco)

frames = []
if not novos.empty:
    novos["Grupo"] = "Novo"; frames.append(novos)
if not prom.empty:
    prom["Grupo"] = "Promissor"; frames.append(prom)
if not leal_camp.empty:
    leal_camp["Grupo"] = "Leal/Campeão"; frames.append(leal_camp)
if not risco.empty:
    risco["Grupo"] = "Em risco"; frames.append(risco)

df_dia = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# Cria ID único
df_dia["ID"] = df_dia["Telefone"].astype(str)

# Aplicar filtros da sessão e do sidebar
todos_ocultos = st.session_state["concluidos"].union(st.session_state["pulados"])
df_dia = df_dia[~df_dia["Telefone"].isin(todos_ocultos)]

df_dia = df_dia[
    df_dia["Dias_num"].fillna(0).between(min_dias, max_dias)
]

df_dia = df_dia[
    df_dia["Valor_num"].fillna(0).between(min_valor, max_valor)
]

if telefone_busca:
    df_dia = df_dia[df_dia["Telefone"].str.contains(telefone_busca)]


# Contadores & resumo (Variáveis prontas para as abas)
count_novos = len(df_dia[df_dia["Classificação"] == "Novo"])
count_prom = len(df_dia[df_dia["Classificação"] == "Promissor"])
count_leais = len(df_dia[df_dia["Classificação"].isin(["Leal", "Campeão"])])
count_risco = len(df_dia[df_dia["Classificação"] == "Em risco"])
total_tarefas = len(df_dia) # Variável total_tarefas definida!


# =========================================================
# 8. ABAS PRINCIPAIS DO SISTEMA
# =========================================================
aba1, aba2, aba3 = st.tabs([
    "📅 Tarefas do dia",
    "📊 Indicadores",
    "🔎 Pesquisa de histórico"
])

# Resumo ao lado das metas (usa total_tarefas e contadores)
with colB_resumo:
    st.markdown("### 📊 Resumo")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Novos", count_novos)
    c2.metric("Promissores", count_prom)
    c3.metric("Leais/Campeões", count_leais)
    c4.metric("Em risco", count_risco)


# =========================================================
# 🟦 ABA 1 — TAREFAS DO DIA (Conteúdo principal)
# =========================================================
with aba1:
    st.header("📅 Tarefas do dia")

    class_filter = st.radio(
        "Filtrar por classificação:",
        ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
        horizontal=True
    )
    
    # Aplica filtro de rádio (precisa ser feito aqui dentro para afetar a exibição)
    df_aba1 = df_dia.copy()
    if class_filter != "Todos":
        df_aba1 = df_aba1[df_aba1["Classificação"] == class_filter]


    st.markdown("---")

    # Notificação geral
    if total_tarefas == 0:
        st.success("🎉 Você está em dia! Nenhum atendimento pendente dentro dos filtros atuais.")
    elif total_tarefas < 10:
        st.info(f"🔔 Hoje você tem **{total_tarefas}** contatos para trabalhar.")


    st.markdown("## 📌 Atendimentos do dia")

    # Download CSV
    if not df_aba1.empty:
        csv = df_aba1.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Baixar lista do dia (CSV)",
            data=csv,
            file_name="tarefas_dia.csv",
            mime="text/csv"
        )
    
    # Loop de renderização dos Cards (com lógica de ação)
    for i in range(0, len(df_aba1), 2):
        col1, col2 = st.columns(2)

        # CARD 1
        row1 = df_aba1.iloc[i]
        id1 = row1["ID"]

        with col1:
            acao, motivo, resumo, proxima, vendedor = card_component(id1, row1)

            if acao == "concluir":
                if motivo.strip():
                    registrar_agendamento(row1, resumo, motivo, str(proxima), vendedor)
                    remover_card(row1["Telefone"], concluido=True)
                    st.rerun()
                else:
                    st.warning("⚠️ **Preencha o Motivo do contato** para registrar a conclusão.", icon="🚨")

            elif acao == "pular":
                remover_card(row1["Telefone"], concluido=False)
                st.rerun()

        # CARD 2 (se existir)
        if i + 1 < len(df_aba1):
            row2 = df_aba1.iloc[i + 1]
            id2 = row2["ID"]

            with col2:
                acao2, motivo2, resumo2, proxima2, vendedor2 = card_component(id2, row2)

                if acao2 == "concluir":
                    if motivo2.strip():
                        registrar_agendamento(row2, resumo2, motivo2, str(proxima2), vendedor2)
                        remover_card(row2["Telefone"], concluido=True)
                        st.rerun()
                    else:
                        st.warning("⚠️ **Preencha o Motivo do contato** para registrar a conclusão.", icon="🚨")

                elif acao2 == "pular":
                    remover_card(row2["Telefone"], concluido=False)
                    st.rerun()

    # Caso vazio (após filtros)
    if df_aba1.empty:
        st.info("🎉 Não há tarefas pendentes para hoje dentro dos filtros selecionados.")


# =========================================================
# 📊 ABA 2 — INDICADORES
# =========================================================
with aba2:
    st.header("📊 Indicadores de Performance")

    # 1. Indicadores de Meta
    st.subheader("Progresso da Sessão Atual")

    concluidos_hoje = base[base["Telefone"].isin(st.session_state["concluidos"])]

    col_ind1, col_ind2 = st.columns(2)
    col_ind1.metric(
        "Tarefas Concluídas (Sessão)",
        len(concluidos_hoje),
        delta=f"Total na sessão: {len(st.session_state['concluidos'])}"
    )
    col_ind2.metric(
        "Clientes Pulados (Sessão)",
        len(st.session_state["pulados"]),
        delta=f"Tarefas restantes: {total_tarefas}"
    )

    st.markdown("---")

    # 2. Distribuição da Base
    st.subheader("Distribuição da Base Total por Classificação")
    df_count = base["Classificação"].value_counts().reset_index()
    df_count.columns = ["Classificação", "Quantidade"]

    # Exibe em formato de gráfico
    st.bar_chart(df_count.set_index("Classificação"))


# =========================================================
# 🔎 ABA 3 — PESQUISA DE HISTÓRICO
# =========================================================
@st.cache_data(ttl=60)
def load_historico():
    try:
        client = get_gsheet_client()
        sh = client.open("Agendamentos")
        ws_hist = sh.worksheet("HISTORICO")
        data = ws_hist.get_all_records()
        df_hist = pd.DataFrame(data)
        # Ajusta nome da coluna (Importante para não quebrar a busca)
        df_hist.columns = [col.replace(' ', '_') for col in df_hist.columns] 
        return df_hist
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return pd.DataFrame()


with aba3:
    st.header("🔎 Pesquisa de Histórico de Contato")

    df_hist = load_historico()

    termo_busca = st.text_input("Buscar por Telefone ou Nome no Histórico")

    if not df_hist.empty and termo_busca:
        # Renomeia colunas para busca segura
        col_nome_hist = 'Nome'
        col_telefone_hist = 'Telefone'
        
        # Busca no histórico pelo termo no nome ou telefone
        df_filtrado = df_hist[
            df_hist[col_telefone_hist].astype(str).str.contains(termo_busca, case=False, na=False) |
            df_hist[col_nome_hist].astype(str).str.contains(termo_busca, case=False, na=False)
        ]

        if not df_filtrado.empty:
            st.subheader(f"Histórico para '{termo_busca}'")
            st.dataframe(
                df_filtrado.sort_values("Data_de_contato", ascending=False),
                use_container_width=True
            )
        else:
            st.info("Nenhum registro encontrado no histórico.")
    elif not df_hist.empty:
        st.info("Digite um Nome ou Telefone para pesquisar no histórico de contatos.")
