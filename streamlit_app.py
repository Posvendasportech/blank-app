# streamlit_app.py
import streamlit as st
import pandas as pd
import time
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ------------------------------
# ⚙️ Configuração da página
# ------------------------------
st.set_page_config(page_title="Dashboard de Vendas", page_icon="📊", layout="wide")

# ------------------------------
# 🔗 URLs das planilhas
# ------------------------------
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"
SHEET_URL_2 = "https://docs.google.com/spreadsheets/d/1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc/export?format=csv"

# ------------------------------
# 🧩 Funções utilitárias
# ------------------------------
@st.cache_data(ttl=60)
def carregar_dados(url: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar planilha: {e}")
        return pd.DataFrame()

def preparar_df_vendas(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # Normaliza nomes de colunas (remove espaços extras)
    df.columns = [c.strip() for c in df.columns]

    # DATA DE INÍCIO -> datetime (suporta dd/mm/yyyy)
    if "DATA DE INÍCIO" in df.columns:
        df["DATA DE INÍCIO"] = pd.to_datetime(
            df["DATA DE INÍCIO"], errors="coerce", dayfirst=True
        )

    # VALOR (R$) -> float
    if "VALOR (R$)" in df.columns:
        df["VALOR (R$)"] = (
            df["VALOR (R$)"]
            .astype(str)
            .str.replace(r"R\$\s*", "", regex=True)
            .str.replace(".", "", regex=False)  # remove separador de milhar
            .str.replace(",", ".", regex=False)  # converte decimal para ponto
        )
        df["VALOR (R$)"] = pd.to_numeric(df["VALOR (R$)"], errors="coerce").fillna(0.0)

    return df

PT_WEEK_ORDER = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]  # sem domingo
PT_WEEK_MAP = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}

# ------------------------------
# 📥 Carregamento dos dados
# ------------------------------
df_vendas_raw = carregar_dados(SHEET_URL_1)
df_extra = carregar_dados(SHEET_URL_2)
df_vendas = preparar_df_vendas(df_vendas_raw.copy())

# ------------------------------
# 🧭 Barra lateral (controles globais)
# ------------------------------
st.sidebar.title("⚙️ Controles")

if st.sidebar.button("🔄 Atualizar dados agora"):
    st.cache_data.clear()
    time.sleep(0.4)
    st.rerun()

st.sidebar.success(f"✅ Dados atualizados às {time.strftime('%H:%M:%S')}")

# ------------------------------
# 🗂️ Abas
# ------------------------------
aba1, aba2 = st.tabs(
    [
        "📊 Análises de Vendas (Planilha Principal)",
        "📑 Segunda Planilha - Análises Complementares",
    ]
)

