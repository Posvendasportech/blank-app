import streamlit as st 
import pandas as pd
from urllib.parse import quote
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# =========================================================
# 🔑 Conexão com Google API
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


# =========================================================
# Configuração visual
# =========================================================
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: #FFFFFF;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# Carregar planilha TOTAL (CACHE)
# =========================================================
@st.cache_data(ttl=60)
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)

SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"
df = load_sheet(SHEET_ID, SHEET_NAME)


# =========================================================
# Mapear colunas
# =========================================================
col_data = df.iloc[:, 0]
col_nome = df.iloc[:, 1]
col_email = df.iloc[:, 2]
col_valor = df.iloc[:, 3]
col_tel = df.iloc[:, 4]
col_compras = df.iloc[:, 5]
col_class = df.iloc[:, 6]
col_dias = df.iloc[:, 8]


# =========================================================
# Conversões
# =========================================================
def converte_dias(v):
    try:
        return int(round(float(str(v).replace(",", "."))))
    except:
        return None

def safe_valor(v):
    try:
        if pd.isna(v): return "—"
        v = str(v).replace("R$", "").replace(",", ".").strip()
        return f"R$ {float(v):.2f}"
    except:
        return "—"


# =========================================================
# Base final
# =========================================================
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


# =========================================================
# Estado do app
# =========================================================
if "concluidos" not in st.session_state:
    st.session_state["concluidos"] = set()


# =========================================================
# Título
# =========================================================
st.title("📅 CRM Sportech – Tarefas do Dia")

class_filter = st.radio(
    "Filtrar por classificação:",
    ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
    horizontal=True
)


# =========================================================
# Configurações
# =========================================================
st.markdown("## ⚙️ Configurações & Resumo do Dia")

colA, colB = st.columns([2, 2])
with colA:
    c1, c2, c3 = st.columns(3)
    meta_novos = c1.number_input("Novos", value=10, min_value=0)
    meta_prom = c2.number_input("Promissores", value=20, min_value=0)
    meta_leais = c3.number_input("Leais/Campeões", value=10, min_value=0)


# =========================================================
# Seleção das tarefas
# =========================================================
novos = base[(base["Classificação"] == "Novo") & (base["Dias_num"] >= 15)]
novos = novos.sort_values("Dias_num", ascending=True).head(meta_novos)

prom = base[base["Classificação"] == "Promissor"].sort_values("Dias_num", ascending=False).head(meta_prom)
leal_camp = base[base["Classificação"].isin(["Leal", "Campeão"])].sort_values("Dias_num", ascending=False).head(meta_leais)
risco = base[base["Classificação"] == "Em risco"].sort_values("Dias_num", ascending=True)

frames = []
if not novos.empty: novos["Grupo"] = "Novo"; frames.append(novos)
if not prom.empty: prom["Grupo"] = "Promissor"; frames.append(prom)
if not leal_camp.empty: leal_camp["Grupo"] = "Leal/Campeão"; frames.append(leal_camp)
if not risco.empty: risco["Grupo"] = "Em risco"; frames.append(risco)

df_dia = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
df_dia = df_dia[~df_dia["Telefone"].isin(st.session_state["concluidos"])]

if class_filter != "Todos":
    df_dia = df_dia[df_dia["Classificação"] == class_filter]


# =========================================================
# Contadores
# =========================================================
count_novos = len(df_dia[df_dia["Classificação"] == "Novo"])
count_prom = len(df_dia[df_dia["Classificação"] == "Promissor"])
count_leais = len(df_dia[df_dia["Classificação"].isin(["Leal", "Campeão"])])
count_risco = len(df_dia[df_dia["Classificação"] == "Em risco"])

with colB:
    st.markdown("### 📊 Resumo")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Novos", count_novos)
    c2.metric("Promissores", count_prom)
    c3.metric("Leais/Campeões", count_leais)
    c4.metric("Em risco", count_risco)


