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
st.subheader("📊 Vendas por Dia")

# Agrupa por data e soma as vendas
vendas_por_dia = df_filtrado.groupby("DATA DE INÍCIO")["VALOR (R$)"].sum().reset_index()

# Remove domingos (weekday=6)
vendas_por_dia = vendas_por_dia[vendas_por_dia["DATA DE INÍCIO"].dt.weekday != 6]

# Ordena por data
vendas_por_dia = vendas_por_dia.sort_values("DATA DE INÍCIO")

# Gráfico de linha diário
# --- Gráficos ---


# Agrupa por data e soma as vendas
vendas_por_dia = df_filtrado.groupby("DATA DE INÍCIO")["VALOR (R$)"].sum().reset_index()

# Remove domingos (weekday=6)
vendas_por_dia = vendas_por_dia[vendas_por_dia["DATA DE INÍCIO"].dt.weekday != 6]

# Ordena por data
vendas_por_dia = vendas_por_dia.sort_values("DATA DE INÍCIO")

# Calcula média móvel de 7 dias para tendência
vendas_por_dia["Tendência"] = vendas_por_dia["VALOR (R$)"].rolling(window=7, min_periods=1).mean()

# Gráfico de linha com duas séries: vendas diárias + tendência
graf1 = px.line(
    vendas_por_dia,
    x="DATA DE INÍCIO",
    y=["VALOR (R$)", "Tendência"],
    title="Vendas por Dia com Linha de Tendência",
    labels={"DATA DE INÍCIO": "Data", "value": "Vendas (R$)", "variable": "Legenda"},
    markers=True
)

# Personaliza cores e linhas
graf1.update_traces(selector=dict(name="VALOR (R$)"), line=dict(width=2, color='cyan'), marker=dict(color='cyan', size=6))
graf1.update_traces(selector=dict(name="Tendência"), line=dict(width=3, color='orange', dash='dash'))

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

# --- Vendas por Dia da Semana ---
st.subheader("📊 Vendas por Dia da Semana")

# Adiciona coluna com nome do dia da semana
df_filtrado["DIA_DA_SEMANA"] = df_filtrado["DATA DE INÍCIO"].dt.day_name()

# Agrupa vendas por dia da semana
vendas_dia_semana = df_filtrado.groupby("DIA_DA_SEMANA")["VALOR (R$)"].sum().reindex(
    ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
).reset_index()

# Gráfico de barras
graf_dia_semana = px.bar(
    vendas_dia_semana,
    x="DIA_DA_SEMANA",
    y="VALOR (R$)",
    title="Vendas por Dia da Semana (excluindo domingos)",
    labels={"DIA_DA_SEMANA":"Dia da Semana", "VALOR (R$)":"Vendas (R$)"},
    text="VALOR (R$)"
)

graf_dia_semana.update_traces(marker_color='cyan')
graf_dia_semana.update_layout(
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    xaxis=dict(showgrid=True, gridcolor='gray'),
    yaxis=dict(showgrid=True, gridcolor='gray')
)

st.plotly_chart(graf_dia_semana, use_container_width=True)


# --- Comparação entre Grupos RFM ---
st.subheader("📊 Análise por Grupo RFM")

# Agrupa por Grupo RFM
rfm_analise = df_filtrado.groupby("GRUPO RFM").agg({
    "VALOR (R$)": "sum",
    "NOME COMPLETO": "nunique"
}).reset_index()

# Calcula ticket médio por grupo
rfm_analise["Ticket Médio"] = rfm_analise["VALOR (R$)"] / rfm_analise["NOME COMPLETO"]

# Gráfico de barras: total de vendas por grupo
graf_rfm_vendas = px.bar(
    rfm_analise,
    x="GRUPO RFM",
    y="VALOR (R$)",
    title="Total de Vendas por Grupo RFM",
    labels={"GRUPO RFM": "Grupo RFM", "VALOR (R$)":"Vendas (R$)"},
    text="VALOR (R$)"
)
graf_rfm_vendas.update_traces(marker_color='cyan')
graf_rfm_vendas.update_layout(
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    xaxis=dict(showgrid=True, gridcolor='gray'),
    yaxis=dict(showgrid=True, gridcolor='gray')
)

st.plotly_chart(graf_rfm_vendas, use_container_width=True)





# --- Curva de Crescimento Acumulada ---
st.subheader("📈 Curva de Crescimento Acumulada de Vendas")

# Agrupa vendas por dia e soma
vendas_diarias = df_filtrado.groupby("DATA DE INÍCIO")["VALOR (R$)"].sum().reset_index()

# Ordena por data
vendas_diarias = vendas_diarias.sort_values("DATA DE INÍCIO")

# Calcula vendas acumuladas
vendas_diarias["Acumulado"] = vendas_diarias["VALOR (R$)"].cumsum()

# Gráfico de linha
graf_acumulado = px.line(
    vendas_diarias,
    x="DATA DE INÍCIO",
    y="Acumulado",
    title="Curva de Crescimento Acumulada de Vendas",
    labels={"DATA DE INÍCIO":"Data", "Acumulado":"Vendas Acumuladas (R$)"},
    markers=True
)

# Estilo
graf_acumulado.update_traces(line=dict(width=2, color='cyan'))
graf_acumulado.update_layout(
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    xaxis=dict(showgrid=True, gridcolor='gray'),
    yaxis=dict(showgrid=True, gridcolor='gray')
)

st.plotly_chart(graf_acumulado, use_container_width=True)


# --- Comparação de Períodos Iguais ---
st.subheader("📊 Comparação de Vendas: Período Atual vs Período Igual do Mês Anterior")