# ======================================================
# 🟢 ABA 1 — PLANILHA PRINCIPAL
# ======================================================
with aba1:
    st.subheader("📦 Planilha Principal - Vendas")

    if df_vendas.empty:
        st.warning("Sem dados para exibir na planilha principal.")
    else:
        # ------------------------------
        # 🧩 Filtros (somente da planilha principal)
        # ------------------------------
        st.sidebar.header("🔎 Filtros (Planilha Principal)")

        # Valores únicos (com dropna para evitar NaN)
        grupos_opts = sorted(df_vendas.get("GRUPO RFM", pd.Series(dtype=str)).dropna().unique().tolist())
        produtos_opts = sorted(df_vendas.get("PRODUTO", pd.Series(dtype=str)).dropna().unique().tolist())

        grupos = st.sidebar.multiselect("Grupo RFM", grupos_opts)
        produtos = st.sidebar.multiselect("Produto", produtos_opts)

        # Aplica filtros com cópia segura
        df_filtrado = df_vendas.copy()
        if grupos:
            df_filtrado = df_filtrado[df_filtrado["GRUPO RFM"].isin(grupos)]
        if produtos:
            df_filtrado = df_filtrado[df_filtrado["PRODUTO"].isin(produtos)]

        # ------------------------------
        # 🎯 KPIs
        # ------------------------------
        if df_filtrado.empty:
            st.info("A combinação de filtros não retornou resultados.")
        else:
            total_vendas = float(df_filtrado["VALOR (R$)"].sum())
            clientes = int(df_filtrado.get("NOME COMPLETO", pd.Series(dtype=str)).nunique())
            ticket_medio = total_vendas / clientes if clientes > 0 else 0.0

            col1, col2, col3 = st.columns(3)
            col1.metric("💰 Total de Vendas", f"R$ {total_vendas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col2.metric("👥 Clientes Únicos", clientes)
            col3.metric("🎯 Ticket Médio", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            # ------------------------------
            # 📈 Gráficos Principais
            # ------------------------------
            # Filtra fora datas nulas e domingo
            base = df_filtrado[df_filtrado["DATA DE INÍCIO"].notna()].copy()
            base = base[base["DATA DE INÍCIO"].dt.weekday != 6]  # exclui domingo

            # --- Vendas por Dia + Tendência ---
            st.subheader("📊 Vendas por Dia com Linha de Tendência")
            vendas_por_dia = (
                base.groupby("DATA DE INÍCIO", as_index=False)["VALOR (R$)"].sum().sort_values("DATA DE INÍCIO")
            )
            if not vendas_por_dia.empty:
                vendas_por_dia["Tendência"] = vendas_por_dia["VALOR (R$)"].rolling(window=7, min_periods=1).mean()

                graf1 = px.line(
                    vendas_por_dia,
                    x="DATA DE INÍCIO",
                    y=["VALOR (R$)", "Tendência"],
                    title="Vendas por Dia com Linha de Tendência",
                    labels={"DATA DE INÍCIO": "Data", "value": "Vendas (R$)", "variable": "Legenda"},
                    markers=True,
                )
                graf1.update_traces(selector=dict(name="VALOR (R$)"), line=dict(width=2, color="cyan"))
                graf1.update_traces(selector=dict(name="Tendência"), line=dict(width=3, color="orange", dash="dash"))
                graf1.update_layout(
                    plot_bgcolor="black",
                    paper_bgcolor="black",
                    font=dict(color="white"),
                    xaxis=dict(showgrid=True, gridcolor="gray"),
                    yaxis=dict(showgrid=True, gridcolor="gray"),
                )
                st.plotly_chart(graf1, use_container_width=True)
            else:
                st.info("Não há dados de vendas diárias após aplicar filtros.")

            # --- Distribuição por Grupo RFM e Produto ---
            colg1, colg2 = st.columns(2)

            with colg1:
                st.subheader("Distribuição por Grupo RFM")
                if "GRUPO RFM" in df_filtrado.columns and not df_filtrado["GRUPO RFM"].dropna().empty:
                    graf2 = px.pie(df_filtrado, names="GRUPO RFM", title="Grupos RFM")
                    graf2.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                    st.plotly_chart(graf2, use_container_width=True)
                else:
                    st.info("Sem dados de GRUPO RFM para exibir.")

            with colg2:
                st.subheader("Vendas por Produto")
                if "PRODUTO" in df_filtrado.columns:
                    vendas_prod = (
                        df_filtrado.groupby("PRODUTO", as_index=False)["VALOR (R$)"].sum().sort_values("VALOR (R$)", ascending=False)
                    )
                    if not vendas_prod.empty:
                        graf3 = px.bar(
                            vendas_prod,
                            x="PRODUTO",
                            y="VALOR (R$)",
                            title="Total de Vendas por Produto",
                            text="VALOR (R$)",
                        )
                        graf3.update_traces(marker_color="cyan", texttemplate="%{text:.2s}")
                        graf3.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                        st.plotly_chart(graf3, use_container_width=True)
                    else:
                        st.info("Sem dados de produtos após os filtros.")
                else:
                    st.info("Coluna 'PRODUTO' não encontrada na planilha.")

            # --- Vendas Semanais ---
            st.subheader("📈 Vendas Semanais")
            if not base.empty:
                base_sem = base.assign(SEMANA=base["DATA DE INÍCIO"].dt.to_period("W").apply(lambda r: r.start_time))
                vendas_semanal = base_sem.groupby("SEMANA", as_index=False)["VALOR (R$)"].sum().sort_values("SEMANA")
                graf_semanal = px.line(
                    vendas_semanal, x="SEMANA", y="VALOR (R$)", title="Vendas Semanais", markers=True
                )
                graf_semanal.update_traces(line=dict(width=2, color="blue"))
                graf_semanal.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                st.plotly_chart(graf_semanal, use_container_width=True)
            else:
                st.info("Sem dados semanais para exibir.")

            # --- Vendas por Dia da Semana (sem domingo) ---
            st.subheader("📊 Vendas por Dia da Semana (exclui domingo)")
            if not base.empty:
                base_dia = base.assign(DIA=base["DATA DE INÍCIO"].dt.dayofweek.map(PT_WEEK_MAP))
                vendas_dia_semana = (
                    base_dia.groupby("DIA", as_index=False)["VALOR (R$)"].sum()
                )
                # Reordenar e remover domingo se existir
                vendas_dia_semana = vendas_dia_semana[vendas_dia_semana["DIA"].isin(PT_WEEK_ORDER)]
                vendas_dia_semana["DIA"] = pd.Categorical(vendas_dia_semana["DIA"], categories=PT_WEEK_ORDER, ordered=True)
                vendas_dia_semana = vendas_dia_semana.sort_values("DIA")

                graf_dia_semana = px.bar(
                    vendas_dia_semana,
                    x="DIA",
                    y="VALOR (R$)",
                    title="Vendas por Dia da Semana",
                    text="VALOR (R$)",
                )
                graf_dia_semana.update_traces(marker_color="cyan")
                graf_dia_semana.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                st.plotly_chart(graf_dia_semana, use_container_width=True)
            else:
                st.info("Sem dados por dia da semana para exibir.")

            # --- Curva Acumulada ---
            st.subheader("📈 Curva de Crescimento Acumulada de Vendas")
            if not vendas_por_dia.empty:
                vendas_acum = vendas_por_dia.copy()
                vendas_acum["Acumulado"] = vendas_acum["VALOR (R$)"].cumsum()
                graf_acumulado = px.line(
                    vendas_acum,
                    x="DATA DE INÍCIO",
                    y="Acumulado",
                    title="Curva de Crescimento Acumulada de Vendas",
                    markers=True,
                )
                graf_acumulado.update_traces(line=dict(width=2, color="cyan"))
                graf_acumulado.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                st.plotly_chart(graf_acumulado, use_container_width=True)
            else:
                st.info("Sem dados suficientes para curva acumulada.")

            # --- Comparação de Períodos Iguais ---
            st.subheader("📊 Comparação: Período Atual vs Mesmo Intervalo do Mês Anterior")
            hoje = datetime.today()
            primeiro_dia_mes_atual = hoje.replace(day=1)
            dia_atual = hoje.day
            primeiro_dia_mes_anterior = (primeiro_dia_mes_atual - timedelta(days=1)).replace(day=1)
            # Limita o mês anterior ao mesmo dia do mês atual (ou ao último dia existente)
            try:
                ultimo_dia_mes_anterior = primeiro_dia_mes_anterior.replace(day=dia_atual)
            except ValueError:
                # Caso o mês anterior não tenha esse dia (ex.: dia 31)
                ultimo_dia_mes_anterior = (primeiro_dia_mes_atual - timedelta(days=1))

            vendas_mes_atual = base[
                (base["DATA DE INÍCIO"] >= primeiro_dia_mes_atual) & (base["DATA DE INÍCIO"] <= hoje)
            ]["VALOR (R$)"].sum()

            vendas_mes_anterior = base[
                (base["DATA DE INÍCIO"] >= primeiro_dia_mes_anterior) & (base["DATA DE INÍCIO"] <= ultimo_dia_mes_anterior)
            ]["VALOR (R$)"].sum()

            if vendas_mes_anterior != 0:
                delta = ((vendas_mes_atual - vendas_mes_anterior) / vendas_mes_anterior) * 100
            else:
                delta = 0.0

            st.metric(
                label=f"Vendas até {hoje.strftime('%d/%m')} (este mês vs anterior)",
                value=f"R$ {vendas_mes_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                delta=f"{delta:.2f}%"
            )

            comparacao = pd.DataFrame(
                {
                    "Período": [f"Mês Anterior (até {dia_atual})", f"Este Mês (até {dia_atual})"],
                    "Vendas (R$)": [vendas_mes_anterior, vendas_mes_atual],
                }
            )
            graf_comparacao = px.bar(
                comparacao,
                x="Período",
                y="Vendas (R$)",
                text="Vendas (R$)",
                title=f"Comparação de Vendas até o Dia {dia_atual}",
            )
            graf_comparacao.update_traces(marker_color="cyan")
            graf_comparacao.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf_comparacao, use_container_width=True)

# ======================================================
# 🔵 ABA 2 — SEGUNDA PLANILHA (somente nela mostramos a tabela da segunda)
# ======================================================
with aba2:
    st.subheader("📑 Segunda Planilha - Dados Complementares")

    if df_extra.empty:
        st.info("Ainda não há dados na segunda planilha para exibir.")
    else:
        st.dataframe(df_extra.head(50), use_container_width=True)

    st.info("🧠 Espaço reservado para análises específicas da segunda planilha (pós-venda, NPS, satisfação, etc.).")


    # --- Análise de todos os clientes (por Grupo RFM) ---
    st.subheader("👥 Clientes por Grupo (Quantidade e Receita)")

    # Vamos usar a planilha principal (df_vendas) porque é ela que tem GRUPO RFM e VALOR (R$)
    base_clientes = df_vendas.copy()

    colunas_necessarias = ["GRUPO RFM", "NOME COMPLETO", "VALOR (R$)"]
    faltantes = [c for c in colunas_necessarias if c not in base_clientes.columns]

    if faltantes:
        st.warning(
            f"Não foi possível gerar o gráfico. Colunas ausentes na planilha principal: {', '.join(faltantes)}"
        )
    else:
        # Agrupamento: clientes únicos e receita por grupo
        grp = (
            base_clientes.dropna(subset=["GRUPO RFM"])
            .groupby("GRUPO RFM", as_index=False)
            .agg(Quantidade=("NOME COMPLETO", "nunique"),
                 Receita=("VALOR (R$)", "sum"))
            .sort_values("Receita", ascending=False)
        )

        # Gráfico único com dois eixos Y (clientes e receita)
        fig = go.Figure()
        fig.add_bar(
            x=grp["GRUPO RFM"],
            y=grp["Quantidade"],
            name="Quantidade de clientes",
        )
        fig.add_bar(
            x=grp["GRUPO RFM"],
            y=grp["Receita"],
            name="Receita (R$)",
            yaxis="y2",
        )

        fig.update_layout(
            title="Quantidade de Clientes e Receita por Grupo",
            xaxis_title="Grupo RFM",
            yaxis=dict(title="Qtd. de clientes", showgrid=True, gridcolor="gray"),
            yaxis2=dict(title="Receita (R$)", overlaying="y", side="right", showgrid=False),
            barmode="group",
            plot_bgcolor="black",
            paper_bgcolor="black",
            font=dict(color="white"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        st.plotly_chart(fig, use_container_width=True)
        st.caption("Obs.: Receita calculada a partir de 'VALOR (R$)' e clientes únicos por 'NOME COMPLETO'.")

