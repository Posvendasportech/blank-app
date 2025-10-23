import streamlit as st
import pandas as pd
import time
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# =========================================
# ⚙️ Configurações básicas
# =========================================
st.set_page_config(page_title="Pós-Vendas • Painel", layout="wide")

TZ = pytz.timezone("America/Sao_Paulo")

# ------------------------------
# 🔗 URLs das planilhas
# ------------------------------
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"
SHEET_URL_2 = "https://docs.google.com/spreadsheets/d/1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc/export?format=csv"

# =========================================
# 🛠️ Utilitários
# =========================================
def format_brl(valor: float) -> str:
    try:
        s = f"{valor:,.2f}"              # 1,234,567.89
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except Exception:
        return "R$ 0,00"

def parse_brl_series(s: pd.Series) -> pd.Series:
    # Remove "R$", espaços, pontos de milhar e troca vírgula por ponto
    return (
        s.astype(str)
         .str.replace(r"R\$\s*", "", regex=True)
         .str.replace(".", "", regex=False)
         .str.replace(",", ".", regex=False)
         .str.strip()
         .replace({"": None})
         .astype(float)
    )

def ensure_cols(df: pd.DataFrame, cols: list[str]) -> bool:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.warning(f"Colunas ausentes na planilha principal: {', '.join(missing)}")
        return False
    return True

# =========================================
# 📥 Carregamento com cache
# =========================================
@st.cache_data(ttl=60)
def carregar_csv(url: str) -> pd.DataFrame:
    try:
        # dayfirst=True pq muitas planilhas BR usam dd/mm/yyyy
        df = pd.read_csv(url, dayfirst=True)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar planilha: {e}")
        return pd.DataFrame()

df_vendas_raw = carregar_csv(SHEET_URL_1)
df_extra = carregar_csv(SHEET_URL_2)

# =========================================
# 🧭 Sidebar
# =========================================
st.sidebar.title("⚙️ Controles")
if st.sidebar.button("🔄 Atualizar dados agora", use_container_width=True):
    st.cache_data.clear()
    time.sleep(0.3)
    st.rerun()

st.sidebar.success(f"✅ Dados atualizados às {time.strftime('%H:%M:%S')}")

# =========================================
# 🧹 Limpeza e preparação dos dados
# =========================================
df_vendas = df_vendas_raw.copy()

if not df_vendas.empty:
    # Normaliza datas
    if "DATA DE INÍCIO" in df_vendas.columns:
        df_vendas["DATA DE INÍCIO"] = pd.to_datetime(
            df_vendas["DATA DE INÍCIO"], errors="coerce", dayfirst=True
        )
    # Normaliza moeda
    if "VALOR (R$)" in df_vendas.columns:
        df_vendas["VALOR (R$)"] = parse_brl_series(df_vendas["VALOR (R$)"])

# =========================================
# 🗂️ Abas
# =========================================
aba1, aba2 = st.tabs(
    ["📊 Análises de Vendas (Planilha Principal)", "📑 Segunda Planilha - Complementar"]
)

# ======================================================
# 🟢 ABA 1 — PLANILHA PRINCIPAL
# ======================================================
with aba1:
    st.subheader("📦 Planilha Principal - Vendas")

    if df_vendas.empty:
        st.info("Sem dados na planilha principal.")
        st.stop()

    st.dataframe(df_vendas.head(), use_container_width=True, height=240)

    # Checa colunas essenciais
    required_cols = ["DATA DE INÍCIO", "VALOR (R$)", "NOME COMPLETO", "PRODUTO", "GRUPO RFM"]
    if not ensure_cols(df_vendas, required_cols):
        st.stop()

    # ------------------------------
    # 🧩 Filtros
    # ------------------------------
    st.sidebar.header("Filtros")

    # Período padrão: últimos 60 dias
    hoje = pd.Timestamp.now(TZ).normalize()
    default_inicio = (hoje - pd.Timedelta(days=60)).date()
    default_fim = hoje.date()

    periodo = st.sidebar.date_input(
        "Período (início e fim)",
        value=(default_inicio, default_fim)
    )

    if isinstance(periodo, tuple) and len(periodo) == 2:
        dt_ini = pd.Timestamp(periodo[0], tz=TZ)
        dt_fim = pd.Timestamp(periodo[1], tz=TZ) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    else:
        dt_ini = pd.Timestamp(default_inicio, tz=TZ)
        dt_fim = pd.Timestamp(default_fim, tz=TZ) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    grupos = st.sidebar.multiselect(
        "Grupo RFM", sorted(df_vendas["GRUPO RFM"].dropna().unique().tolist())
    )
    produtos = st.sidebar.multiselect(
        "Produto", sorted(df_vendas["PRODUTO"].dropna().unique().tolist())
    )

    df_filtrado = df_vendas.copy()
    df_filtrado = df_filtrado[
        (df_filtrado["DATA DE INÍCIO"] >= dt_ini.tz_localize(None)) &
        (df_filtrado["DATA DE INÍCIO"] <= dt_fim.tz_localize(None))
    ]

    if grupos:
        df_filtrado = df_filtrado[df_filtrado["GRUPO RFM"].isin(grupos)]
    if produtos:
        df_filtrado = df_filtrado[df_filtrado["PRODUTO"].isin(produtos)]

    if df_filtrado.empty:
        st.info("Nenhum registro encontrado para os filtros aplicados.")
        st.stop()

    # ------------------------------
    # 🎯 KPIs
    # ------------------------------
    total_vendas = float(df_filtrado["VALOR (R$)"].sum())
    clientes = int(df_filtrado["NOME COMPLETO"].nunique())
    ticket_medio = total_vendas / clientes if clientes > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Total de Vendas", format_brl(total_vendas))
    c2.metric("👥 Clientes Únicos", clientes)
    c3.metric("🎯 Ticket Médio", format_brl(ticket_medio))

    # ------------------------------
    # 📈 Gráficos
    # ------------------------------
    # (a) Vendas por Dia com Tendência (exclui domingos)
    st.subheader("📊 Vendas por Dia com Linha de Tendência")
    vendas_por_dia = (
        df_filtrado.groupby(df_filtrado["DATA DE INÍC]()
