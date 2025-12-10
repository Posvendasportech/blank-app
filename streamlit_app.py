import streamlit as st 
import pandas as pd
from urllib.parse import quote
import streamlit.components.v1 as components
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
# Carregar planilha TOTAL com CACHE (SUPER RÁPIDO AGORA)
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
# Estado — agora MUITO mais leve
# =========================================================
if "concluidos" not in st.session_state:
    st.session_state["concluidos"] = set()

if "selecionado" not in st.session_state:
    st.session_state["selecionado"] = None  # telefone selecionado para formulário


def selecionar_card(tel):
    st.session_state["selecionado"] = tel


def remover_card(tel):
    st.session_state["concluidos"].add(str(tel))
    st.session_state["selecionado"] = None  # limpa formulário sem rerun


# =========================================================
# Interface principal
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
# Função de salvar no Google Sheets
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


# ------------------------------
# Renderização dos cards + formulário compacto
# ------------------------------
def card_atendimento(idx, row):
    st.markdown(
        """
        <style>
        .card-container {
            background-color: #ffffff;
            padding: 20px;
            border-radius: 20px;
            margin-bottom: 30px;
            display: grid;
            grid-template-columns: 260px 1fr 120px;
            grid-template-rows: auto auto;
            grid-gap: 20px;
            border: 1px solid #e6e6e6;
            box-shadow: 0px 4px 15px rgba(0,0,0,0.10);
        }
        
        /* BLOCO ESQUERDO — DADOS DO CLIENTE */
        .dados {
            grid-row: 1 / span 2;
            background-color: #0546b8;
            color: white;
            padding: 22px;
            border-radius: 20px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            font-size: 18px;
            line-height: 1.6;
        }

        /* MOTIVO DO CONTATO */
        .motivo {
            background-color: #0546b8;
            color: white;
            padding: 15px;
            border-radius: 20px;
            font-size: 17px;
        }

        /* RESUMO DA CONVERSA */
        .resumo {
            background-color: #0546b8;
            color: white;
            padding: 15px;
            border-radius: 20px;
            font-size: 17px;
        }

        /* BOTÃO DE CONCLUIR */
        .bt-concluir {
            background-color: #0546b8;
            color: white;
            padding: 15px 10px;
            border-radius: 20px;
            text-align: center;
            font-weight: bold;
            cursor: pointer;
            margin-top: 10px;
        }
        .bt-concluir:hover {
            filter: brightness(0.85);
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

    # -------------------------------
    # CAMPOS INTERATIVOS EM STREAMLIT
    # -------------------------------
    motivo = st.text_input("Motivo do próximo contato", key=f"motivo_{idx}")
    resumo = st.text_area("Resumo da conversa", key=f"resumo_{idx}", height=80)
    proxima = st.date_input("Próxima data", key=f"prox_{idx}")

    # -------------------------------
    # RENDER DO CARD PRINCIPAL
    # -------------------------------
    st.markdown(
        f"""
        <div class="card-container">
            
            <!-- BLOCO ESQUERDO -->
            <div class="dados">
                <b>{row['Cliente']}</b><br>
                📱 {row['Telefone']}<br>
                🏷 {row['Classificação']}<br>
                💰 {safe_valor(row['Valor'])}<br>
                ⏳ {row['Dias_num']} dias desde a compra
            </div>

            <!-- MOTIVO DO CONTATO -->
            <div class="motivo">
                <b>Motivo do próximo contato:</b><br>
                {motivo if motivo else "—"}
            </div>

            <!-- RESUMO DA CONVERSA -->
            <div class="resumo">
                <b>Resumo da conversa:</b><br>
                {resumo if resumo else "—"}
            </div>

            <!-- BOTÃO CONCLUIR -->
            <div class="bt-concluir" onclick="window.parent.document.getElementById('btn_{idx}').click();">
                ✔ Concluir
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    # Botão invisível do Streamlit
    if st.button("✔", key=f"btn_{idx}", help="Botão oculto"):
        return motivo, resumo, proxima

    return None, None, None
