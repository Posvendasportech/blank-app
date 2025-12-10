import streamlit as st 
import pandas as pd
from urllib.parse import quote
import streamlit.components.v1 as components
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# ------------------------------
# 🔑 Conexão com Google API
# ------------------------------
def get_gsheet_client():
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(credentials)
    return client


# ------------------------------
# Configuração da página
# ------------------------------
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: #FFFFFF;
}
</style>
""", unsafe_allow_html=True)


# ------------------------------
# Carregar planilha SEM CACHE
# ------------------------------
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)

SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"

df = load_sheet(SHEET_ID, SHEET_NAME)


# ------------------------------
# Mapear colunas (A–I)
# ------------------------------
col_data = df.iloc[:, 0]
col_nome = df.iloc[:, 1]
col_email = df.iloc[:, 2]
col_valor = df.iloc[:, 3]
col_tel = df.iloc[:, 4]
col_compras = df.iloc[:, 5]
col_class = df.iloc[:, 6]
col_dias = df.iloc[:, 8]  # Dias desde a compra


# ------------------------------
# Conversão segura de dias
# ------------------------------
def converte_dias(v):
    try:
        v = str(v).replace(",", ".")
        return int(round(float(v)))
    except:
        return None


# ------------------------------
# Conversão segura de valor
# ------------------------------
def safe_valor(v):
    try:
        if pd.isna(v):
            return "—"
        v = str(v).replace("R$", "").replace(" ", "").replace(",", ".")
        return f"R$ {float(v):.2f}"
    except:
        return "—"


# ------------------------------
# Criar base
# ------------------------------
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


# ------------------------------
# Estado local — concluídos
# ------------------------------
if "concluidos" not in st.session_state:
    st.session_state["concluidos"] = set()

def remover_card(tel):
    st.session_state["concluidos"].add(str(tel))
    st.rerun()


# ------------------------------
# Título e filtro
# ------------------------------
st.title("📅 CRM Sportech – Tarefas do Dia")

class_filter = st.radio(
    "Filtrar por classificação:",
    ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
    horizontal=True
)



# ------------------------------
# Configurações & Resumo
# ------------------------------
st.markdown("## ⚙️ Configurações & Resumo do Dia")

colA, colB = st.columns([2, 2])

with colA:
    c1, c2, c3 = st.columns(3)
    meta_novos = c1.number_input("Novos", value=10, min_value=0)
    meta_prom = c2.number_input("Promissores", value=20, min_value=0)
    meta_leais = c3.number_input("Leais/Campeões", value=10, min_value=0)


# ------------------------------
# Seleção das tarefas
# ------------------------------
novos = base[(base["Classificação"] == "Novo") & (base["Dias_num"] >= 15)]
novos = novos.sort_values("Dias_num", ascending=True).head(meta_novos)

prom = base[base["Classificação"] == "Promissor"]
prom = prom.sort_values("Dias_num", ascending=False).head(meta_prom)

leal_camp = base[base["Classificação"].isin(["Leal", "Campeão"])]
leal_camp = leal_camp.sort_values("Dias_num", ascending=False).head(meta_leais)

risco = base[base["Classificação"] == "Em risco"].sort_values("Dias_num")

frames = []
if not novos.empty: novos["Grupo"] = "Novo"; frames.append(novos)
if not prom.empty: prom["Grupo"] = "Promissor"; frames.append(prom)
if not leal_camp.empty: leal_camp["Grupo"] = "Leal/Campeão"; frames.append(leal_camp)
if not risco.empty: risco["Grupo"] = "Em risco"; frames.append(risco)

df_dia = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

df_dia = df_dia[~df_dia["Telefone"].isin(st.session_state["concluidos"])]
if class_filter != "Todos":
    df_dia = df_dia[df_dia["Classificação"] == class_filter]


# ------------------------------
# Contadores
# ------------------------------
count_novos = len(df_dia[df_dia["Classificação"] == "Novo"])
count_prom = len(df_dia[df_dia["Classificação"] == "Promissor"])
count_leais = len(df_dia[df_dia["Classificação"].isin(["Leal", "Campeão"])])
count_risco = len(df_dia[df_dia["Classificação"] == "Em risco"])

with colB:
    st.markdown("### 📊 Resumo")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Novos", count_novos)
    r2.metric("Promissores", count_prom)
    r3.metric("Leais/Campeões", count_leais)
    r4.metric("Em risco", count_risco)


# ------------------------------
# 📌 Registrar agendamento + histórico
# ------------------------------
def registrar_agendamento(row, comentario, motivo, proxima_data):

    client = get_gsheet_client()

    # AQUI ESTAVA O ERRO! Nome corrigido:
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
# CSS
# ------------------------------
css = """
<style>
.grid-container {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    grid-gap: 28px;
    width: 100%;
}
.card {
    background-color: #FFFFFF;
    width: 100%;
    min-height: 260px;
    padding: 20px;
    border-radius: 18px;
    border: 1px solid #e1e1e1;
    display: flex; flex-direction: column; justify-content: space-between;
    box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
    transition: all 0.25s ease;
}
.card:hover {
    transform: translateY(-4px);
    box-shadow: 0px 8px 20px rgba(0,0,0,0.25);
}
.card.fade-out { opacity: 0; }
.card h3 { margin: 0; font-size: 20px; color: #111; font-weight: 700; }
.card p { margin: 3px 0; font-size: 14px; color: #333; }
</style>
"""


# ------------------------------
# Renderização dos cards + formulário
# ------------------------------
html_cards = css + "<div class='grid-container'>"

for idx, row in df_dia.iterrows():

    valor = safe_valor(row["Valor"])
    dias = row["Dias_num"]

    st.markdown(f"### 🧩 Registro do contato — {row['Cliente']} ({row['Telefone']})")

    comentario = st.text_input("📝 Como foi a conversa?", key=f"com_{idx}")
    motivo = st.text_input("📌 Motivo do contato", key=f"mot_{idx}")
    proxima_data = st.date_input("📅 Próxima data de contato", key=f"prox_{idx}")

    if st.button(f"Salvar e concluir ({row['Telefone']})", key=f"save_{idx}"):

        registrar_agendamento(row, comentario, motivo, str(proxima_data))
        st.success("Contato registrado com sucesso!")
        remover_card(row["Telefone"])

    html_cards += f"""
    <div id='card_{idx}' class='card'>
        <div>
            <h3>👤 {row['Cliente']}</h3>
            <p>📱 {row['Telefone']}</p>
            <p>🏷 {row['Classificação']}</p>
            <p>💰 {valor}</p>
            <p>⏳ {dias} dias desde compra</p>
        </div>
    </div>
    """

html_cards += "</div>"

components.html(html_cards, height=1500, scrolling=True)
import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

st.title("🔍 Teste de Conexão — Google Sheets API")

# ------------------------------
# 1) Criar cliente Google Sheets
# ------------------------------
st.write("### 1️⃣ Carregando credenciais...")
try:
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    st.success("Credenciais carregadas com sucesso!")
except Exception as e:
    st.error("❌ ERRO ao carregar credenciais:")
    st.error(str(e))
    st.stop()

# ------------------------------
# 2) Autorizando gspread
# ------------------------------
st.write("### 2️⃣ Autorizando gspread...")
try:
    client = gspread.authorize(creds)
    st.success("gspread autorizado!")
except Exception as e:
    st.error("❌ ERRO ao autorizar gspread:")
    st.error(str(e))
    st.stop()

# ------------------------------
# 3) Listar planilhas acessíveis pelo serviço
# ------------------------------
st.write("### 3️⃣ Listando todas as planilhas acessíveis pelo serviço...")
try:
    arquivos = client.list_spreadsheet_files()
    st.write("##### 📄 Planilhas encontradas:")
    st.json(arquivos)

    nomes = [a["name"] for a in arquivos]
    st.write("##### 🔍 Nomes detectados:", nomes)
except Exception as e:
    st.error("❌ ERRO ao listar planilhas:")
    st.error(str(e))
    st.stop()

# ------------------------------
# 4) Tentar abrir planilha "Agendamentos"
# ------------------------------
st.write("### 4️⃣ Tentando abrir a planilha **Agendamentos**...")
try:
    sh = client.open("Agendamentos")
    st.success("✅ A planilha 'Agendamentos' foi aberta com sucesso!")
    st.write("ID:", sh.id)
except Exception as e:
    st.error("❌ ERRO ao abrir a planilha 'Agendamentos':")
    st.error(str(e))
    st.stop()

# ------------------------------
# 5) Ler abas internas
# ------------------------------
st.write("### 5️⃣ Tentando ler abas internas da planilha...")

try:
    ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
    st.success("Aba AGENDAMENTOS_ATIVOS encontrada!")
except Exception as e:
    st.error("❌ ERRO: não encontrou aba AGENDAMENTOS_ATIVOS:")
    st.error(str(e))

try:
    ws_hist = sh.worksheet("HISTORICO")
    st.success("Aba HISTORICO encontrada!")
except Exception as e:
    st.error("❌ ERRO: não encontrou aba HISTORICO:")
    st.error(str(e))
