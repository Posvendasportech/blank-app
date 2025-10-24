# streamlit_app.py
import streamlit as st
import pandas as pd
import time
import plotly.express as px
from datetime import datetime, timedelta
from urllib.parse import quote
import re

# ------------------------------
# ⚙️ Configuração da página
# ------------------------------
st.set_page_config(page_title="Dashboard de Vendas", page_icon="📊", layout="wide")

# ------------------------------
# 🔗 IDs / padrões das planilhas
# ------------------------------
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"
SHEET2_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
DEFAULT_SHEET2_SHEETNAME = "Total"

# ======================================================
# 🧩 Funções utilitárias
# ======================================================
@st.cache_data(ttl=120)
def carregar_csv(url: str) -> pd.DataFrame:
    df = pd.read_csv(
        url,
        sep=",",
        engine="python",
        on_bad_lines="skip",
        encoding="utf-8",
        na_values=["", "NA", "NaN", None],
    )

    unnamed = sum(str(c).startswith("Unnamed") for c in df.columns)
    if unnamed > len(df.columns) // 2:
        _raw = pd.read_csv(url, sep=",", header=None)
        new_header = _raw.iloc[0]
        df = _raw[1:]
        df.columns = new_header
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _col_by_letter(df: pd.DataFrame, letter: str) -> str | None:
    letter = (letter or "").strip().upper()
    if not letter:
        return None
    idx = ord(letter) - ord("A")
    if 0 <= idx < len(df.columns):
        return df.columns[idx]
    return None


def _to_float_brl(series: pd.Series) -> pd.Series:
    """Converte valores mistos BRL/US/EU corretamente."""
    def parse_one(x):
        s = str(x).strip().replace("\u00A0", " ")
        s = re.sub(r"[Rr]\$\s*", "", s)
        s = re.sub(r"[^\d,.\-]", "", s)

        if s.count(",") > 0 and s.count(".") > 0:
            s = s.replace(".", "").replace(",", ".")  # BR
        elif s.count(",") > 0:
            left, right = s.rsplit(",", 1)
            if right.isdigit() and 1 <= len(right) <= 2:
                s = left.replace(",", "") + "." + right
            else:
                s = s.replace(",", "")
        elif s.count(".") > 0:
            left, right = s.rsplit(".", 1)
            if right.isdigit() and 1 <= len(right) <= 2:
                s = left.replace(".", "") + "." + right
            else:
                s = s.replace(".", "")
        try:
            return float(s)
        except:
            return 0.0
    return series.apply(parse_one)


def preparar_df_vendas(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "DATA DE INÍCIO" in df.columns:
        df["DATA DE INÍCIO"] = pd.to_datetime(df["DATA DE INÍCIO"], errors="coerce", dayfirst=True)
    if "VALOR (R$)" in df.columns:
        df["VALOR (R$)"] = _to_float_brl(df["VALOR (R$)"])
    return df


def preparar_df_historico_resumo(df: pd.DataFrame, valor_letter="D", compras_letter="F") -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    nome_col = next((c for c in ["NOME", "CLIENTE", "NOME COMPLETO"] if c in df.columns), df.columns[0])
    email_col = next((c for c in ["E-MAIL", "EMAIL"] if c in df.columns), None)

    df["CLIENTE_NOME"] = df[nome_col].astype(str)
    df["CLIENTE_EMAIL"] = df[email_col].astype(str).str.lower() if email_col else ""
    df["CLIENTE_ID"] = df["CLIENTE_EMAIL"].where(df["CLIENTE_EMAIL"] != "", df["CLIENTE_NOME"])

    col_val = _col_by_letter(df, valor_letter)
    col_cmp = _col_by_letter(df, compras_letter)

    df["VALOR_PAD"] = _to_float_brl(df[col_val]) if col_val else 0.0
    df["N_COMPRAS"] = pd.to_numeric(df[col_cmp], errors="coerce").fillna(0).astype(int) if col_cmp else 0
    return df

# ======================================================
# 📥 Carregamento das planilhas
# ======================================================
with st.spinner("Carregando Planilha 1..."):
    df_vendas_raw = carregar_csv(SHEET_URL_1)
df_vendas = preparar_df_vendas(df_vendas_raw)

st.sidebar.title("⚙️ Controles")
sheet2_sheetname = st.sidebar.text_input("📄 Aba da Planilha 2", DEFAULT_SHEET2_SHEETNAME)
valor_letter = st.sidebar.text_input("Letra da coluna de Valor", "D")
compras_letter = st.sidebar.text_input("Letra da coluna de Compras", "F")

SHEET_URL_2 = f"https://docs.google.com/spreadsheets/d/{SHEET2_ID}/gviz/tq?tqx=out:csv&sheet={quote(sheet2_sheetname)}"

if st.sidebar.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

with st.spinner("Carregando Planilha 2..."):
    try:
        df_extra_raw = carregar_csv(SHEET_URL_2)
    except Exception as e:
        st.error(f"Erro ao carregar planilha: {e}")
        df_extra_raw = pd.DataFrame()

df_historico = preparar_df_historico_resumo(df_extra_raw, valor_letter, compras_letter)

ok1 = "✅" if not df_vendas.empty else "⚠️"
ok2 = "✅" if not df_historico.empty else "⚠️"
st.markdown(f"**Planilha 1:** {ok1} | **Planilha 2:** {ok2}")

aba1, aba2 = st.tabs(["📊 Colaborador", "📑 Histórico de Clientes"])

# ======================================================
# 🟢 ABA 1
# ======================================================
with aba1:
    st.subheader("📦 Vendas do Colaborador")
    if df_vendas.empty:
        st.warning("Sem dados.")
    else:
        total = df_vendas["VALOR (R$)"].sum()
        st.metric("💰 Total de vendas", f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

# ======================================================
# 🔵 ABA 2
# ======================================================
with aba2:
    st.subheader("📑 Histórico Geral de Clientes")
    if df_historico.empty:
        st.warning("Sem dados de histórico.")
    else:
        receita_total = df_historico["VALOR_PAD"].sum()
        total_compras = df_historico["N_COMPRAS"].sum()
        clientes = df_historico["CLIENTE_ID"].nunique()
        aov = receita_total / total_compras if total_compras > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Receita total", f"R$ {receita_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c2.metric("🧑‍🤝‍🧑 Clientes", clientes)
        c3.metric("🛒 Compras", total_compras)
        c4.metric("🎯 Ticket médio", f"R$ {aov:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        st.subheader("🏆 Top Clientes por Valor Gasto")
        top = df_historico.sort_values("VALOR_PAD", ascending=False).head(20)
        graf = px.bar(top, x="CLIENTE_NOME", y="VALOR_PAD", text="VALOR_PAD", title="Top 20 Clientes")
        graf.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
        graf.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
        st.plotly_chart(graf, use_container_width=True)

        st.dataframe(df_historico.head(50), use_container_width=True)
