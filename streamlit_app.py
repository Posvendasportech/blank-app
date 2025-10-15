import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dashboard de Vendas", layout="wide")

# --- Carrega dados do Google Sheets ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"
df = pd.read_csv(SHEET_URL)

# --- Limpeza e preparação ---
df["DATA DE INÍCIO"] = pd.to_datetime(df["DATA DE INÍCIO"], errors="coerce")
df["VALOR (R$)"] = (
    df["VALOR (R$)"]
    .astype(str)
    .str.replace("R\$", "", regex=True)
    .str.replace(",", ".")
    .astype(float)
)

# --- Filtros laterais ---
st.sidebar.header("Filtros 🔍")

grupos = st.sidebar.multiselect("Grupo RFM", sorted(df["GRUPO RFM"].dropna().unique()))
produtos = st.sidebar.multiselect("Produto", sorted(df["PRODUTO"].dropna().unique()))
data_range = st.sidebar.date_input(
    "Período",
    [df["DATA DE INÍCIO"].min(), df["DATA DE INÍCIO"].max()]
)

df_filtrado = df.copy()
if grupos:
    df_filtrado = df_filtrado[df_filtrado["GRUPO RFM"].isin(grupos)]
if produtos:
    df_filtrado = df_filtrado[df_filtrado["PRODUTO"].isin(produtos)]
df_filtrado = df_filtrado[
    (df_filtrado["DATA DE INÍCIO"] >= pd.to_datetime(data_range[0])) &
    (df_filtrado["DATA DE INÍCIO"] <= pd.to_datetime(data_range[1]))
]

# --- KPIs ---
total_vendas = df_filtrado["VALOR (R$)"].sum()
clientes = df_filtrado["NOME COMPLETO"].nunique()
ticket_medio = total_vendas / clientes if clientes > 0 else 0
contato_perc = (df_filtrado["CONTATO FEITO"].notna().mean()) * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 Total em Vendas", f"R$ {total_vendas:,.2f}")
col2.metric("👥 Clientes", clientes)
col3.metric("🎯 Ticket Médio", f"R$ {ticket_medio:,.2f}")
col4.metric("📞 Contato Feito (%)", f"{contato_perc:.1f}%")

# --- Gráficos ---
st.markdown("### 📊 Vendas por Dia")
graf_vendas = px.bar(
    df_filtrado.groupby("DATA DE INÍCIO")["VALOR (R$)"].sum().reset_index(),
    x="DATA DE INÍCIO",
    y="VALOR (R$)",
    title="Vendas por Dia",
)
st.plotly_chart(graf_vendas, use_container_width=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🧭 Distribuição por Grupo RFM")
    graf_rfm = px.pie(
        df_filtrado,
        names="GRUPO RFM",
        title="Distribuição de Clientes por Grupo",
    )
    st.plotly_chart(graf_rfm, use_container_width=True)

with col2:
    st.markdown("### 📦 Vendas por Produto")
    graf_prod = px.bar(
        df_filtrado.groupby("PRODUTO")["VALOR (R$)"].sum().reset_index(),
        x="PRODUTO",
        y="VALOR (R$)",
        title="Vendas por Produto",
    )
    st.plotly_chart(graf_prod, use_container_width=True)
