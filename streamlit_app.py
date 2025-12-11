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
# Carregar planilha TOTAL (CACHE)
# =========================================================
@st.cache_data(ttl=60)
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)

SHEET_ID = st.secrets["nome"]
SHEET_NAME = "Total"
df = load_sheet(SHEET_ID, SHEET_NAME)


# =========================================================
# Carregar agendamentos ativos
# =========================================================
@st.cache_data(ttl=60)
def load_agendamentos():
    client = get_gsheet_client()
    sh = client.open("Agendamentos")
    ws = sh.worksheet("AGENDAMENTOS_ATIVOS")
    data = ws.get_all_records()
    return pd.DataFrame(data)

agendamentos = load_agendamentos()

hoje = datetime.now().strftime("%Y-%m-%d")
agendamentos["Data de chamada"] = pd.to_datetime(agendamentos["Data de chamada"], errors="coerce")
agendamentos_do_dia = agendamentos[agendamentos["Data de chamada"].dt.strftime("%Y-%m-%d") == hoje]


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
base["Valor_num"] = base["Valor"].apply(valor_num)


# =========================================================
# Estado do app
# =========================================================
if "concluidos" not in st.session_state:
    st.session_state["concluidos"] = set()
if "pulados" not in st.session_state:
    st.session_state["pulados"] = set()
if "historico_stack" not in st.session_state:
    st.session_state["historico_stack"] = []


def remover_card(telefone, concluido=True):
    tel = str(telefone)
    if concluido:
        st.session_state["concluidos"].add(tel)
    else:
        st.session_state["pulados"].add(tel)
    st.session_state["historico_stack"].append(tel)


# =========================================================
# Remover agendamento da planilha
# =========================================================
def remover_agendamento_da_planilha(telefone):
    client = get_gsheet_client()
    sh = client.open("Agendamentos")
    ws = sh.worksheet("AGENDAMENTOS_ATIVOS")

    registros = ws.get_all_values()

    for i, row in enumerate(registros):
        if row[4] == telefone:
            ws.delete_rows(i + 1)
            break


# =========================================================
# Título
# =========================================================
st.title("📅 CRM Sportech – Tarefas do Dia")


# =========================================================
# Abas principais
# =========================================================
aba1, aba2, aba3 = st.tabs([
    "📅 Tarefas do dia",
    "📊 Indicadores",
    "🔎 Pesquisa de histórico"
])


# =========================================================
# 🟦 ABA 1 — TAREFAS DO DIA
# =========================================================
with aba1:

    st.header("📅 Tarefas do dia")

    class_filter = st.radio(
        "Filtrar por classificação:",
        ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
        horizontal=True
    )

    contato_tipo = st.radio(
        "Tipo de atendimento:",
        ["Primeiro contato", "Agendamentos do dia"],
        horizontal=True
    )


# =========================================================
# Sidebar
# =========================================================
with st.sidebar:
    st.header("⚙️ Filtros avançados")

    min_dias = st.number_input("Mínimo de dias desde a última compra", min_value=0, value=0)
    max_dias = st.number_input("Máximo de dias desde a última compra", min_value=0, value=365)

    min_valor = st.number_input("Valor mínimo (R$)", min_value=0.0, value=0.0, step=10.0)
    max_valor = st.number_input("Valor máximo (R$)", min_value=0.0, value=1000.0, step=10.0)

    telefone_busca = st.text_input("Buscar por telefone (qualquer parte)")

    st.markdown("---")
    st.header("🔁 Controles da sessão")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("↩ Voltar último cliente"):
            if st.session_state["historico_stack"]:
                ultimo = st.session_state["historico_stack"].pop()
                st.session_state["concluidos"].discard(ultimo)
                st.session_state["pulados"].discard(ultimo)
    with col_s2:
        if st.button("🧹 Resetar sessão"):
            st.session_state["concluidos"] = set()
            st.session_state["pulados"] = set()
            st.session_state["historico_stack"] = []


# =========================================================
# 🎯 Metas
# =========================================================
st.markdown("## 🎯 Configurações & Metas do Dia")

colA, colB = st.columns([2, 2])
with colA:
    c1, c2, c3, c4 = st.columns(4)
    meta_novos = c1.number_input("Novos", value=10, min_value=0)
    meta_prom = c2.number_input("Promissores", value=20, min_value=0)
    meta_leais = c3.number_input("Leais/Campeões", value=10, min_value=0)
    meta_risco = c4.number_input("Em risco", value=10, min_value=0)


