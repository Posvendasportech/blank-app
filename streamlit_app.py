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

# ==============================
# 🧩 Funções utilitárias
# ==============================
@st.cache_data(ttl=120)
def carregar_csv(url: str) -> pd.DataFrame:
    """Carrega CSV remoto e tenta corrigir cabeçalho 'torto' (muitos 'Unnamed')."""
    df = pd.read_csv(
        url,
        sep=",",
        engine="python",
        on_bad_lines="skip",
        encoding="utf-8",
        na_values=["", "NA", "NaN", None],
    )

    def _fix_header(_df: pd.DataFrame) -> pd.DataFrame:
        unnamed = sum(str(c).startswith("Unnamed") for c in _df.columns)
        if unnamed <= len(_df.columns) // 2:
            return _df  # cabeçalho parece OK

        _raw = pd.read_csv(url, sep=",", engine="python", on_bad_lines="skip",
                           encoding="utf-8", header=None)
        best_idx, best_score = 0, -1
        limit = min(10, len(_raw))
        for i in range(limit):
            row = _raw.iloc[i].astype(str).fillna("")
            score = sum(any(ch.isalpha() for ch in str(x)) for x in row)
            if score > best_score:
                best_score, best_idx = score, i

        new_header = _raw.iloc[best_idx].astype(str).str.strip().tolist()
        _raw = _raw.iloc[best_idx + 1:].reset_index(drop=True)
        _raw.columns = [c if c else f"col_{i}" for i, c in enumerate(new_header)]
        return _raw

    if not df.empty:
        df = _fix_header(df)
        df.columns = [str(c).strip() for c in df.columns]
    return df


