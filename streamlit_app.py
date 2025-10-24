# streamlit_app_forcado_coluna.py
import streamlit as st
import pandas as pd
import time
import plotly.express as px
from datetime import datetime, timedelta
from urllib.parse import quote
import re

st.set_page_config(page_title="Dashboard de Vendas", page_icon="📊", layout="wide")

SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"
SHEET2_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
DEFAULT_SHEET2_SHEETNAME = "Total"

@st.cache_data(ttl=180)
def carregar_csv(url: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(url, sep=",", engine="python", on_bad_lines="skip", encoding="utf-8", na_values=["", "NA", "NaN", None])
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    unnamed = sum(str(c).startswith("Unnamed") for c in df.columns)
    if unnamed > len(df.columns) // 2:
        try:
            _raw = pd.read_csv(url, sep=",", header=None, engine="python")
            new_header = _raw.iloc[0]
            df = _raw[1:].reset_index(drop=True)
            df.columns = new_header
        except Exception:
            pass
    df.columns = [str(c).strip() for c in df.columns]
    return df

# ---------- helpers ----------
def _as_series_safe(df: pd.DataFrame, col_label) -> pd.Series:
    obj = df[col_label] if (df is not None and col_label in df.columns) else pd.Series([], dtype="object")
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj

def _dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
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
    df = df.copy(); df.columns = new_cols
    return df

def _cleanup_currency_text(s_raw: str) -> str:
    s = str(s_raw or "").strip().replace("\u00A0", " ")
    s = re.sub(r"[Rr]\$\s*", "", s)
    s = re.sub(r"[^\d,\.\-]", "", s)
    return s

def _to_float_brl_strict(series: pd.Series) -> pd.Series:
    def parse_one(x):
        if pd.isna(x):
            return float("nan")
        s = _cleanup_currency_text(x)
        if "," in s:
            s2 = s.replace(".", "").replace(",", ".")
            try:
                return float(s2)
            except Exception:
                pass
        s_digits = re.sub(r"[^\d\-]", "", s)
        if s_digits in ("", "-"):
            return float("nan")
        neg = s_digits.startswith("-")
        d = s_digits[1:] if neg else s_digits
        val = float(d) / 100.0 if len(d) <= 2 else float(d[:-2] + "." + d[-2:])
        return -val if neg else val
    out = series.astype("string").apply(parse_one)
    try:
        s_pos = out[out > 0]
        if len(s_pos) >= 20:
            med = s_pos.median()
            if med > 0 and s_pos.quantile(0.99) > 10000 * med:
                out = out.mask(out > 10000 * med, other=float("nan"))
    except Exception:
        pass
    return out.fillna(0.0)

def _to_float_brl_relaxed(series: pd.Series) -> pd.Series:
    def parse_one(x):
        if pd.isna(x):
            return float("nan")
        s = _cleanup_currency_text(x)
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            left, right = s.rsplit(",", 1)
            if right.isdigit() and 1 <= len(right) <= 2:
                s = left.replace(",", "") + "." + right
            else:
                s = (left + right).replace(",", "")
        elif "." in s:
            left, right = s.rsplit(".", 1)
            if right.isdigit() and 1 <= len(right) <= 2:
                s = left.replace(".", "") + "." + right
            else:
                s = (left + right).replace(".", "")
        else:
            d = re.sub(r"\D", "", str(x))
            s = (f"0.{d.zfill(2)}" if len(d) <= 2 else d[:-2] + "." + d[-2:])
        try:
            return float(s)
        except Exception:
            return float("nan")
    return series.astype("string").apply(parse_one).fillna(0.0)

def _format_brl(x: float) -> str:
    try:
        return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

VALOR_PATTERNS   = re.compile(r"(valor|receita|total|gasto|faturamento|ltv)", re.I)
COMPRAS_PATTERNS = re.compile(r"(compra|pedido|ordens?|qtd|quant)", re.I)

def _score_money_col(s: pd.Series) -> float:
    try:
        parsed = _to_float_brl_strict(s)
        pos = parsed[parsed > 0]
        if len(pos) == 0:
            return 0.0
        return float(pos.median() * len(pos))
    except Exception:
        return 0.0

def detectar_colunas_resumo(df: pd.DataFrame):
    valor_cands, compras_cands = [], []
    for c in df.columns:
        c_str = str(c)
        if VALOR_PATTERNS.search(c_str):
            valor_cands.append(c)
        if COMPRAS_PATTERNS.search(c_str):
            compras_cands.append(c)
    if not valor_cands:
        valor_cands = list(df.columns)
    best_val, best_score = None, -1
    for c in valor_cands:
        try:
            s = _as_series_safe(df, c)
            sc = _score_money_col(s)
            if sc > best_score:
                best_score = sc
                best_val = c
        except Exception:
            continue
    if not compras_cands:
        for c in df.columns:
            try:
                s = pd.to_numeric(_as_series_safe(df, c), errors="coerce")
                if s.notna().sum() == 0:
                    continue
                if (s.dropna() % 1 == 0).mean() > 0.95 and s.dropna().median() <= 5:
                    compras_cands.append(c)
            except Exception:
                continue
    best_cmp = compras_cands[0] if compras_cands else None
    return best_val, best_cmp

def preparar_df_vendas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    if not isinstance(df, pd.DataFrame):
        try:
            df = pd.DataFrame(df)
        except Exception:
            return pd.DataFrame()
    if df.empty:
        return df
    if "DATA DE INÍCIO" in df.columns:
        df["DATA DE INÍCIO"] = pd.to_datetime(df["DATA DE INÍCIO"], errors="coerce", dayfirst=True)
    if "VALOR (R$)" in df.columns:
        df["VALOR (R$)"] = _to_float_brl_relaxed(df["VALOR (R$)"])
    return df

def preparar_df_historico_resumo(df: pd.DataFrame):
    if df.empty:
        return df.copy(), None, None
    df = df.copy(); df.columns = [str(c).strip() for c in df.columns]
    nome_col  = next((c for c in ["NOME COMPLETO","CLIENTE","NOME","Nome"] if c in df.columns), df.columns[0])
    email_col = next((c for c in ["E-MAIL","EMAIL","Email","e-mail"] if c in df.columns), None)
    df["CLIENTE_NOME"]  = _as_series_safe(df, nome_col).astype(str).str.strip() if nome_col else ""
    df["CLIENTE_EMAIL"] = _as_series_safe(df, email_col).astype(str).str.strip().str.lower() if email_col else ""
    df["CLIENTE_ID"]    = df["CLIENTE_EMAIL"].where(df["CLIENTE_EMAIL"] != "", df["CLIENTE_NOME"])
    valor_col, compras_col = detectar_colunas_resumo(df)
    df["VALOR_PAD"] = _to_float_brl_strict(_as_series_safe(df, valor_col)) if valor_col else 0.0
    if compras_col:
        df["N_COMPRAS"] = pd.to_numeric(_as_series_safe(df, compras_col), errors="coerce").fillna(0).astype(int)
    else:
        df["N_COMPRAS"] = 0
    try:
        base_nome = _as_series_safe(df, nome_col) if nome_col else pd.Series([], dtype=str)
        mask_total = base_nome.astype(str).str.lower().str.contains("total|subtotal|geral", regex=True, na=False)
        df = df.loc[~mask_total].reset_index(drop=True)
    except Exception:
        pass
    try:
        s = df["VALOR_PAD"]; med = s.median(); q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = max(q3 - q1, 1.0); hard_cap = (med + 3*iqr) * 10
        df.loc[s > hard_cap, "VALOR_PAD"] = 0.0
    except Exception:
        pass
    return df, valor_col, compras_col

def preparar_df_historico_transacional(df: pd.DataFrame, valor_col=None, date_col=None, produto_col=None) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    df = df.copy(); df.columns = [str(c).strip() for c in df.columns]
    if not date_col or date_col not in df.columns:
        for c in ["DATA","DATA DA COMPRA","DATA DE INÍCIO","DATA VENDA","DATA/HORA","DATA HORA"]:
            if c in df.columns: date_col = c; break
    df["DATA_REF"] = pd.to_datetime(_as_series_safe(df, date_col), errors="coerce", dayfirst=True) if date_col and date_col in df.columns else pd.NaT
    if not valor_col or valor_col not in df.columns:
        for c in ["VALOR (R$)","VALOR","TOTAL (R$)","TOTAL","PREÇO","PRECO"]:
            if c in df.columns: valor_col = c; break
    df["VALOR_PAD"] = _to_float_brl_strict(_as_series_safe(df, valor_col)) if valor_col and valor_col in df.columns else 0.0
    if not produto_col or produto_col not in df.columns:
        for c in ["PRODUTO","ITEM","SKU","DESCRIÇÃO","DESCRICAO"]:
            if c in df.columns: produto_col = c; break
    df["PRODUTO_PAD"] = _as_series_safe(df, produto_col).astype(str) if produto_col and produto_col in df.columns else ""
    nome_col  = next((c for c in ["NOME COMPLETO","CLIENTE","NOME","Nome"] if c in df.columns), None)
    email_col = next((c for c in ["E-MAIL","EMAIL","Email","e-mail"] if c in df.columns), None)
    df["CLIENTE_NOME"]  = _as_series_safe(df, nome_col).astype(str).str.strip() if nome_col else ""
    df["CLIENTE_EMAIL"] = _as_series_safe(df, email_col).astype(str).str.strip().str.lower() if email_col else ""
    df["CLIENTE_ID"]    = df["CLIENTE_EMAIL"].where(df["CLIENTE_EMAIL"] != "", df["CLIENTE_NOME"])
    return df

# ========================= CARREGAMENTO =========================
with st.spinner("Carregando Planilha 1 (colaborador)…"):
    df_vendas_raw = carregar_csv(SHEET_URL_1)

df_vendas_raw = _dedupe_columns(df_vendas_raw)
df_vendas = preparar_df_vendas(df_vendas_raw.copy())

sheet2_sheetname = DEFAULT_SHEET2_SHEETNAME
SHEET_URL_2 = f"https://docs.google.com/spreadsheets/d/{SHEET2_ID}/gviz/tq?tqx=out:csv&sheet={quote(sheet2_sheetname)}"
with st.spinner("Carregando Planilha 2…"):
    df_extra_raw = carregar_csv(SHEET_URL_2)

df_extra_raw = _dedupe_columns(df_extra_raw)

# Detecta modo transacional
date_candidates = [c for c in ["DATA","DATA DA COMPRA","DATA DE INÍCIO","DATA VENDA","DATA/HORA","DATA HORA"] if c in df_extra_raw.columns]
is_transacional = False
if date_candidates:
    try:
        dt = pd.to_datetime(_as_series_safe(df_extra_raw, date_candidates[0]), errors="coerce", dayfirst=True)
        is_transacional = dt.notna().sum() >= max(10, int(len(df_extra_raw)*0.2))
    except Exception:
        is_transacional = False

# ============ Sidebar: Forçar coluna de valor (Planilha 2) ============
st.sidebar.header("Planilha 2 — Controles")
force_val_col = st.sidebar.checkbox("Forçar coluna de VALOR", value=False, help="Use se a detecção automática não acertar.")
forced_name = st.sidebar.text_input("Nome exato da coluna (opcional)", value="") if force_val_col else ""
forced_letter = st.sidebar.text_input("Letra da coluna (opcional, ex.: D)", value="") if force_val_col else ""
forced_col_final = None
if force_val_col and not df_extra_raw.empty:
    if forced_name and forced_name in df_extra_raw.columns:
        forced_col_final = forced_name
    elif forced_letter:
        abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        letter = forced_letter.strip().upper()
        idx = 0
        for ch in letter:
            if ch not in abc:
                idx = None; break
            idx = idx * 26 + (abc.index(ch) + 1)
        if idx:
            zero_idx = idx - 1
            if 0 <= zero_idx < len(df_extra_raw.columns):
                forced_col_final = df_extra_raw.columns[zero_idx]

# ========================= LÓGICA PRINCIPAL =========================
if is_transacional:
    df_hist = preparar_df_historico_transacional(df_extra_raw.copy())
    valor_col_det = "VALOR_PAD"; compras_col_det = None
    if forced_col_final:
        try:
            df_hist["VALOR_PAD"] = _to_float_brl_strict(_as_series_safe(df_extra_raw, forced_col_final))
            valor_col_det = forced_col_final + " (forçado)"
        except Exception:
            st.warning("Não foi possível aplicar a coluna de valor forçada na planilha transacional.")
else:
    df_hist, valor_col_det, compras_col_det = preparar_df_historico_resumo(df_extra_raw.copy())
    if forced_col_final:
        try:
            df_hist["VALOR_PAD"] = _to_float_brl_strict(_as_series_safe(df_extra_raw, forced_col_final))
            valor_col_det = forced_col_final + " (forçado)"
        except Exception:
            st.warning("Não foi possível aplicar a coluna de valor forçada no resumo.")

# ========================= TOPO =========================
c_a, c_b, _ = st.columns([1,1,2])
with c_a:
    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear(); time.sleep(0.2); st.rerun()
with c_b:
    st.success(f"✅ Dados atualizados às {time.strftime('%H:%M:%S')}")

ok1 = "✅" if not df_vendas.empty else "⚠️"
ok2 = "✅" if not df_hist.empty else "⚠️"
st.markdown(f"**Planilha 1 (Colaborador):** {ok1}  |  **Planilha 2 (Geral):** {ok2}")

# ========================= ABAS =========================
aba1, aba2 = st.tabs(["📊 Análises do Colaborador (Planilha 1)","📑 Histórico Geral (Planilha 2)"])

with aba1:
    colab_detectado = None
    if not df_vendas.empty:
        for c in ["COLABORADOR","VENDEDOR","RESPONSÁVEL"]:
            if c in df_vendas.columns and not df_vendas[c].dropna().empty:
                vals = df_vendas[c].dropna().astype(str).unique().tolist()
                if len(vals) == 1:
                    colab_detectado = vals[0]
                break
    st.subheader(f"📦 Vendas do Colaborador{(' — ' + colab_detectado) if colab_detectado else ''}")
    if df_vendas.empty:
        st.warning("Sem dados na Planilha 1.")
    else:
        total_vendas = float(df_vendas.get("VALOR (R$)", pd.Series(dtype=float)).sum())
        clientes = int(df_vendas.get("NOME COMPLETO", pd.Series(dtype=str)).nunique()) if "NOME COMPLETO" in df_vendas.columns else 0
        ticket = total_vendas / clientes if clientes > 0 else 0.0
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Total de Vendas", _format_brl(total_vendas))
        c2.metric("👥 Clientes Únicos", clientes)
        c3.metric("🎯 Ticket Médio",    _format_brl(ticket))
        base = df_vendas[df_vendas.get("DATA DE INÍCIO").notna()] if "DATA DE INÍCIO" in df_vendas.columns else pd.DataFrame()
        if not base.empty:
            base = base[base["DATA DE INÍCIO"].dt.weekday != 6]
        st.subheader("📊 Vendas por Dia com Linha de Tendência")
        vendas_por_dia = (base.groupby("DATA DE INÍCIO", as_index=False)["VALOR (R$)"].sum().sort_values("DATA DE INÍCIO")) if not base.empty else pd.DataFrame()
        if not vendas_por_dia.empty:
            vendas_por_dia["Tendência"] = vendas_por_dia["VALOR (R$)"].rolling(window=7, min_periods=1).mean()
            graf1 = px.line(vendas_por_dia, x="DATA DE INÍCIO", y=["VALOR (R$)","Tendência"], markers=True,
                            labels={"DATA DE INÍCIO":"Data","value":"Vendas (R$)","variable":"Legenda"})
            graf1.update_traces(selector=dict(name="VALOR (R$)"), line=dict(width=2))
            graf1.update_traces(selector=dict(name="Tendência"),   line=dict(width=3, dash="dash"))
            st.plotly_chart(graf1, use_container_width=True)

with aba2:
    st.subheader("📑 Histórico Geral de Clientes")
    if df_hist.empty:
        st.info("Sem dados na Planilha 2.")
    else:
        if is_transacional:
            min_data = pd.to_datetime(df_hist["DATA_REF"], errors="coerce").min()
            max_data = pd.to_datetime(df_hist["DATA_REF"], errors="coerce").max()
            if pd.isna(min_data) or pd.isna(max_data):
                min_data = datetime.today() - timedelta(days=180)
                max_data = datetime.today()
            periodo = st.date_input("Período", value=(min_data.date(), max_data.date()), min_value=(min_data - timedelta(days=365)).date(), max_value=(max_data + timedelta(days=365)).date())
            df_hist_filt = df_hist.copy()
            if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
                di, df_ = periodo
                di = datetime.combine(di, datetime.min.time())
                df_ = datetime.combine(df_, datetime.max.time())
                df_hist_filt = df_hist_filt[(df_hist_filt["DATA_REF"] >= di) & (df_hist_filt["DATA_REF"] <= df_)]
            total_geral = float(df_hist_filt["VALOR_PAD"].sum())
            clientes_geral = int(df_hist_filt["CLIENTE_ID"].nunique())
            pedidos_geral = int(df_hist_filt.shape[0])
            aov = total_geral / pedidos_geral if pedidos_geral > 0 else 0.0
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Receita (período)", _format_brl(total_geral))
            k2.metric("🧑‍🤝‍🧑 Clientes únicos", clientes_geral)
            k3.metric("🧾 Pedidos", pedidos_geral)
            k4.metric("🧮 Ticket médio (AOV)", _format_brl(aov))
            st.caption("Modo transacional (com datas).")
        else:
            receita_total = float(df_hist["VALOR_PAD"].sum())
            total_compras = int(df_hist["N_COMPRAS"].sum()) if "N_COMPRAS" in df_hist.columns else 0
            clientes = int(df_hist["CLIENTE_ID"].nunique()) if "CLIENTE_ID" in df_hist.columns else int(df_hist.shape[0])
            aov = receita_total / total_compras if total_compras > 0 else 0.0
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Receita total (clientes)", _format_brl(receita_total))
            k2.metric("🧑‍🤝‍🧑 Clientes", clientes)
            k3.metric("🛒 Nº de compras", total_compras)
            k4.metric("🎯 Ticket médio", _format_brl(aov))
            st.caption(f"Coluna de VALOR: **{valor_col_det}** | Coluna de COMPRAS: **{compras_col_det or '—'}**")
        st.markdown("---")
        st.caption("Prévia (50 primeiras linhas)")
        _preview = _dedupe_columns(df_hist.copy())
        for col in _preview.select_dtypes(include=['object']).columns:
            try:
                _preview[col] = _preview[col].apply(lambda v: v if isinstance(v, (str, int, float, type(None), pd.Timestamp)) else str(v))
            except Exception:
                _preview[col] = _preview[col].astype(str)
        st.dataframe(_preview.head(50), use_container_width=True)
