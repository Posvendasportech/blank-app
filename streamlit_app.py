# streamlit_app.py 
import streamlit as st
import pandas as pd
from urllib.parse import quote
from datetime import datetime

# ----------------------------------------
# ⚙️ Configuração da página
# ----------------------------------------
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

# TEMA ESCURO
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: #FFFFFF;
}
.card {
    background-color: #0A0A0A;
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #1F1F1F;
    margin-bottom: 12px;
}
.card h3 {
    margin-bottom: 6px;
}
.button-finish {
    background-color: #0066FF;
    color: white;
    padding: 8px 14px;
    border-radius: 8px;
    border: none;
}
</style>
""", unsafe_allow_html=True)

# ----------------------------------------
# 🔗 IDs / padrões das planilhas
# ----------------------------------------
SHEET2_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
DEFAULT_SHEET2_SHEETNAME = "Total"

# ----------------------------------------
# 📌 Função para carregar planilhas
# ----------------------------------------
@st.cache_data
def load_sheet(sheet_id, sheet_name):
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?"
        f"tqx=out:csv&sheet={quote(sheet_name)}"
    )
    return pd.read_csv(url)

# ----------------------------------------
# Estado para tarefas concluídas (por telefone)
# ----------------------------------------
if "concluidos" not in st.session_state:
    st.session_state["concluidos"] = set()

def concluir(tel):
    st.session_state["concluidos"].add(str(tel))
    st.rerun()

# ----------------------------------------
# Carregar planilha
# ----------------------------------------
df = load_sheet(SHEET2_ID, DEFAULT_SHEET2_SHEETNAME)

# Nome das colunas:
# A = data, B = nome, C = email, D = valor, E = telefone, F = compras, G = classificação

df["data_dt"] = pd.to_datetime(df.iloc[:, 0], errors="coerce")
df["Dias desde compra"] = (datetime.today() - df["data_dt"]).dt.days

df.columns = ["Data", "Cliente", "Email", "Valor", "Telefone", "Compras", "Classificação", "data_dt", "Dias desde compra"]

# ----------------------------------------
# Título + Filtro
# ----------------------------------------
st.title("📅 CRM Sportech – Tarefas do Dia")

class_filter = st.radio(
    "Filtrar por classificação:",
    ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
    horizontal=True
)

# ----------------------------------------
# Configurações do dia (metas)
# ----------------------------------------
st.subheader("⚙️ Configurações do dia")

col1, col2, col3 = st.columns(3)

meta_novos = col1.number_input("Meta de Check-in (Novos)", min_value=0, value=10)
meta_prom = col2.number_input("Promissores por dia", min_value=0, value=20)
meta_leais = col3.number_input("Leais + Campeões por dia", min_value=0, value=10)

# ----------------------------------------
# Seleção de tarefas do dia
# ----------------------------------------

# Novos (somente quem completou 15+ dias)
novos = df[(df["Classificação"] == "Novo") & (df["Dias desde compra"] >= 15)].sort_values("Dias desde compra", ascending=False)
novos = novos.head(meta_novos)

# Promissores
promissores = df[df["Classificação"] == "Promissor"].sort_values("Dias desde compra", ascending=False)
promissores = promissores.head(meta_prom)

# Leais + Campeões
grupo_fidelidade = df[df["Classificação"].isin(["Leal", "Campeão"])].sort_values("Dias desde compra", ascending=False)
grupo_fidelidade = grupo_fidelidade.head(meta_leais)

# Em risco (mostrar todos)
em_risco = df[df["Classificação"] == "Em risco"].sort_values("Dias desde compra")

# Dormentes → só aparecem no filtro específico
dormentes = df[df["Classificação"] == "Dormente"]

# Montar lista final DO DIA
dia_frames = []

if not novos.empty:
    temp = novos.copy()
    temp["Grupo"] = "Novo"
    dia_frames.append(temp)

if not promissores.empty:
    temp = promissores.copy()
    temp["Grupo"] = "Promissor"
    dia_frames.append(temp)

if not grupo_fidelidade.empty:
    temp = grupo_fidelidade.copy()
    temp["Grupo"] = "Leal/Campeão"
    dia_frames.append(temp)

if not em_risco.empty:
    temp = em_risco.copy()
    temp["Grupo"] = "Em risco"
    dia_frames.append(temp)

df_dia = pd.concat(dia_frames, ignore_index=True) if dia_frames else pd.DataFrame()

# remover concluídos
df_dia = df_dia[~df_dia["Telefone"].astype(str).isin(st.session_state["concluidos"])]

# ----------------------------------------
# Aplicar filtro por classificação
# ----------------------------------------
if class_filter != "Todos":
    df_dia = df_dia[df_dia["Classificação"] == class_filter]

# ----------------------------------------
# Cards das tarefas
# ----------------------------------------
st.subheader("📋 Tarefas do Dia")

if df_dia.empty:
    st.info("Nenhuma tarefa para hoje com os critérios selecionados.")
else:
    for idx, row in df_dia.iterrows():
        st.markdown(f"""
        <div class="card">
            <h3>👤 {row['Cliente']}</h3>
            <p>📱 {row['Telefone']}</p>
            <p>🏷️ Classificação: {row['Classificação']} | 🔵 Grupo do dia: {row['Grupo']}</p>
            <p>🛍️ Compras: {row['Compras']} | 💰 Valor gasto: R$ {row['Valor']}</p>
            <p>⏳ Dias desde compra: {row['Dias desde compra']}</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button(f"✔ Concluir {row['Cliente']}", key=f"concluir_{idx}"):
            concluir(row["Telefone"])