def _dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Garante nomes de colunas únicos; adiciona _2, _3, ... nas duplicadas."""
    if df is None:
        return pd.DataFrame()
    if not isinstance(df, pd.DataFrame):
        try:
            df = pd.DataFrame(df)
        except Exception:
            return pd.DataFrame()
    if df.empty:
        return df
    new_cols, seen = [], {}
    for c in df.columns:
        base = str(c)
        if base not in seen:
            seen[base] = 1
            new_cols.append(base)
        else:
            k = seen[base] + 1
            cand = f"{base}_{k}"
            while cand in seen:
                k += 1
                cand = f"{base}_{k}"
            seen[base] = k
            seen[cand] = 1
            new_cols.append(cand)
    out = df.copy()
    out.columns = new_cols
    return out


def _as_series_safe(df: pd.DataFrame, col_label) -> pd.Series:
    """Sempre retorna uma Series, mesmo se houver colunas duplicadas (df[col] -> DataFrame)."""
    if df is None or col_label is None or col_label not in df.columns:
        return pd.Series([pd.NA] * (len(df) if df is not None else 0))
    obj = df[col_label]
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]  # pega a 1ª ocorrência
    return obj


# Mapa de letra (A..Z, AA..AZ, ...) -> índice de coluna
ABC = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
def _letter_to_index(letter: str) -> int | None:
    if not letter:
        return None
    letter = str(letter).strip().upper()
    idx = 0
    for ch in letter:
        if ch not in ABC:
            return None
        idx = idx * 26 + (ABC.index(ch) + 1)
    return idx - 1 if idx > 0 else None

def _col_by_letter(df: pd.DataFrame, letter: str) -> str | None:
    j = _letter_to_index(letter)
    if j is None:
        return None
    if 0 <= j < len(df.columns):
        return df.columns[j]
    return None


def preparar_df_vendas(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara a planilha do colaborador: datas e valores."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # DATA
    if "DATA DE INÍCIO" in df.columns:
        df["DATA DE INÍCIO"] = pd.to_datetime(df["DATA DE INÍCIO"], errors="coerce", dayfirst=True)

    # VALOR
    if "VALOR (R$)" in df.columns:
        s = df["VALOR (R$)"].astype(str)
        s = s.str.replace("\u00A0", " ", regex=False)
        s = s.str.replace(r"[Rr]\$\s*", "", regex=True)
        s = s.str.replace(".", "", regex=False)   # milhar
        s = s.str.replace(",", ".", regex=False)  # decimal
        df["VALOR (R$)"] = pd.to_numeric(s, errors="coerce").fillna(0.0)

    return df


def preparar_df_historico(
    df: pd.DataFrame,
    valor_col_name: str | None = None,
    date_col_name: str | None = None,
) -> pd.DataFrame:
    """Prepara o histórico: converte valor em número, data em datetime e cria chaves de cliente."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = _dedupe_columns(df.copy())
    df.columns = [str(c).strip() for c in df.columns]

    # --- DATA_REF (por nome ou por conteúdo)
    if date_col_name and date_col_name in df.columns:
        date_col = date_col_name
    else:
        date_cols_hint = ["DATA", "DATA DA COMPRA", "DATA DE INÍCIO", "DATA VENDA", "DATA/HORA", "DATA HORA"]
        date_col = next((c for c in date_cols_hint if c in df.columns), None)
        if date_col is None:
            best, best_rate = None, 0.0
            sample = df.head(200)
            for c in df.columns:
                s = _as_series_safe(sample, c)
                rate = pd.to_datetime(s, errors="coerce", dayfirst=True).notna().mean()
                if rate > best_rate:
                    best, best_rate = c, rate
            date_col = best if best_rate >= 0.4 else None

    if date_col:
        df["DATA_REF"] = pd.to_datetime(_as_series_safe(df, date_col), errors="coerce", dayfirst=True)
    else:
        df["DATA_REF"] = pd.Series(pd.NaT, index=df.index)

    # --- VALOR_PAD
    def to_float(series: pd.Series) -> pd.Series:
        s = series.astype(str)
        s = s.str.replace("\u00A0", " ", regex=False)          # NBSP
        s = s.str.replace(r"[Rr]\$\s*", "", regex=True)        # remove R$
        s = s.str.replace(" ", "", regex=False)                # remove espaços
        # Heurística: vírgula como decimal?
        comma_decimal = ((s.str.contains(",")) & (~s.str.contains(r"\d,\d{3,}", regex=True))).mean() >= 0.5
        if comma_decimal:
            s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        else:
            s = s.str.replace(",", "", regex=False)
        return pd.to_numeric(s, errors="coerce").fillna(0.0)

    if valor_col_name and valor_col_name in df.columns:
        chosen_val_col = valor_col_name
    else:
        # heurística: escolhe a coluna que mais "parece" dinheiro
        blacklist = {"CPF","ID","ID_CLIENTE","TELEFONE","CELULAR","CEP","QUANTIDADE","QTD"}
        money_re = re.compile(r"^\s*(R\$\s*)?[\d\.\,]+(\s*)$")
        best, best_hits = None, -1
        sample = df.head(200)
        for c in df.columns:
            if any(b in str(c).upper() for b in blacklist):
                continue
            s = _as_series_safe(sample, c).astype(str)
            hits = s.str.match(money_re).sum()
            if hits > best_hits:
                best, best_hits = c, hits
        chosen_val_col = best

    df["VALOR_PAD"] = to_float(_as_series_safe(df, chosen_val_col)) if chosen_val_col in df.columns else 0.0

    # --- CHAVES DE CLIENTE
    nome_col  = next((c for c in ["NOME COMPLETO","CLIENTE","NOME","Nome"] if c in df.columns), None)
    email_col = next((c for c in ["E-MAIL","EMAIL","Email","e-mail"] if c in df.columns), None)
    id_col    = next((c for c in ["CPF","ID_CLIENTE","ID"] if c in df.columns), None)

    df["CLIENTE_NOME"]  = _as_series_safe(df, nome_col).astype(str).str.strip() if nome_col else ""
    df["CLIENTE_EMAIL"] = _as_series_safe(df, email_col).astype(str).str.strip().str.lower() if email_col else ""
    if id_col:
        df["CLIENTE_ID"] = _as_series_safe(df, id_col).astype(str).str.strip()
    else:
        df["CLIENTE_ID"] = df["CLIENTE_EMAIL"].where(df["CLIENTE_EMAIL"] != "", df["CLIENTE_NOME"])

    return df

# ==============================
# Constantes auxiliares
# ==============================
PT_WEEK_ORDER = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
PT_WEEK_MAP = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}

# ------------------------------
# 📥 Carregamento da PLANILHA 1
# ------------------------------
with st.spinner("Carregando Planilha 1 (colaborador)…"):
    df_vendas_raw = carregar_csv(SHEET_URL_1)
df_vendas_raw = _dedupe_columns(df_vendas_raw)
df_vendas = preparar_df_vendas(df_vendas_raw.copy())