# =========================================================
# Função de gravação no Google Sheets
# =========================================================
def registrar_agendamento(row, comentario, motivo, proxima_data):

    client = get_gsheet_client()
    sh = client.open("Agendamentos")

    ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
    ws_hist = sh.worksheet("HISTORICO")

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    ws_hist.append_row([
        agora,
        row["Cliente"],
        row["Telefone"],
        row["Classificação"],
        safe_valor(row["Valor"]),
        comentario,
        motivo,
        proxima_data
    ], value_input_option="USER_ENTERED")

    if proxima_data:
        ws_ag.append_row([
            row["Cliente"],
            row["Telefone"],
            row["Classificação"],
            comentario,
            motivo,
            proxima_data
        ], value_input_option="USER_ENTERED")


# =========================================================
# CARD LADO A LADO (2 por linha)
# =========================================================
# =========================================================
# 🔥 CSS ESTILO GYMSHARK + GRID DE CARDS
# =========================================================
st.markdown("""
<style>

.card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(430px, 1fr));
    gap: 32px;
    margin-top: 25px;
}

.gym-card {
    background: #111315;
    border: 1px solid #222;
    padding: 24px;
    border-radius: 22px;
    box-shadow: 0px 4px 18px rgba(0,0,0,0.35);
}

.gym-header {
    background: #0B3BAA;
    padding: 18px;
    border-radius: 18px;
    color: white;
    font-size: 18px;
    line-height: 1.6;
    margin-bottom: 18px;
}

.gym-section-title {
    font-weight: bold;
    font-size: 15px;
    margin-bottom: 6px;
    color: #e6e6e6;
}

.gym-button {
    margin-top: 14px;
    width: 100%;
    padding: 12px;
    background: #0B3BAA;
    color: white;
    border-radius: 14px;
    text-align: center;
    font-weight: bold;
    cursor: pointer;
}

.gym-button:hover {
    filter: brightness(1.12);
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# 🎯 FUNÇÃO DO CARD DE ATENDIMENTO
# =========================================================
def card_atendimento(idx, row):

    with st.container():
        st.markdown('<div class="gym-card">', unsafe_allow_html=True)

        # --- Cabeçalho estilo Gymshark ---
        st.markdown(f"""
            <div class="gym-header">
                <b>{row['Cliente']}</b><br>
                📱 {row['Telefone']}<br>
                🏷 {row['Classificação']}<br>
                💰 {safe_valor(row['Valor'])}<br>
                ⏳ {row['Dias_num']} dias desde compra
            </div>
        """, unsafe_allow_html=True)

        # Campo Motivo
        st.markdown("<div class='gym-section-title'>Motivo do contato</div>", unsafe_allow_html=True)
        motivo = st.text_input("", key=f"motivo_{idx}")

        # Campo Resumo da conversa
        st.markdown("<div class='gym-section-title'>Resumo da conversa</div>", unsafe_allow_html=True)
        resumo = st.text_area("", key=f"resumo_{idx}", height=80)

        # Campo Próxima data
        st.markdown("<div class='gym-section-title'>Próxima data</div>", unsafe_allow_html=True)
        proxima = st.date_input("", key=f"prox_{idx}")

        # Botão estilo Gymshark
        if st.button(f"Registrar e concluir ({row['Telefone']})", key=f"save_{idx}"):
            return motivo, resumo, proxima

        st.markdown("</div>", unsafe_allow_html=True)

    return None, None, None


# =========================================================
# 🧩 RENDERIZAÇÃO FINAL — GRID COM VÁRIOS CARDS POR PÁGINA
# =========================================================
st.markdown("## 📌 Atendimentos do dia")

st.markdown('<div class="card-grid">', unsafe_allow_html=True)

for idx, row in df_dia.iterrows():

    motivo, resumo, proxima = card_atendimento(idx, row)

    if motivo:
        registrar_agendamento(row, motivo, resumo, str(proxima))
        remover_card(row["Telefone"])

st.markdown("</div>", unsafe_allow_html=True)
