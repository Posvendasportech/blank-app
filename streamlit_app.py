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
st.subheader("📊 Vendas por Dia (Linha)")

# Agrupa por data e soma as vendas
vendas_por_dia = df_filtrado.groupby("DATA DE INÍCIO")["VALOR (R$)"].sum().reset_index()

# Ordena por data
vendas_por_dia = vendas_por_dia.sort_values("DATA DE INÍCIO")

# Gráfico de linha diário
graf1 = px.line(
    vendas_por_dia,
    x="DATA DE INÍCIO",
    y="VALOR (R$)",
    title="Vendas por Dia",
    labels={"DATA DE INÍCIO": "Data", "VALOR (R$)": "Vendas (R$)"},
    markers=True
)

# Linha fina e elegante
graf1.update_traces(line=dict(width=2, color='cyan'), marker=dict(color='cyan', size=6))

# Fundo preto e layout limpo
graf1.update_layout(
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    xaxis=dict(showgrid=True, gridcolor='gray', zerolinecolor='gray'),
    yaxis=dict(showgrid=True, gridcolor='gray', zerolinecolor='gray'),
    title=dict(font=dict(color='white', size=20))
)

st.plotly_chart(graf1, use_container_width=True)

# --- Gráficos auxiliares ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("Distribuição por Grupo RFM")
    graf2 = px.pie(df_filtrado, names="GRUPO RFM", title="Grupos RFM")
    graf2.update_layout(
        plot_bgcolor='black',
        paper_bgcolor='black',
        font=dict(color='white'),
        title=dict(font=dict(color='white', size=18))
    )
    st.plotly_chart(graf2, use_container_width=True)

with col2:
    st.subheader("Vendas por Produto")
    graf3 = px.bar(
        df_filtrado.groupby("PRODUTO")["VALOR (R$)"].sum().reset_index(),
        x="PRODUTO",
        y="VALOR (R$)",
        title="Total de Vendas por Produto"
    )
    graf3.update_traces(marker_color='cyan')
    graf3.update_layout(
        plot_bgcolor='black',
        paper_bgcolor='black',
        font=dict(color='white'),
        xaxis=dict(showgrid=True, gridcolor='gray', zerolinecolor='gray'),
        yaxis=dict(showgrid=True, gridcolor='gray', zerolinecolor='gray'),
        title=dict(font=dict(color='white', size=18))
    )
    st.plotly_chart(graf3, use_container_width=True)




# --- Gráfico de vendas semana a semana (linha fina) ---
st.subheader("📈 Vendas Semanais (Linha Fina)")

# Cria coluna de semana (início da semana)
df_filtrado["SEMANA"] = df_filtrado["DATA DE INÍCIO"].dt.to_period("W").apply(lambda r: r.start_time)

# Agrupa por semana e soma as vendas
vendas_semanal = df_filtrado.groupby("SEMANA")["VALOR (R$)"].sum().reset_index()

# Cria gráfico de linha fina
graf_semanal = px.line(
    vendas_semanal,
    x="SEMANA",
    y="VALOR (R$)",
    title="Vendas Semanais",
    labels={"SEMANA": "Semana", "VALOR (R$)": "Vendas (R$)"},
    markers=True
)

# Personaliza a linha para ficar mais fina
graf_semanal.update_traces(line=dict(width=2, color='blue'))

# Ajusta layout para ficar mais elegante
graf_semanal.update_layout(
    xaxis_title="Semana",
    yaxis_title="Vendas (R$)",
    xaxis=dict(showgrid=True, gridcolor='gray'),
    yaxis=dict(showgrid=True, gridcolor='gray'),
    plot_bgcolor='black'
)

st.plotly_chart(graf_semanal, use_container_width=True)
