import streamlit as st
import pandas as pd
from urllib.parse import quote
import streamlit.components.v1 as components

# ----------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ----------------------------------------
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

# ----------------------------------------
# TEMA E ESTILOS
# ----------------------------------------
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: #FFFFFF;
}

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
.card p { margin: 4px 0; font-size: 13px; color: #333 }

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
""", unsafe_allow_html=True)

# ----------------------------------------
# FUNÇÃO PARA CARREGAR PLANILHA
# ----------------------------------------
@st.cache_data
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)

SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"

df = load_sheet(SHEET_ID, SHEET_NAME)

# ----------------------------------------
# MAPEAR COLUNAS
# ----------------------------------------
col_data = df.iloc[:, 0]       # Data
col_nome = df.iloc[:, 1]       # Nome
col_email = df.iloc[:, 2]      # Email
col_valor = df.iloc[:, 3]      # Valor
col_tel = df.iloc[:, 4]        # Telefone
col_compras = df.iloc[:, 5]    # Nº compras
col_class = df.iloc[:, 6]      # Classificação
col_dias = df.iloc[:, 8]       # Coluna I (dias desde compra)

# ----------------------------------------
# FUNÇÃO PARA FORMATAR VALORES COM SEGURANÇA
# ----------------------------------------
def safe_valor(v):
    try:
        if pd.isna(v):
            return "—"

        v = str(v).strip()

        v = v.replace("R$", "").replace(" ", "")
        v = v.replace(",", ".")

        v = float(v)

        return f"R$ {v:.2f}"
    except:
        return "—"

# ----------------------------------------
# CRIAR BASE PRINCIPAL
# ----------------------------------------
base = pd.DataFrame({
    "Data": pd.to_datetime(col_data, errors="coerce"),
    "Cliente": col_nome,
    "Email": col_email,
    "Valor": col_valor,
    "Telefone": col_tel.astype(str),
    "Compras": col_compras,
    "Classificação": col_class,
    "Dias desde compra": col_dias
})

# ----------------------------------------
# ARREDONDAMENTO DOS DIAS
# ----------------------------------------
def safe_round(value):
    try:
        value = float(str(value).replace(",", "."))
        return int(round(value))
    except:
        return None

base["Dias arredondados"] = base["Dias desde compra"].apply(safe_round)

# ----------------------------------------
# ESTADO DE CARDS CONCLUÍDOS
# ----------------------------------------
if "concluidos" not in st.session_state:
    st.session_state["concluidos"] = set()

def concluir(tel):
    st.session_state["concluidos"].add(str(tel))
    st.rerun()

# ----------------------------------------
# TÍTULO E FILTRO
# ----------------------------------------
st.title("📅 CRM Sportech – Tarefas do Dia")

class_filter = st.radio(
    "Filtrar por classificação:",
    ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
    horizontal=True
)

# ----------------------------------------
# CONFIGURAÇÃO DAS METAS DIÁRIAS
# ----------------------------------------
st.subheader("⚙️ Configurações do dia")

c1, c2, c3 = st.columns(3)

meta_novos = c1.number_input("Meta de Check-in (Novos)", value=10, min_value=0)
meta_prom = c2.number_input("Promissores por dia", value=20, min_value=0)
meta_leais = c3.number_input("Leais + Campeões por dia", value=10, min_value=0)

# ----------------------------------------
# SELEÇÃO DAS TAREFAS
# ----------------------------------------

novos = base[(base["Classificação"] == "Novo") & (base["Dias arredondados"] >= 15)]
novos = novos.sort_values("Dias arredondados", ascending=False).head(meta_novos)

prom = base[base["Classificação"] == "Promissor"]
prom = prom.sort_values("Dias arredondados", ascending=False).head(meta_prom)

leal_camp = base[base["Classificação"].isin(["Leal", "Campeão"])]
leal_camp = leal_camp.sort_values("Dias arredondados", ascending=False).head(meta_leais)

risco = base[base["Classificação"] == "Em risco"].sort_values("Dias arredondados")

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

df_dia = df_dia[~df_dia["Telefone"].isin(st.session_state["concluidos"])]

if class_filter != "Todos":
    df_dia = df_dia[df_dia["Classificação"] == class_filter]

# ----------------------------------------
# SE NÃO TIVER TAREFAS
# ----------------------------------------
st.subheader("📋 Tarefas do Dia")

if df_dia.empty:
    st.info("Nenhuma tarefa encontrada para hoje.")
    st.stop()

# ----------------------------------------
# GERAR HTML DOS CARDS
# ----------------------------------------
html_cards = "<div class='grid-container'>"

for idx, row in df_dia.iterrows():

    valor = safe_valor(row["Valor"])
    dias = row["Dias arredondados"] if pd.notna(row["Dias arredondados"]) else "—"

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

components.html(html_cards, height=1700, scrolling=True)

# ----------------------------------------
# BOTÕES STREAMLIT INVISÍVEIS
# ----------------------------------------
for idx, row in df_dia.iterrows():
    if st.button("✔", key=f"btn_{idx}", help="Concluir tarefa"):
        concluir(row["Telefone"])
