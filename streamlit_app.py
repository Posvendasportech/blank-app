import streamlit as st
import pandas as pd
from urllib.parse import quote
from datetime import datetime

# ------------------------------
# Configuração da página
# ------------------------------
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

# Tema escuro
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: #FFFFFF;
}
.card {
    background-color: #0F0F0F;
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #1F1F1F;
    margin-bottom: 12px;
}
.card h3 {
    margin-bottom: 6px;
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
# Mapear colunas por índice (A–G)
# ------------------------------
col_data = df.iloc[:, 0]      # A - Data
col_nome = df.iloc[:, 1]      # B - Nome
col_email = df.iloc[:, 2]     # C - Email
col_valor = df.iloc[:, 3]     # D - Valor gasto total
col_tel = df.iloc[:, 4]       # E - Telefone
col_compras = df.iloc[:, 5]   # F - Nº compras
col_class = df.iloc[:, 6]     # G - Classificação
col_dias = df.iloc[:, 9]    # I - Dias desde a ultima compra


# Criar dataframe base sem renomear colunas originais
base = pd.DataFrame({
    "Data": pd.to_datetime(col_data, errors="coerce"),
    "Cliente": col_nome,
    "Email": col_email,
    "Valor": col_valor,
    "Telefone": col_tel.astype(str),
    "Compras": col_compras,
    "Classificação": col_class
    "Dias desde a ultima compra": col_dias
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
# Configurações do dia (metas)
# ------------------------------
st.subheader("⚙️ Configurações do dia")

c1, c2, c3 = st.columns(3)

meta_novos = c1.number_input("Meta de Check-in (Novos)", value=10, min_value=0)
meta_prom = c2.number_input("Promissores por dia", value=20, min_value=0)
meta_leais = c3.number_input("Leais + Campeões por dia", value=10, min_value=0)

# ------------------------------
# Seleção de tarefas do dia
# ------------------------------

# Novos com +15 dias
novos = base[(base["Classificação"] == "Novo") & (base["Dias desde compra"] >= 15)]
novos = novos.sort_values("Dias desde compra", ascending=False).head(meta_novos)

# Promissores
prom = base[base["Classificação"] == "Promissor"]
prom = prom.sort_values("Dias desde compra", ascending=False).head(meta_prom)

# Leais + Campeões
leal_camp = base[base["Classificação"].isin(["Leal", "Campeão"])]
leal_camp = leal_camp.sort_values("Dias desde compra", ascending=False).head(meta_leais)

# Em risco (todos)
risco = base[base["Classificação"] == "Em risco"].sort_values("Dias desde compra")

# Montar lista final do dia
frames = []

if not novos.empty:
    t = novos.copy()
    t["Grupo"] = "Novo"
    frames.append(t)

if not prom.empty:
    t = prom.copy()
    t["Grupo"] = "Promissor"
    frames.append(t)

if not leal_camp.empty:
    t = leal_camp.copy()
    t["Grupo"] = "Leal/Campeão"
    frames.append(t)

if not risco.empty:
    t = risco.copy()
    t["Grupo"] = "Em risco"
    frames.append(t)

df_dia = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# Remover concluídos
df_dia = df_dia[~df_dia["Telefone"].isin(st.session_state["concluidos"])]

# Aplicar filtro de classificação
if class_filter != "Todos":
    df_dia = df_dia[df_dia["Classificação"] == class_filter]

import streamlit.components.v1 as components

import streamlit.components.v1 as components

# ===================================================================
# FUNÇÃO PARA FORMATAR VALOR
# ===================================================================
def format_valor(v):
    try:
        if pd.isna(v):
            return "—"
        v = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return f"R$ {float(v):.2f}"
    except:
        return "—"

# ===================================================================
# LER DIAS DESDE A COMPRA DA COLUNA I (ÍNDICE 8)
# ===================================================================
 "Dias desde a ultima compra": col_dias = df.iloc[:, 9]

st.subheader("📋 Tarefas do Dia")

if class_filter == "Dormente":
    df_dia = base[base["Classificação"] == "Dormente"]

if df_dia.empty:
    st.info("Nenhuma tarefa encontrada para hoje.")
    st.stop()

# ===================================================================
# CSS — BLOCO FECHADO CORRETAMENTE
# ===================================================================
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
    height: 230px;
    padding: 16px;
    border-radius: 14px;
    border: 1px solid #dddddd;

    display: flex;
    flex-direction: column;
    justify-content: space-between;

    box-shadow: 0px 2px 8px rgba(0,0,0,0.15);

    opacity: 1;
    transition: opacity 0.5s ease-out;
}

.card.fade-out {
    opacity: 0;
}

.card h3 { margin: 0; font-size: 19px; color: #000 }
.card p { margin: 4px 0; font-size: 13px; color: #222 }

.button-finish {
    background-color: #0066FF;
    color: white;
    padding: 8px 10px;
    border-radius: 8px;
    width: 100%;
    font-size: 14px;
    cursor: pointer;
    border: none;
}

.button-finish:hover {
    background-color: #004FCC;
}

</style>
"""

# ===================================================================
# GERAR HTML COMPLETO
# ===================================================================
html_cards = css + "<div class='grid-container'>"

for idx, row in df_dia.iterrows():

    valor = format_valor(row["Valor"])
    dias = row["Dias desde compra"] if pd.notna(row["Dias desde compra"]) else "—"

    html_cards += f"""
    <div id='card_{idx}' class='card'>
        <div>
            <h3>👤 {row['Cliente']}</h3>
            <p>📱 {row['Telefone']}</p>
            <p>🏷 {row['Classificação']}</p>
            <p>💰 {valor}</p>
            <p>⏳ {dias} dias desde compra</p>
        </div>

        <button class='button-finish' onclick="
            document.getElementById('card_{idx}').classList.add('fade-out');
            setTimeout(function(){{
                window.parent.document.getElementById('btn_{idx}').click();
            }}, 450);
        ">
            ✔ Concluir
        </button>
    </div>
    """

html_cards += "</div>"

# ===================================================================
# RENDERIZAR HTML PURO
# ===================================================================
components.html(html_cards, height=1600, scrolling=True)

# ===================================================================
# BOTÕES STREAMLIT OCULTOS
# ===================================================================
for idx, row in df_dia.iterrows():
    if st.button("✔", key=f"btn_{idx}", help="Concluir tarefa"):
        concluir(row["Telefone"])
