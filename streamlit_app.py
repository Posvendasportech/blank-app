# streamlit_app.py
import streamlit as st
import pandas as pd
from urllib.parse import quote
from datetime import datetime

# ----------------------------------------
# ⚙️ Configuração da página
# ----------------------------------------
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

# Tema escuro simples
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background-color: #000000;
        color: #FFFFFF;
    }
    [data-testid="stHeader"] {
        background: rgba(0,0,0,0.0);
    }
    [data-testid="stSidebar"] {
        background-color: #050505;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        return pd.DataFrame()

# ----------------------------------------
# 🧠 Estado para tarefas concluídas (por telefone)
# ----------------------------------------
if "concluidos" not in st.session_state:
    st.session_state["concluidos"] = set()

def marcar_concluido(telefone: str):
    st.session_state["concluidos"].add(str(telefone))
    st.rerun()

# ----------------------------------------
# 📌 Carregar planilha de leads
# ----------------------------------------
df_leads = load_sheet(SHEET2_ID, DEFAULT_SHEET2_SHEETNAME)

# ----------------------------------------
# 📌 Título / layout principal
# ----------------------------------------
st.title("📅 CRM Sportech – Painel de Tarefas do Dia")

if df_leads.empty:
    st.warning("⚠️ A planilha de leads não pôde ser carregada.")
    st.stop()

# ----------------------------------------
# 🧩 Mapeamento das colunas A–G
# ----------------------------------------
col_data          = df_leads.iloc[:, 0]  # A - Data do último pedido
col_nome          = df_leads.iloc[:, 1]  # B - Nome
col_email         = df_leads.iloc[:, 2]  # C - Email
col_valor         = df_leads.iloc[:, 3]  # D - Valor total gasto
col_telefone      = df_leads.iloc[:, 4]  # E - Telefone
col_compras       = df_leads.iloc[:, 5]  # F - Nº de compras
col_classificacao = df_leads.iloc[:, 6]  # G - Classificação

df_base = pd.DataFrame({
    "Data": pd.to_datetime(col_data, errors="coerce"),
    "Cliente": col_nome,
    "Email": col_email,
    "Telefone": col_telefone.astype(str),
    "Valor": col_valor,
    "Compras": col_compras,
    "Classificação": col_classificacao,
})

df_base["Dias desde compra"] = (datetime.today() - df_base["Data"]).dt.days

# ----------------------------------------
# 🔵 TOPO – INDICADORES BÁSICOS + CONFIG DO DIA
# ----------------------------------------
st.markdown("### 🔹 Indicadores básicos & configuração do dia")

col_indic, col_conf = st.columns(2)

with col_conf:
    st.markdown("##### ⚙️ Metas de contatos do dia")
    meta_novos = st.number_input("Novos (dia 15+)", min_value=0, value=10, step=1)
    meta_prom = st.number_input("Promissores/dia", min_value=0, value=20, step=1)
    meta_leais_cam = st.number_input("Leais + Campeões/dia", min_value=0, value=10, step=1)

with col_indic:
    total_base = len(df_base)
    total_novos_prontos = len(
        df_base[(df_base["Classificação"] == "Novo") & (df_base["Dias desde compra"] >= 15)]
    )
    total_prom = len(df_base[df_base["Classificação"] == "Promissor"])
    total_leais = len(df_base[df_base["Classificação"] == "Leal"])
    total_camp = len(df_base[df_base["Classificação"] == "Campeão"])
    total_risco = len(df_base[df_base["Classificação"] == "Em risco"])
    total_dorm = len(df_base[df_base["Classificação"] == "Dormente"])

    st.metric("Base total", total_base)
    c1, c2, c3 = st.columns(3)
    c1.metric("Novos (15+ dias)", total_novos_prontos)
    c2.metric("Promissores", total_prom)
    c3.metric("Leais + Campeões", total_leais + total_camp)
    c4, c5 = st.columns(2)
    c4.metric("Em risco", total_risco)
    c5.metric("Dormentes", total_dorm)

# ----------------------------------------
# 🧭 PANORAMA DE CONTATOS DO DIA
# ----------------------------------------
st.markdown("### 🔹 Panorama de contatos do dia")

# ------------------ Seleção por grupo ------------------
# NOVOS → todos com 15+ dias, limitado pela meta
novos_raw = df_base[(df_base["Classificação"] == "Novo") & (df_base["Dias desde compra"] >= 15)]
novos_raw = novos_raw.sort_values("Dias desde compra", ascending=False)
novos_dia = novos_raw.head(meta_novos) if meta_novos > 0 else novos_raw.iloc[0:0]

# PROMISSORES → meta_prom por dia
prom_raw = df_base[df_base["Classificação"] == "Promissor"].sort_values(
    "Dias desde compra", ascending=False
)
prom_dia = prom_raw.head(meta_prom) if meta_prom > 0 else prom_raw.iloc[0:0]

# LEAIS + CAMPEÕES → meta combinada
leal_raw = df_base[df_base["Classificação"] == "Leal"]
camp_raw = df_base[df_base["Classificação"] == "Campeão"]
leal_camp_raw = pd.concat([leal_raw, camp_raw]).sort_values(
    "Dias desde compra", ascending=False
)
leal_camp_dia = leal_camp_raw.head(meta_leais_cam) if meta_leais_cam > 0 else leal_camp_raw.iloc[0:0]

# EM RISCO → todos, priorizando quem está com data mais recente (virou risco "agora")
risco_dia = df_base[df_base["Classificação"] == "Em risco"].sort_values(
    "Dias desde compra"
)

# DORMENTES → extra, mostrados à parte
dorm_dia = df_base[df_base["Classificação"] == "Dormente"].sort_values(
    "Dias desde compra", ascending=False
)

# Montar DF de tarefas do dia (sem dormentes ainda)
lista_frames = []
if not novos_dia.empty:
    temp = novos_dia.copy()
    temp["Grupo"] = "Novo (15+)"
    lista_frames.append(temp)

if not prom_dia.empty:
    temp = prom_dia.copy()
    temp["Grupo"] = "Promissor"
    lista_frames.append(temp)

if not leal_camp_dia.empty:
    temp = leal_camp_dia.copy()
    temp["Grupo"] = "Leal/Campeão"
    lista_frames.append(temp)

if not risco_dia.empty:
    temp = risco_dia.copy()
    temp["Grupo"] = "Em risco"
    lista_frames.append(temp)

if lista_frames:
    df_tarefas_dia = pd.concat(lista_frames, ignore_index=True)
else:
    df_tarefas_dia = pd.DataFrame(columns=df_base.columns.tolist() + ["Grupo"])

# Remover quem já foi concluído nesta sessão
df_tarefas_dia = df_tarefas_dia[
    ~df_tarefas_dia["Telefone"].astype(str).isin(st.session_state["concluidos"])
]

total_tarefas = len(df_tarefas_dia)

c_pan1, c_pan2, c_pan3 = st.columns(3)
c_pan1.metric("Total selecionado para hoje", total_tarefas)
c_pan2.metric("Concluídos (sessão)", len(st.session_state["concluidos"]))
c_pan3.metric("Restantes", max(total_tarefas - len(st.session_state["concluidos"]), 0))

# ----------------------------------------
# 📋 TAREFAS DIÁRIAS (tabela com botão concluir)
# ----------------------------------------
st.markdown("### 🔹 Tarefas diárias")

if total_tarefas == 0:
    st.info("Nenhum cliente selecionado para hoje com os critérios atuais.")
else:
    # ordenar por prioridade operacional: Em risco > Novo > Promissor > Leal/Camp
    ordem_grupo = pd.CategoricalDtype(
        ["Em risco", "Novo (15+)", "Promissor", "Leal/Campeão"], ordered=True
    )
    df_tarefas_dia["Grupo"] = df_tarefas_dia["Grupo"].astype(ordem_grupo)
    df_tarefas_dia = df_tarefas_dia.sort_values(
        ["Grupo", "Dias desde compra"], ascending=[True, False]
    )

    # Exibir linha a linha com botão concluir
    for idx, row in df_tarefas_dia.iterrows():
        with st.container():
            cols = st.columns([2, 2, 1, 1, 1, 1])

            cols[0].markdown(f"**👤 {row['Cliente']}**  \n📱 {row['Telefone']}")
            cols[1].markdown(
                f"**Grupo:** {row['Grupo']}  \nClassificação: {row['Classificação']}"
            )
            cols[2].markdown(f"🛒 Compras: **{row['Compras']}**")
            cols[3].markdown(f"💰 Valor: **R$ {row['Valor']}**")
            cols[4].markdown(f"⏳ Dias desde compra: **{row['Dias desde compra']}**")

            if cols[5].button("✔ Concluir", key=f"concluir_{idx}"):
                marcar_concluido(row["Telefone"])

        st.markdown("---")

# ----------------------------------------
# 📊 GRUPO TOTAL – visão geral da base
# ----------------------------------------
st.markdown("### 🔹 Grupo total (base completa)")

with st.expander("Ver base completa por classificação"):
    st.dataframe(
        df_base.sort_values("Dias desde compra", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
