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

# KPIs por grupo RFM
st.subheader("Métricas por Grupo RFM")
for index, row in rfm_analise.iterrows():
    st.markdown(f"**{row['GRUPO RFM']}**: Total Vendas = R$ {row['VALOR (R$)']:.2f} | "
                f"Clientes = {row['NOME COMPLETO']} | Ticket Médio = R$ {row['Ticket Médio']:.2f}")

# --- Heatmap: Dia da Semana x Mês (corrigido) ---
st.subheader("📊 Heatmap de Vendas: Dia da Semana x Mês")

# Adiciona colunas de mês e dia da semana
df_filtrado["MÊS"] = df_filtrado["DATA DE INÍCIO"].dt.strftime("%Y-%m")
df_filtrado["DIA_DA_SEMANA"] = df_filtrado["DATA DE INÍCIO"].dt.day_name()

# Agrupa por mês e dia da semana
heatmap_data = df_filtrado.groupby(["MÊS","DIA_DA_SEMANA"])["VALOR (R$)"].sum().reset_index()

# Pivot para formato de heatmap
heatmap_pivot = heatmap_data.pivot(index="DIA_DA_SEMANA", columns="MÊS", values="VALOR (R$)")

# Substitui NaN por 0
heatmap_pivot = heatmap_pivot.fillna(0)

# Ordena os dias da semana corretamente
dias_ordem = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
heatmap_pivot = heatmap_pivot.reindex(dias_ordem)

# Gráfico de heatmap
import plotly.figure_factory as ff

z = heatmap_pivot.values
x = heatmap_pivot.columns
y = heatmap_pivot.index

heatmap = ff.create_annotated_heatmap(
    z=z,
    x=x,
    y=y,
    colorscale='Viridis',
    showscale=True,
    font_colors=['white'],
    reversescale=False
)

# Layout fundo preto
heatmap.update_layout(
    plot_bgcolor='black',
    paper_bgcolor='black',
    font=dict(color='white', size=12),
    title=dict(text="Heatmap de Vendas por Dia da Semana e Mês", font=dict(color='white', size=18))
)

st.plotly_chart(heatmap, use_container_width=True)
