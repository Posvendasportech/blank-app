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


# --- Comparação de Meses ---
st.subheader("📊 Comparação de Vendas: Este Mês vs Mês Anterior")

# Adiciona coluna de mês
df_filtrado["MÊS"] = df_filtrado["DATA DE INÍCIO"].dt.to_period("M")

# Agrupa vendas por mês
vendas_mensais = df_filtrado.groupby("MÊS")["VALOR (R$)"].sum().reset_index()
vendas_mensais["MÊS"] = vendas_mensais["MÊS"].dt.to_timestamp()

# Seleciona últimos 2 meses
ultimos_2_meses = vendas_mensais.sort_values("MÊS").tail(2)

# Calcula crescimento percentual
crescimento = ((ultimos_2_meses["VALOR (R$)"].iloc[1] - ultimos_2_meses["VALOR (R$)"].iloc[0]) /
               ultimos_2_meses["VALOR (R$)"].iloc[0] * 100)

st.metric(
    label=f"Crescimento de {ultimos_2_meses['MÊS'].iloc[0].strftime('%b/%Y')} → {ultimos_2_meses['MÊS'].iloc[1].strftime('%b/%Y')}",
    value=f"R$ {ultimos_2_meses['VALOR (R$)'].iloc[1]:,.2f}",
    delta=f"{crescimento:.2f}%"
)

# Gráfico de barras comparativo
graf_comparacao = px.bar(
    ultimos_2_meses,
    x="MÊS",
    y="VALOR (R$)",
    text="VALOR (R$)",
    title="Comparação de Vendas Mensais",
    labels={"MÊS":"Mês", "VALOR (R$)":"Vendas (R$)"}
)
graf_comparacao.update_traces(marker_color='cyan')
graf_comparacao.update_layout(
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white')
)
st.plotly_chart(graf_comparacao, use_container_width=True)


# --- Crescimento Diário, Semanal e Mensal ---
st.subheader("📊 Crescimento das Vendas (%)")

# Crescimento diário
vendas_diarias["Crescimento Diário (%)"] = vendas_diarias["VALOR (R$)"].pct_change() * 100

# Crescimento semanal
vendas_semanais = df_filtrado.resample("W-MON", on="DATA DE INÍCIO")["VALOR (R$)"].sum().reset_index()
vendas_semanais["Crescimento Semanal (%)"] = vendas_semanais["VALOR (R$)"].pct_change() * 100

# Crescimento mensal
vendas_mensais = df_filtrado.resample("M", on="DATA DE INÍCIO")["VALOR (R$)"].sum().reset_index()
vendas_mensais["Crescimento Mensal (%)"] = vendas_mensais["VALOR (R$)"].pct_change() * 100

# Gráficos de linha
graf_crescimento = make_subplots(rows=3, cols=1, shared_xaxes=False, vertical_spacing=0.1,
                                 subplot_titles=("Crescimento Diário (%)", "Crescimento Semanal (%)", "Crescimento Mensal (%)"))

import plotly.graph_objects as go

# Linha diária
graf_crescimento.add_trace(go.Scatter(
    x=vendas_diarias["DATA DE INÍCIO"],
    y=vendas_diarias["Crescimento Diário (%)"],
    mode="lines+markers",
    line=dict(color="cyan", width=2),
    name="Diário"
), row=1, col=1)

# Linha semanal
graf_crescimento.add_trace(go.Scatter(
    x=vendas_semanais["DATA DE INÍCIO"],
    y=vendas_semanais["Crescimento Semanal (%)"],
    mode="lines+markers",
    line=dict(color="orange", width=2),
    name="Semanal"
), row=2, col=1)

# Linha mensal
graf_crescimento.add_trace(go.Scatter(
    x=vendas_mensais["DATA DE INÍCIO"],
    y=vendas_mensais["Crescimento Mensal (%)"],
    mode="lines+markers",
    line=dict(color="lime", width=2),
    name="Mensal"
), row=3, col=1)

# Layout
graf_crescimento.update_layout(
    height=900,
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white'),
    title_text="Crescimento Diário, Semanal e Mensal (%)"
)

st.plotly_chart(graf_crescimento, use_container_width=True)
