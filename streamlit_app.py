import streamlit as st
import pandas as pd
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"

# --- Atualiza o app automaticamente a cada 60 segundos ---
st_autorefresh(interval=60 * 1000, key="autorefresh")

st.sidebar.title("⚙️ Controles")

if st.sidebar.button("🔄 Atualizar dados agora"):
    st.cache_data.clear()
    st.experimental_rerun()

@st.cache_data(ttl=60)  # guarda os dados por 60 segundos
def carregar_dados():
    return pd.read_csv(SHEET_URL)

df = carregar_dados()
st.success(f"Dados atualizados às {time.strftime('%H:%M:%S')}")

# --- Limpeza dos dados ---
df["DATA DE INÍCIO"] = pd.to_datetime(df["DATA DE INÍCIO"], errors="coerce")
df["VALOR (R$)"] = (
    df["VALOR (R$)"]
    .astype(str)
    .str.replace("R\$", "", regex=True)
    .str.replace(",", ".")
    .astype(float)
)

# --- Filtros ---
st.sidebar.header("Filtros")
grupos = st.sidebar.multiselect("Grupo RFM", df["GRUPO RFM"].dropna().unique())
produtos = st.sidebar.multiselect("Produto", df["PRODUTO"].dropna().unique())

df_filtrado = df.copy()
if grupos:
    df_filtrado = df_filtrado[df_filtrado["GRUPO RFM"].isin(grupos)]
if produtos:
    df_filtrado = df_filtrado[df_filtrado["PRODUTO"].isin(produtos)]

# --- KPIs ---
total_vendas = df_filtrado["VALOR (R$)"].sum()
clientes = df_filtrado["NOME COMPLETO"].nunique()
ticket_medio = total_vendas / clientes if clientes > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("💰 Total de Vendas", f"R$ {total_vendas:,.2f}")
col2.metric("👥 Clientes Únicos", clientes)
col3.metric("🎯 Ticket Médio", f"R$ {ticket_medio:,.2f}")

# --- Gráficos ---
st.subheader("📊 Vendas por Data")
graf1 = px.bar(df_filtrado, x="DATA DE INÍCIO", y="VALOR (R$)", title="Vendas por Dia")
st.plotly_chart(graf1, use_container_width=True)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Distribuição por Grupo RFM")
    graf2 = px.pie(df_filtrado, names="GRUPO RFM", title="Grupos RFM")
    st.plotly_chart(graf2, use_container_width=True)
with col2:
    st.subheader("Vendas por Produto")
    graf3 = px.bar(
        df_filtrado.groupby("PRODUTO")["VALOR (R$)"].sum().reset_index(),
        x="PRODUTO",
        y="VALOR (R$)",
        title="Total de Vendas por Produto"
    )
    st.plotly_chart(graf3, use_container_width=True)
