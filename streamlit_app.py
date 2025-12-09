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
col_data = df.iloc[:, 0]      
col_nome = df.iloc[:, 1]      
col_email = df.iloc[:, 2]     
col_valor = df.iloc[:, 3]     
col_tel = df.iloc[:, 4]       
col_compras = df.iloc[:, 5]   
col_class = df.iloc[:, 6]     
col_dias = df.iloc[:, 8]      


# ------------------------------
# Criar coluna numérica segura de dias
# ------------------------------
def converte_dias(v):
    try:
        v = str(v).strip().replace(",", ".")
        v = float(v)
        return int(round(v))
    except:
        return None  # Nunca retorna string → evita erro no filtro

# ------------------------------
# Função formatar valor com segurança
# ------------------------------
def safe_valor(v):
    try:
        if pd.isna(v):
            return "—"
        v = str(v).replace("R$", "").replace(" ", "").replace(",", ".")
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
    "Dias_num": col_dias.apply(converte_dias)   # 🔥 agora 100% numérico
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
st.subheader("⚙️ Configurações do dia")

c1, c2, c3 = st.columns(3)

meta_novos = c1.number_input("Meta de Check-in (Novos)", value=10, min_value=0)
meta_prom = c2.number_input("Promissores por dia", value=20, min_value=0)
meta_leais = c3.number_input("Leais + Campeões por dia", value=10, min_value=0)


# ------------------------------
# Seleção de tarefas do dia
# ------------------------------

# Novos com 15+ dias
novos = base[(base["Classificação"] == "Novo") & (base["Dias_num"] >= 15)]
novos = novos.sort_values("Dias_num", ascending=False).head(meta_novos)

# Promissores
prom = base[base["Classificação"] == "Promissor"]
prom = prom.sort_values("Dias_num", ascending=False).head(meta_prom)

# Leais + Campeões
leal_camp = base[base["Classificação"].isin(["Leal", "Campeão"])]
leal_camp = leal_camp.sort_values("Dias_num", ascending=False).head(meta_leais)

# Em risco
risco = base[base["Classificação"] == "Em risco"].sort_values("Dias_num")

# Montar lista final
frames = []

if not novos.empty:
    novos["Grupo"] = "Novo"
    frames.append(novos)

if not prom.empty:
    prom["Grupo"] = "Promissor"
    frames.append(prom)

if not leal_camp.empty:
    leal_camp["Grupo"] = "Leal/Campeão"
    frames.append(leal_camp)

if not risco.empty:
    risco["Grupo"] = "Em risco"
    frames.append(risco)

df_dia = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# Remover concluídos
df_dia = df_dia[~df_dia["Telefone"].isin(st.session_state["concluidos"])]

# Aplicar filtro
if class_filter != "Todos":
    df_dia = df_dia[df_dia["Classificação"] == class_filter]


# ------------------------------
# CSS dos cards
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


# ------------------------------
# Gerar HTML dos cards
# ------------------------------
html_cards = css + "<div class='grid-container'>"

for idx, row in df_dia.iterrows():

    valor = safe_valor(row["Valor"])
    dias = row["Dias_num"] if pd.notna(row["Dias_num"]) else "—"

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


# ------------------------------
# Renderizar HTML
# ------------------------------
components.html(html_cards, height=1800, scrolling=True)


# ------------------------------
# Botões ocultos de conclusão
# ------------------------------
for idx, row in df_dia.iterrows():
    if st.button("✔", key=f"btn_{idx}"):
        concluir(row["Telefone"])