from datetime import datetime, timedelta

# Define período atual (até hoje)
hoje = datetime.today()
primeiro_dia_mes_atual = hoje.replace(day=1)
dia_atual = hoje.day

# Define período equivalente do mês anterior
primeiro_dia_mes_anterior = (primeiro_dia_mes_atual - timedelta(days=1)).replace(day=1)
ultimo_dia_mes_anterior = primeiro_dia_mes_anterior.replace(day=dia_atual)

# Filtra vendas do período atual e mês anterior
vendas_mes_atual = df_filtrado[
    (df_filtrado["DATA DE INÍCIO"] >= primeiro_dia_mes_atual) &
    (df_filtrado["DATA DE INÍCIO"] <= hoje)
]["VALOR (R$)"].sum()

vendas_mes_anterior = df_filtrado[
    (df_filtrado["DATA DE INÍCIO"] >= primeiro_dia_mes_anterior) &
    (df_filtrado["DATA DE INÍCIO"] <= ultimo_dia_mes_anterior)
]["VALOR (R$)"].sum()

# Calcula variação percentual
delta = ((vendas_mes_atual - vendas_mes_anterior) / vendas_mes_anterior) * 100 if vendas_mes_anterior != 0 else 0

# Exibe métricas
st.metric(
    label=f"Vendas: {primeiro_dia_mes_atual.strftime('%d/%m')} até {hoje.strftime('%d/%m')} (este mês vs mês anterior)",
    value=f"R$ {vendas_mes_atual:,.2f}",
    delta=f"{delta:.2f}%"
)

# Gráfico comparativo
comparacao = pd.DataFrame({
    "Período": [f"Mês Anterior (até {dia_atual})", f"Este Mês (até {dia_atual})"],
    "Vendas (R$)": [vendas_mes_anterior, vendas_mes_atual]
})

import plotly.express as px

graf_comparacao = px.bar(
    comparacao,
    x="Período",
    y="Vendas (R$)",
    text="Vendas (R$)",
    title=f"Comparação de Vendas até o Dia {dia_atual}",
    labels={"Vendas (R$)":"Vendas (R$)", "Período":"Período"}
)
graf_comparacao.update_traces(marker_color='cyan')
graf_comparacao.update_layout(
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white')
)

st.plotly_chart(graf_comparacao, use_container_width=True)


# --- Crescimento de Vendas Relacionado ao Valor ---
st.subheader("📊 Crescimento Real de Vendas com Percentual")

import plotly.graph_objects as go

# Crescimento semanal
vendas_semanais = df_filtrado.resample("W-MON", on="DATA DE INÍCIO")["VALOR (R$)"].sum().reset_index()
vendas_semanais["Crescimento (%)"] = vendas_semanais["VALOR (R$)"].pct_change() * 100

# Gráfico semanal
fig_semanal = go.Figure()

# Barra: valor das vendas
fig_semanal.add_trace(go.Bar(
    x=vendas_semanais["DATA DE INÍCIO"],
    y=vendas_semanais["VALOR (R$)"],
    name="Vendas (R$)",
    marker_color='cyan',
    text=vendas_semanais["VALOR (R$)"].map(lambda x: f"R$ {x:,.0f}"),
    textposition='auto'
))

# Linha: crescimento percentual
fig_semanal.add_trace(go.Scatter(
    x=vendas_semanais["DATA DE INÍCIO"],
    y=vendas_semanais["Crescimento (%)"],
    name="Crescimento (%)",
    yaxis="y2",
    mode="lines+markers",
    line=dict(color="orange", width=2)
))

# Layout com dois eixos Y
fig_semanal.update_layout(
    title="Crescimento Semanal de Vendas",
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    xaxis=dict(showgrid=True, gridcolor='gray'),
    yaxis=dict(title="Vendas (R$)", showgrid=True, gridcolor='gray'),
    yaxis2=dict(title="Crescimento (%)", overlaying="y", side="right", showgrid=False),
    legend=dict(font=dict(color='white'))
)

st.plotly_chart(fig_semanal, use_container_width=True)

# Crescimento mensal
vendas_mensais = df_filtrado.resample("M", on="DATA DE INÍCIO")["VALOR (R$)"].sum().reset_index()
vendas_mensais["Crescimento (%)"] = vendas_mensais["VALOR (R$)"].pct_change() * 100

# Gráfico mensal
fig_mensal = go.Figure()

# Barra: valor das vendas
fig_mensal.add_trace(go.Bar(
    x=vendas_mensais["DATA DE INÍCIO"],
    y=vendas_mensais["VALOR (R$)"],
    name="Vendas (R$)",
    marker_color='cyan',
    text=vendas_mensais["VALOR (R$)"].map(lambda x: f"R$ {x:,.0f}"),
    textposition='auto'
))

# Linha: crescimento percentual
fig_mensal.add_trace(go.Scatter(
    x=vendas_mensais["DATA DE INÍCIO"],
    y=vendas_mensais["Crescimento (%)"],
    name="Crescimento (%)",
    yaxis="y2",
    mode="lines+markers",
    line=dict(color="orange", width=2)
))

# Layout com dois eixos Y
fig_mensal.update_layout(
    title="Crescimento Mensal de Vendas",
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    xaxis=dict(showgrid=True, gridcolor='gray'),
    yaxis=dict(title="Vendas (R$)", showgrid=True, gridcolor='gray'),
    yaxis2=dict(title="Crescimento (%)", overlaying="y", side="right", showgrid=False),
    legend=dict(font=dict(color='white'))
)

st.plotly_chart(fig_mensal, use_container_width=True)
