import streamlit as st
import pandas as pd
import time
import plotly.express as px
from datetime import datetime, timedelta

# ------------------------------
# 🔗 URLs das planilhas
# ------------------------------
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"
SHEET_URL_2 = "https://docs.google.com/spreadsheets/d/1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc/export?format=csv"

# ------------------------------
# ⚙️ Função de carregamento com cache
# ------------------------------
@st.cache_data(ttl=60)
def carregar_dados(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar planilha: {e}")
        return pd.DataFrame()

# ------------------------------
# 📥 Carregamento dos dados
# ------------------------------
df_vendas = carregar_dados(SHEET_URL_1)
df_extra = carregar_dados(SHEET_URL_2)

# ------------------------------
# 🧹 Limpeza e preparação dos dados
# ------------------------------
if not df_vendas.empty:
    df_vendas["DATA DE INÍCIO"] = pd.to_datetime(df_vendas["DATA DE INÍCIO"], errors="coerce")
    df_vendas["VALOR (R$)"] = (
        df_vendas["VALOR (R$)"]
        .astype(str)
        .str.replace("R\$", "", regex=True)
        .str.replace(",", ".")
        .astype(float)
    )

# ------------------------------
# 🧭 Barra lateral
# ------------------------------
st.sidebar.title("⚙️ Controles")

if st.sidebar.button("🔄 Atualizar dados agora"):
    st.cache_data.clear()
    time.sleep(0.5)
    st.rerun()

st.sidebar.success(f"✅ Dados atualizados às {time.strftime('%H:%M:%S')}")

# ------------------------------
# 🗂️ Criação das abas principais
# ------------------------------
aba1, aba2 = st.tabs(["📊 Análises de Vendas (Planilha Principal)", "📑 Segunda Planilha - Análises Complementares"])



    # ------------------------------
    # 🧩 Filtros
    # ------------------------------
    st.sidebar.header("Filtros")

    if not df_vendas.empty:
        grupos = st.sidebar.multiselect("Grupo RFM", df_vendas["GRUPO RFM"].dropna().unique())
        produtos = st.sidebar.multiselect("Produto", df_vendas["PRODUTO"].dropna().unique())

        df_filtrado = df_vendas.copy()
        if grupos:
            df_filtrado = df_filtrado[df_filtrado["GRUPO RFM"].isin(grupos)]
        if produtos:
            df_filtrado = df_filtrado[df_filtrado["PRODUTO"].isin(produtos)]
    else:
        df_filtrado = pd.DataFrame()

    # ------------------------------
    # 🎯 KPIs
    # ------------------------------
    if not df_filtrado.empty:
        total_vendas = df_filtrado["VALOR (R$)"].sum()
        clientes = df_filtrado["NOME COMPLETO"].nunique()
        ticket_medio = total_vendas / clientes if clientes > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Total de Vendas", f"R$ {total_vendas:,.2f}")
        col2.metric("👥 Clientes Únicos", clientes)
        col3.metric("🎯 Ticket Médio", f"R$ {ticket_medio:,.2f}")

    # ------------------------------
    # 📈 Gráficos Principais
    # ------------------------------
    if not df_filtrado.empty:

        # --- Vendas por Dia com Tendência ---
        st.subheader("📊 Vendas por Dia com Linha de Tendência")

        vendas_por_dia = (
            df_filtrado.groupby("DATA DE INÍCIO")["VALOR (R$)"]
            .sum()
            .reset_index()
            .sort_values("DATA DE INÍCIO")
        )
        vendas_por_dia = vendas_por_dia[vendas_por_dia["DATA DE INÍCIO"].dt.weekday != 6]
        vendas_por_dia["Tendência"] = vendas_por_dia["VALOR (R$)"].rolling(window=7, min_periods=1).mean()

        graf1 = px.line(
            vendas_por_dia,
            x="DATA DE INÍCIO",
            y=["VALOR (R$)", "Tendência"],
            title="Vendas por Dia com Linha de Tendência",
            labels={"DATA DE INÍCIO": "Data", "value": "Vendas (R$)", "variable": "Legenda"},
            markers=True
        )
        graf1.update_traces(selector=dict(name="VALOR (R$)"), line=dict(width=2, color='cyan'))
        graf1.update_traces(selector=dict(name="Tendência"), line=dict(width=3, color='orange', dash='dash'))
        graf1.update_layout(
            plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'),
            xaxis=dict(showgrid=True, gridcolor='gray'), yaxis=dict(showgrid=True, gridcolor='gray')
        )
        st.plotly_chart(graf1, use_container_width=True)

        # --- Distribuição por Grupo RFM e Produto ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Distribuição por Grupo RFM")
            graf2 = px.pie(df_filtrado, names="GRUPO RFM", title="Grupos RFM")
            graf2.update_layout(plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'))
            st.plotly_chart(graf2, use_container_width=True)

        with col2:
            st.subheader("Vendas por Produto")
            graf3 = px.bar(
                df_filtrado.groupby("PRODUTO")["VALOR (R$)"].sum().reset_index(),
                x="PRODUTO", y="VALOR (R$)", title="Total de Vendas por Produto"
            )
            graf3.update_traces(marker_color='cyan')
            graf3.update_layout(plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'))
            st.plotly_chart(graf3, use_container_width=True)

        # --- Vendas Semanais ---
        st.subheader("📈 Vendas Semanais")
        df_filtrado["SEMANA"] = df_filtrado["DATA DE INÍCIO"].dt.to_period("W").apply(lambda r: r.start_time)
        vendas_semanal = df_filtrado.groupby("SEMANA")["VALOR (R$)"].sum().reset_index()

        graf_semanal = px.line(
            vendas_semanal, x="SEMANA", y="VALOR (R$)",
            title="Vendas Semanais", markers=True
        )
        graf_semanal.update_traces(line=dict(width=2, color='blue'))
        graf_semanal.update_layout(plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'))
        st.plotly_chart(graf_semanal, use_container_width=True)

        # --- Vendas por Dia da Semana ---
        st.subheader("📊 Vendas por Dia da Semana")
        df_filtrado["DIA_DA_SEMANA"] = df_filtrado["DATA DE INÍCIO"].dt.day_name()
        vendas_dia_semana = (
            df_filtrado.groupby("DIA_DA_SEMANA")["VALOR (R$)"].sum()
            .reindex(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"])
            .reset_index()
        )
        graf_dia_semana = px.bar(
            vendas_dia_semana, x="DIA_DA_SEMANA", y="VALOR (R$)",
            title="Vendas por Dia da Semana (excluindo domingos)", text="VALOR (R$)"
        )
        graf_dia_semana.update_traces(marker_color='cyan')
        graf_dia_semana.update_layout(plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'))
        st.plotly_chart(graf_dia_semana, use_container_width=True)

        # --- Curva Acumulada ---
        st.subheader("📈 Curva de Crescimento Acumulada de Vendas")
        vendas_diarias = vendas_por_dia.copy()
        vendas_diarias["Acumulado"] = vendas_diarias["VALOR (R$)"].cumsum()
        graf_acumulado = px.line(
            vendas_diarias, x="DATA DE INÍCIO", y="Acumulado",
            title="Curva de Crescimento Acumulada de Vendas", markers=True
        )
        graf_acumulado.update_traces(line=dict(width=2, color='cyan'))
        graf_acumulado.update_layout(plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'))
        st.plotly_chart(graf_acumulado, use_container_width=True)

        # --- Comparação de Períodos Iguais ---
        st.subheader("📊 Comparação de Vendas: Período Atual vs Período Igual do Mês Anterior")

        hoje = datetime.today()
        primeiro_dia_mes_atual = hoje.replace(day=1)
        dia_atual = hoje.day
        primeiro_dia_mes_anterior = (primeiro_dia_mes_atual - timedelta(days=1)).replace(day=1)
        ultimo_dia_mes_anterior = primeiro_dia_mes_anterior.replace(day=dia_atual)

        vendas_mes_atual = df_filtrado[
            (df_filtrado["DATA DE INÍCIO"] >= primeiro_dia_mes_atual) &
            (df_filtrado["DATA DE INÍCIO"] <= hoje)
        ]["VALOR (R$)"].sum()

        vendas_mes_anterior = df_filtrado[
            (df_filtrado["DATA DE INÍCIO"] >= primeiro_dia_mes_anterior) &
            (df_filtrado["DATA DE INÍCIO"] <= ultimo_dia_mes_anterior)
        ]["VALOR (R$)"].sum()

        delta = ((vendas_mes_atual - vendas_mes_anterior) / vendas_mes_anterior) * 100 if vendas_mes_anterior != 0 else 0

        st.metric(
            label=f"Vendas até {hoje.strftime('%d/%m')} (este mês vs anterior)",
            value=f"R$ {vendas_mes_atual:,.2f}",
            delta=f"{delta:.2f}%"
        )

        comparacao = pd.DataFrame({
            "Período": [f"Mês Anterior (até {dia_atual})", f"Este Mês (até {dia_atual})"],
            "Vendas (R$)": [vendas_mes_anterior, vendas_mes_atual]
        })
        graf_comparacao = px.bar(
            comparacao, x="Período", y="Vendas (R$)", text="Vendas (R$)",
            title=f"Comparação de Vendas até o Dia {dia_atual}"
        )
        graf_comparacao.update_traces(marker_color='cyan')
        graf_comparacao.update_layout(plot_bgcolor='black', paper_bgcolor='black', font=dict(color='white'))
        st.plotly_chart(graf_comparacao, use_container_width=True)

# ======================================================
# 🔵 ABA 2 — SEGUNDA PLANILHA (para futuras análises)
# ======================================================
with aba2:
    st.subheader("📑 Segunda Planilha - Dados Complementares")
    st.dataframe(df_extra.head())

    st.info("🧠 Aqui você poderá adicionar análises específicas da segunda planilha, sem interferir na principal.")
    st.write("Exemplo: comportamento de clientes, análise de pós-venda, respostas de satisfação etc.")