# ------------------------------
# 🧭 Sidebar / Controles
# ------------------------------
st.sidebar.title("⚙️ Controles")

sheet2_sheetname = st.sidebar.text_input(
    "📄 Nome da aba (Planilha 2)",
    value=DEFAULT_SHEET2_SHEETNAME,
    help="Ex.: Total (tem que ser exatamente como aparece na guia do Google Sheets)",
)
SHEET_URL_2 = f"https://docs.google.com/spreadsheets/d/{SHEET2_ID}/gviz/tq?tqx=out:csv&sheet={quote(sheet2_sheetname)}"

if st.sidebar.button("🔄 Atualizar dados agora"):
    st.cache_data.clear()
    time.sleep(0.3)
    st.rerun()
st.sidebar.success(f"✅ Dados atualizados às {time.strftime('%H:%M:%S')}")

# Identificação do colaborador (rótulo)
colab_detectado = None
if not df_vendas.empty:
    for c in ["COLABORADOR", "VENDEDOR", "RESPONSÁVEL"]:
        if c in df_vendas.columns and not df_vendas[c].dropna().empty:
            vals = df_vendas[c].dropna().astype(str).unique().tolist()
            if len(vals) == 1:
                colab_detectado = vals[0]
            break
colaborador = st.sidebar.text_input("👤 Nome do colaborador (rótulo do relatório)", value=colab_detectado or "")

# ------------------------------
# 📥 Carregamento da PLANILHA 2
# ------------------------------
with st.spinner("Carregando Planilha 2 (histórico)…"):
    try:
        df_extra_raw = carregar_csv(SHEET_URL_2)
    except Exception:
        df_extra_raw = pd.DataFrame()
df_extra_raw = _dedupe_columns(df_extra_raw)

# ====== Mapeamento manual (seguro) da Planilha 2 ======
with st.sidebar.expander("🧩 Mapear colunas da Planilha 2", expanded=False):
    cols = df_extra_raw.columns.tolist() if not df_extra_raw.empty else []
    options = cols if cols else [""]

    sugestao_val = next((c for c in ["VALOR (R$)", "VALOR", "TOTAL (R$)", "TOTAL", "PREÇO", "PRECO"] if c in cols), None)
    sugestao_data = next((c for c in ["DATA", "DATA DA COMPRA", "DATA DE INÍCIO", "DATA VENDA", "DATA/HORA", "DATA HORA"] if c in cols), None)

    valor_col_name = st.selectbox("Coluna de VALOR", options=options,
                                  index=(options.index(sugestao_val) if (sugestao_val in options) else 0))
    date_col_name  = st.selectbox("Coluna de DATA",  options=options,
                                  index=(options.index(sugestao_data) if (sugestao_data in options) else 0))

    # (Opcional) Forçar coluna de valor por letra (ex.: D)
    letter = st.text_input("Letra da coluna de VALOR (opcional, ex.: D)", value="")
    if letter and not df_extra_raw.empty:
        forced_name = _col_by_letter(df_extra_raw, letter)
        if forced_name:
            valor_col_name = forced_name
            st.caption(f"Usando coluna de VALOR pela letra **{letter.upper()}** → **{forced_name}**")

    if valor_col_name == "": valor_col_name = None
    if date_col_name == "":  date_col_name  = None

df_historico = preparar_df_historico(df_extra_raw.copy(),
                                     valor_col_name=valor_col_name,
                                     date_col_name=date_col_name)

# Status rápido no topo
ok1 = "✅" if isinstance(df_vendas, pd.DataFrame) and not df_vendas.empty else "⚠️"
ok2 = "✅" if isinstance(df_historico, pd.DataFrame) and not df_historico.empty else "⚠️"
st.markdown(f"**Planilha 1 (Colaborador):** {ok1}  |  **Planilha 2 (Histórico):** {ok2}")

# ------------------------------
# 🗂️ Abas
# ------------------------------
aba1, aba2 = st.tabs([
    "📊 Análises do Colaborador (Planilha 1)",
    "📑 Histórico Geral de Clientes (Planilha 2)",
])