# =========================================================
# Seleção das tarefas (primeiro contato)
# =========================================================
novos = base[(base["Classificação"] == "Novo") & (base["Dias_num"].fillna(0) >= 15)]
prom = base[base["Classificação"] == "Promissor"]
leal_camp = base[base["Classificação"].isin(["Leal", "Campeão"])]
risco = base[base["Classificação"] == "Em risco"]

novos = novos.sort_values("Dias_num").head(meta_novos)
prom = prom.sort_values("Dias_num", ascending=False).head(meta_prom)
leal_camp = leal_camp.sort_values("Dias_num", ascending=False).head(meta_leais)
risco = risco.sort_values("Dias_num").head(meta_risco)

frames = []
for df_temp, grupo in [(novos, "Novo"), (prom, "Promissor"), (leal_camp, "Leal/Campeão"), (risco, "Em risco")]:
    if not df_temp.empty:
        df_temp["Grupo"] = grupo
        frames.append(df_temp)

df_dia = pd.concat(frames) if frames else pd.DataFrame()

todos_ocultos = st.session_state["concluidos"].union(st.session_state["pulados"])
df_dia = df_dia[~df_dia["Telefone"].isin(todos_ocultos)]

if class_filter != "Todos":
    df_dia = df_dia[df_dia["Classificação"] == class_filter]

df_dia = df_dia[df_dia["Dias_num"].fillna(0).between(min_dias, max_dias)]
df_dia = df_dia[df_dia["Valor_num"].fillna(0).between(min_valor, max_valor)]

if telefone_busca:
    df_dia = df_dia[df_dia["Telefone"].str.contains(telefone_busca)]


# =========================================================
# Aplicar filtro entre primeiro contato e agendamentos
# =========================================================
if contato_tipo == "Primeiro contato":
    lista_final = df_dia.copy()

else:
    lista_final = agendamentos_do_dia.copy()

    lista_final.rename(columns={
        "Nome": "Cliente",
        "Telefone": "Telefone",
        "Classificação": "Classificação",
        "Pedido": "Valor",
        "Follow up": "Follow up"
    }, inplace=True)

lista_final["ID"] = lista_final["Telefone"].astype(str)


# =========================================================
# Registrar agendamento
# =========================================================
def registrar_agendamento(row, comentario, motivo, proxima_data, vendedor):

    client = get_gsheet_client()
    sh = client.open("Agendamentos")

    ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
    ws_hist = sh.worksheet("HISTORICO")

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

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


# =========================================================
# Card Component (versão estável)
# =========================================================
def card_component(id_fix, row):
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)

        dias_txt = f"{row.get('Dias_num', '—')} dias desde compra"

        st.markdown(
            f"""
            <div class="card-header">
                <b>{row['Cliente']}</b><br>
                📱 {row['Telefone']}<br>
                🏷 {row['Classificação']}<br>
                💰 {safe_valor(row.get('Valor'))}<br>
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

        motivo = st.text_input(
            "Motivo do contato",
            value=row.get("Follow up", ""),
            key=f"mot_{id_fix}"
        )

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
# Atendimentos do dia
# =========================================================
st.markdown("## 📌 Atendimentos do dia")

for i in range(0, len(lista_final), 2):

    col1, col2 = st.columns(2)

    # CARD 1
    row1 = lista_final.iloc[i]
    id1 = row1["ID"]

    with col1:
        acao, motivo, resumo, proxima, vendedor = card_component(id1, row1)

        if acao == "concluir" and motivo:
            registrar_agendamento(row1, resumo, motivo, str(proxima), vendedor)

            if contato_tipo == "Agendamentos do dia":
                remover_agendamento_da_planilha(row1["Telefone"])

            remover_card(row1["Telefone"], concluido=True)
            st.rerun()

        elif acao == "pular":
            remover_card(row1["Telefone"], concluido=False)
            st.rerun()

    # CARD 2
    if i + 1 < len(lista_final):
        row2 = lista_final.iloc[i + 1]
        id2 = row2["ID"]

        with col2:
            acao2, motivo2, resumo2, proxima2, vendedor2 = card_component(id2, row2)

            if acao2 == "concluir" and motivo2:
                registrar_agendamento(row2, resumo2, motivo2, str(proxima2), vendedor2)

                if contato_tipo == "Agendamentos do dia":
                    remover_agendamento_da_planilha(row2["Telefone"])

                remover_card(row2["Telefone"], concluido=True)
                st.rerun()

            elif acao2 == "pular":
                remover_card(row2["Telefone"], concluido=False)
                st.rerun()

# Caso não tenha tarefas
if lista_final.empty:
    st.info("🎉 Não há tarefas pendentes para hoje dentro dos filtros selecionados.")
