import streamlit as st 
import pandas as pd
from urllib.parse import quote
import streamlit.components.v1 as components

# ------------------------------
# Configuração da página
# ------------------------------
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

# Tema escuro básico
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: #FFFFFF;
}
</style>
""", unsafe_allow_html=True)


# ------------------------------
# Função para carregar planilha
# ------------------------------
@st.cache_data
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)


SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"

df = load_sheet(SHEET_ID, SHEET_NAME)


# ------------------------------
# Mapear colunas (A–I)
# ------------------------------
col_data = df.iloc[:, 0]      # A - Data
col_nome = df.iloc[:, 1]      # B - Nome
col_email = df.iloc[:, 2]     # C - Email
col_valor = df.iloc[:, 3]     # D - Valor gasto total
col_tel = df.iloc[:, 4]       # E - Telefone
col_compras = df.iloc[:, 5]   # F - Nº compras
col_class = df.iloc[:, 6]     # G - Classificação
col_dias = df.iloc[:, 8]      # I - Dias desde a última compra


# ------------------------------
# Função para arredondar dias (corrige 95,28 → 95)
# ------------------------------
def arredonda_dias(v):
    try:
        v = float(str(v).replace(",", "."))
        return int(round(v))
    except:
        return "—"


# ------------------------------
# Função formatar valor com segurança
# ------------------------------
def safe_valor(v):
    try:
        if pd.isna(v):
            return "—"
        v = str(v).replace("R$", "").replace(" ", "")
        v = v.replace(",", ".")
        v = float(v)
        return f"R$ {v:.2f}"
    except:
        return "—"


# ------------------------------
# Criar base limpa
# ------------------------------
base = pd.DataFrame({
    "Data": pd.to_datetime(col_data, errors="coerce"),
    "Cliente": col_nome,
    "Email": col_email,
    "Valor": col_valor,
    "Telefone": col_tel.astype(str),
    "Compras": col_compras,
    "Classificação": col_class,
    "Dias desde compra": col_dias.apply(arredonda_dias)   # 🔥 agora arredonda!
})


# ------------------------------
# Estado de concluídos
# ------------------------------
if "concluidos" not in st.session_state:
    st.session_state["concluidos"] = set()

def concluir(tel):
    st.session_state["concluidos"].add(str(tel))
    st.rerun()


# ------------------------------
# Layout – Título + Filtro
# ------------------------------
st.title("📅 CRM Sportech – Tarefas do Dia")

class_filter = st.radio(
    "Filtrar por classificação:",
    ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
    horizontal=True
)


# ------------------------------
# Configurações do dia
# ------------------------------
st.subh
