import streamlit as st
import pandas as pd
import time
import plotly.express as px

SHEET_URL = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"

st.set_page_config(page_title="Dashboard de Vendas", layout="wide")

# --- Função para carregar dados com cache de 60 segundos ---
@st.cache_data(ttl=60)
def carregar_dados():
    df = pd.read_csv(SHEET_URL)
    df["DATA DE INÍCIO"] = pd.to_datetime(df["DATA DE INÍCIO"], errors="coerce")
    df["VALOR (R$)"] = (
        df["VALOR (R$)"]
        .astype(str)
        .str.replace("R\$", "", regex=True)
        .str.replace(",", ".")
        .astype(float)
    )
    return df

df = carregar_dados()
st.success(f"Dados atualizados às {time.strftime('%H:%M:%S')}")

# --- Sidebar ---
st.sidebar.title("⚙️ Controles")
if st.sidebar.button("🔄 Atualizar dados agora"):
    st.cache_data.clear()
    df = carregar_dados()  # Recarrega os dados manualmente

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


# --- Gráfico de crescimento mensal ---
st.subheader("📈 Crescimento Mensal de Vendas")

# Agrupa por mês
df_filtrado["MÊS"] = df_filtrado["DATA DE INÍCIO"].dt.to_period("M").dt.to_timestamp()
vendas_mensal = df_filtrado.groupby("MÊS")["VALOR (R$)"].sum().reset_index()

# Calcula acumulado mensal (opcional)
vendas_mensal["Vendas Acumuladas"] = vendas_mensal["VALOR (R$)"].cumsum()

# Cria gráfico de linha
graf_mensal = px.line(
    vendas_mensal,
    x="MÊS",
    y="Vendas Acumuladas",  # ou use "VALOR (R$)" se quiser só por mês
    title="Curva de Crescimento Mensal de Vendas",
    labels={"MÊS": "Mês", "Vendas Acumuladas": "Total Acumulado (R$)"},
    markers=True
)

st.plotly_chart(graf_mensal, use_container_width=True)
