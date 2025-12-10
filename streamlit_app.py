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
# Cards
# =========================================================

st.markdown("""
<style>
/* ... seu CSS de fundo preto existente ... */

.card {
    background-color: #1a1a1a; /* Cinza escuro */
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 20px; /* Espaço entre os cards verticais */
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    height: 100%; /* Garante que os cards na mesma linha tenham a mesma altura */
    display: flex;
    flex-direction: column;
}

.card-header {
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid #333333;
    color: #FFFFFF;
}

.card-header b {
    font-size: 1.1em;
    color: #4CAF50; /* Cor de destaque para o nome */
}

.card-title {
    font-weight: bold;
    margin-top: 10px;
    margin-bottom: 5px;
    color: #999999;
}

.input-box {
    width: 100%;
    padding: 8px;
    margin-bottom: 10px;
    border: 1px solid #555555;
    border-radius: 4px;
    background-color: #2a2a2a; /* Fundo do input */
    color: #FFFFFF;
    box-sizing: border-box;
}

textarea.input-box {
    resize: vertical;
}

.submit-btn {
    background-color: #4CAF50; /* Verde */
    color: white;
    padding: 10px 15px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    text-align: center;
    margin-top: auto; /* Empurra o botão para baixo */
}

.submit-btn:hover {
    background-color: #45a049;
}
</style>
""", unsafe_allow_html=True)



# =========================================================
# FUNÇÃO DO CARD (HTML + JS) - VERSÃO CORRIGIDA E COMPLETA
# =========================================================
def card_html(idx, row):

    # O HTML deve incluir todos os campos de input e o JavaScript de comunicação
    html = f"""
    <div class="card">

        <div class="card-header">
            <b>{row['Cliente']}</b><br>
            📱 {row['Telefone']}<br>
            🏷 {row['Classificação']}<br>
            💰 {safe_valor(row['Valor'])}<br>
            ⏳ {row['Dias_num']} dias desde compra
        </div>

        <div class="card-title">Motivo do contato</div>
        <input class="input-box" id="motivo_{idx}" placeholder="Ex.: Check-in">

        <div class="card-title">Resumo da conversa</div>
        <textarea class="input-box" id="resumo_{idx}" rows="3" placeholder="O que foi conversado e quais os próximos passos..."></textarea>

        <div class="card-title">Próxima data (Opcional)</div>
        <input class="input-box" type="date" id="data_{idx}">

        <div class="submit-btn" onclick="sendForm{idx}()">Registrar e concluir</div>

        <script>
            function sendForm{idx}() {{
                // 1. Captura os valores dos inputs
                const motivo = document.getElementById("motivo_{idx}").value;
                const resumo = document.getElementById("resumo_{idx}").value;
                const data = document.getElementById("data_{idx}").value;

                // 2. Envia os dados capturados via postMessage para o Streamlit (iframe pai)
                window.parent.postMessage(
                    {{
                        type: "salvar",
                        idx: "{idx}",
                        motivo: motivo,
                        resumo: resumo,
                        data: data
                    }},
                    "*"
                );
            }}
        </script>

    </div>
    """

    st.markdown(html, unsafe_allow_html=True)

    # =========================================================
# RECEBE EVENTO DO JS (VERIFIQUE SE ESTÁ ASSIM)
# =========================================================
if "event" not in st.session_state:
    st.session_state["event"] = None

event = st.session_state["event"]

if event and event["type"] == "salvar":
    idx = int(event["idx"])
    row = df_dia.loc[idx] # Use .loc[idx] pois idx é o índice do DataFrame original
    
    registrar_agendamento(row, event["resumo"], event["motivo"], event["data"]) # ATENÇÃO: Verifique a ordem dos parâmetros aqui, o seu original era (row, comentario, motivo, proxima_data)
    
    # 🌟 Melhoria: Feedback e remoção do card
    st.session_state["concluidos"].add(row["Telefone"])
    st.success(f"Tarefa registrada para **{row['Cliente']}** e concluída.")
    st.session_state["event"] = None # Limpa o evento para evitar reexecução
    st.rerun() # Reexecuta o script para que o card suma

# =========================================================
# RENDERIZAÇÃO FINAL – GRID (2 Colunas)
# =========================================================
st.title("📌 Atendimentos do dia")

# Obtém a lista de índices (idx) do DataFrame para iterar
indices = df_dia.index.tolist()

# Itera sobre os índices em passos de 2
for i in range(0, len(indices), 2):
    
    # Cria duas colunas para cada par de cards
    col1, col2 = st.columns(2)
    
    # Renderiza o primeiro card (na coluna 1)
    idx1 = indices[i]
    row1 = df_dia.loc[idx1]
    with col1:
        # A função card_html recebe o índice original e a linha
        card_html(idx1, row1)
        
    # Renderiza o segundo card, se existir (na coluna 2)
    if i + 1 < len(indices):
        idx2 = indices[i+1]
        row2 = df_dia.loc[idx2]
        with col2:
            card_html(idx2, row2)
            
# Se df_dia estiver vazio
if df_dia.empty:
    st.info("🎉 Não há tarefas pendentes para a classificação selecionada hoje.")