# ======================================================
# 🟢 ABA 1 — PLANILHA 1 (Colaborador)
# ======================================================
with aba1:
    titulo_colab = f"📦 Vendas do Colaborador {f'— {colaborador}' if colaborador else ''}".strip()
    st.subheader(titulo_colab)

    if df_vendas.empty:
        st.warning("Sem dados para exibir na planilha do colaborador.")
    else:
        # KPIs principais
        total_colab = float(df_vendas.get("VALOR (R$)", pd.Series(dtype=float)).sum())
        clientes_colab = int(df_vendas.get("NOME COMPLETO", pd.Series(dtype=str)).nunique())
        ticket_medio_colab = total_colab / clientes_colab if clientes_colab > 0 else 0.0

        col1, col2, col3 = st.columns(3)
        brl = lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        col1.metric("💰 Vendas do Colaborador", brl(total_colab))
        col2.metric("👥 Clientes Únicos", clientes_colab)
        col3.metric("🎯 Ticket Médio", brl(ticket_medio_colab))

        # Série temporal (sem domingo)
        base = df_vendas[df_vendas.get("DATA DE INÍCIO").notna()].copy() if "DATA DE INÍCIO" in df_vendas.columns else pd.DataFrame()
        if not base.empty:
            base = base[base["DATA DE INÍCIO"].dt.weekday != 6]

        st.subheader("📊 Vendas por Dia com Linha de Tendência")
        vendas_por_dia = (
            base.groupby("DATA DE INÍCIO", as_index=False)["VALOR (R$)"].sum().sort_values("DATA DE INÍCIO")
        ) if not base.empty else pd.DataFrame()
        if not vendas_por_dia.empty:
            vendas_por_dia["Tendência"] = vendas_por_dia["VALOR (R$)"].rolling(window=7, min_periods=1).mean()
            graf1 = px.line(
                vendas_por_dia, x="DATA DE INÍCIO", y=["VALOR (R$)", "Tendência"],
                labels={"DATA DE INÍCIO": "Data", "value": "Vendas (R$)", "variable": "Legenda"},
                markers=True,
            )
            st.plotly_chart(graf1, use_container_width=True)
        else:
            st.info("Sem dados de vendas diárias.")

# ======================================================
# 🔵 ABA 2 — HISTÓRICO GERAL (Clientes)
# ======================================================
with aba2:
    st.subheader("📑 Histórico Geral de Clientes")

    if df_historico.empty:
        st.info("Ainda não há dados na planilha de histórico para exibir.")
    else:
        # Filtros
        min_data = pd.to_datetime(df_historico["DATA_REF"]).min()
        max_data = pd.to_datetime(df_historico["DATA_REF"]).max()
        if pd.isna(min_data) or pd.isna(max_data):
            min_data = datetime.today() - timedelta(days=180)
            max_data = datetime.today()

        periodo = st.date_input("Período (Histórico)",
                                value=(min_data.date(), max_data.date()))

        prod_col = next((c for c in ["PRODUTO", "ITEM", "SKU", "DESCRIÇÃO", "DESCRICAO"]
                         if c in df_historico.columns), None)
        prod_opts = sorted(df_historico[prod_col].dropna().unique().tolist()) if prod_col else []
        produtos_hist = st.multiselect("Produto (Histórico)", prod_opts) if prod_col else []

        df_hist_filt = df_historico.copy()
        if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
            di, df_ = periodo
            di = datetime.combine(di, datetime.min.time())
            df_ = datetime.combine(df_, datetime.max.time())
            df_hist_filt = df_hist_filt[(df_hist_filt["DATA_REF"] >= di) & (df_hist_filt["DATA_REF"] <= df_)]
        if prod_col and produtos_hist:
            df_hist_filt = df_hist_filt[df_hist_filt[prod_col].isin(produtos_hist)]

        # KPIs gerais
        total_geral = float(df_hist_filt["VALOR_PAD"].sum())
        clientes_geral = int(df_hist_filt["CLIENTE_ID"].nunique())
        pedidos_geral = int(df_hist_filt.shape[0])
        aov = total_geral / pedidos_geral if pedidos_geral > 0 else 0.0

        brl = lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 Receita (período)", brl(total_geral))
        k2.metric("🧑‍🤝‍🧑 Clientes únicos", clientes_geral)
        k3.metric("🧾 Pedidos", pedidos_geral)
        k4.metric("🧮 Ticket médio (AOV)", brl(aov))

        st.markdown("---")
        st.caption("Prévia do histórico bruto (50 primeiras linhas)")
        st.dataframe(df_hist_filt.head(50), use_container_width=True)
