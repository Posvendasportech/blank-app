# streamlit_app.py
import streamlit as st
import pandas as pd
import time
import plotly.express as px
from datetime import datetime, timedelta
from urllib.parse import quote
import re

# =========================
# Config da página
# =========================
st.set_page_config(page_title="Dashboard de Vendas", page_icon="📊", layout="wide")

# =========================
# IDs / URLs
# =========================
# Planilha 1 (vendas de UM colaborador) — link CSV direto
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"

# Planilha 2 (geral)
SHEET2_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
DEFAULT_SHEET2_SHEETNAME = "Total"

# =========================
# Utils
# =========================
@st.cache_data(ttl=180)
def carregar_csv(url: str) -> pd.DataFrame:
    """Lê CSV remoto e tenta consertar cabeçalho ruim."""
    df = pd.read_csv(
        url, sep=",", engine="python", on_bad_lines="skip",
        encoding="utf-8", na_values=["", "NA", "NaN", None]
    )
    unnamed = sum(str(c).startswith("Unnamed") for c in df.columns)
    if unnamed > len(df.columns) // 2:
        _raw = pd.read_csv(url, sep=",", header=None, engine="python")
        new_header = _raw.iloc[0]
        df = _raw[1:].reset_index(drop=True)
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

def _cleanup_currency_text(s_raw: str) -> str:
    """Remove R$, espaços estranhos e mantém apenas dígitos, vírgula, ponto e sinal."""
    s = str(s_raw).strip().replace("\u00A0", " ")
    s = re.sub(r"[Rr]\$\s*", "", s)
    s = re.sub(r"[^\d,.\-]", "", s)
    return s

def _to_float_brl_strict(series: pd.Series) -> pd.Series:
    """
    Conversão *estrita* pt-BR para evitar estouro:
    - Assume '.' = milhar e ',' = decimal SEMPRE (se houver vírgula).
    - Se não existir vírgula:
        - remove todos os pontos (tratados como milhar)
        - se só sobram dígitos → interpreta em centavos (divide por 100) quando fizer sentido.
    - Aplica correção defensiva se valores ficarem absurdos.
    """
    def parse_one(x):
        if pd.isna(x):
            return float("nan")
        raw = str(x)
        s = _cleanup_currency_text(raw)

        # Caso com vírgula: cenário padrão BR
        if "," in s:
            s2 = s.replace(".", "").replace(",", ".")
            try:
                return float(s2)
            except Exception:
                pass

        # Sem vírgula: trate pontos como milhar e tente centavos
        s_digits = re.sub(r"[^\d\-]", "", s)  # só dígitos e sinal
        if s_digits in ("", "-",):
            return float("nan")
        # Heurística: números sem vírgula normalmente estão em centavos quando vieram de exportações
        neg = s_digits.startswith("-")
        d = s_digits[1:] if neg else s_digits
        if len(d) <= 2:
            val = float(d) / 100.0
        else:
            val = float(d[:-2] + "." + d[-2:])
        return -val if neg else val

    out = series.astype("string").apply(parse_one)

    # Correção de escala defensiva (anti-trilhão):
    # Se 95º percentil for > 10.000x a mediana e ambos > 0, tente reprocessar assumindo vírgula decimal sempre.
    try:
        s_pos = out[out > 0]
        if len(s_pos) >= 20:
            med = s_pos.median()
            p95 = s_pos.quantile(0.95)
            if med > 0 and p95 > 10000 * med:
                out = series.astype("string").apply(
                    lambda x: float(_cleanup_currency_text(x).replace(".", "").replace(",", ".")) \
                              if re.search(r"[\d]+[,]\d{1,2}", str(x)) else float("nan")
                )
    except Exception:
        pass

    return out.fillna(0.0)

def _to_float_brl_relaxed(series: pd.Series) -> pd.Series:
    """
    Conversor *flexível* (usa na planilha do colaborador, que costuma vir bem formatada).
    """
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
            if len(d) <= 2:
                s = f"0.{d.zfill(2)}"
            else:
                s = d[:-2] + "." + d[-2:]
        try:
            return float(s)
        except Exception:
            return float("nan")
    return series.astype("string").apply(parse_one).fillna(0.0)

def preparar_df_vendas(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "DATA DE INÍCIO" in df.columns:
        df["DATA DE INÍCIO"] = pd.to_datetime(df["DATA DE INÍCIO"], errors="coerce", dayfirst=True)
    if "VALOR (R$)" in df.columns:
        df["VALOR (R$)"] = _to_float_brl_relaxed(df["VALOR (R$)"])
    return df

def preparar_df_historico_resumo(df: pd.DataFrame, valor_letter="D", compras_letter="F") -> pd.DataFrame:
    """Planilha 2 no formato: 1 linha = 1 cliente. D=Valor total, F=Compras."""
    if df.empty:
        return df.copy()
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Nome / Email / ID
    nome_col  = next((c for c in ["NOME COMPLETO","CLIENTE","NOME","Nome"] if c in df.columns), df.columns[0])
    email_col = next((c for c in ["E-MAIL","EMAIL","Email","e-mail"] if c in df.columns), None)
    df["CLIENTE_NOME"]  = df[nome_col].astype(str).str.strip() if nome_col else ""
    df["CLIENTE_EMAIL"] = df[email_col].astype(str).str.strip().str.lower() if email_col else ""
    df["CLIENTE_ID"]    = df["CLIENTE_EMAIL"].where(df["CLIENTE_EMAIL"] != "", df["CLIENTE_NOME"])

    # Valor / Compras por LETRA (conversão ESTRITA para evitar estouro)
    col_val = _col_by_letter(df, valor_letter)   # D
    col_cmp = _col_by_letter(df, compras_letter) # F
    df["VALOR_PAD"] = _to_float_brl_strict(df[col_val]) if col_val else 0.0
    df["N_COMPRAS"] = pd.to_numeric(df[col_cmp], errors="coerce").fillna(0).astype(int) if col_cmp else 0

    # Remove linhas agregadoras (Total/Subtotal/Geral)
    mask_total = df[nome_col].astype(str).str.lower().str.contains("total|subtotal|geral", regex=True, na=False) if nome_col else False
    df = df.loc[~mask_total].reset_index(drop=True)

    return df

def preparar_df_historico_transacional(df: pd.DataFrame, valor_col=None, date_col=None, produto_col=None) -> pd.DataFrame:
    """Planilha 2 transacional: linhas = pedidos (com data, valor, produto...)."""
    if df.empty:
        return df.copy()
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Data
    if not date_col or date_col not in df.columns:
        for c in ["DATA","DATA DA COMPRA","DATA DE INÍCIO","DATA VENDA","DATA/HORA","DATA HORA"]:
            if c in df.columns: date_col = c; break
    df["DATA_REF"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True) if date_col and date_col in df.columns else pd.NaT

    # Valor (conversão ESTRITA)
    if not valor_col or valor_col not in df.columns:
        for c in ["VALOR (R$)","VALOR","TOTAL (R$)","TOTAL","PREÇO","PRECO"]:
            if c in df.columns: valor_col = c; break
    df["VALOR_PAD"] = _to_float_brl_strict(df[valor_col]) if valor_col and valor_col in df.columns else 0.0

    # Produto
    if not produto_col or produto_col not in df.columns:
        for c in ["PRODUTO","ITEM","SKU","DESCRIÇÃO","DESCRICAO"]:
            if c in df.columns: produto_col = c; break
    df["PRODUTO_PAD"] = df[produto_col].astype(str) if produto_col and produto_col in df.columns else ""

    # Cliente
    nome_col  = next((c for c in ["NOME COMPLETO","CLIENTE","NOME","Nome"] if c in df.columns), None)
    email_col = next((c for c in ["E-MAIL","EMAIL","Email","e-mail"] if c in df.columns), None)
    df["CLIENTE_NOME"]  = df[nome_col].astype(str).str.strip() if nome_col else ""
    df["CLIENTE_EMAIL"] = df[email_col].astype(str).str.strip().str.lower() if email_col else ""
    df["CLIENTE_ID"]    = df["CLIENTE_EMAIL"].where(df["CLIENTE_EMAIL"] != "", df["CLIENTE_NOME"])
    return df

# =========================
# Helpers
# =========================
PT_WEEK_ORDER = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado"]
PT_WEEK_MAP   = {0:"Segunda",1:"Terça",2:"Quarta",3:"Quinta",4:"Sexta",5:"Sábado",6:"Domingo"}

def _format_brl(x: float) -> str:
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =========================
# Carrega Planilha 1
# =========================
with st.spinner("Carregando Planilha 1 (colaborador)…"):
    df_vendas_raw = carregar_csv(SHEET_URL_1)
df_vendas = preparar_df_vendas(df_vendas_raw.copy())

# =========================
# Carrega Planilha 2 (auto-detecção de modo)
# =========================
sheet2_sheetname = DEFAULT_SHEET2_SHEETNAME
SHEET_URL_2 = f"https://docs.google.com/spreadsheets/d/{SHEET2_ID}/gviz/tq?tqx=out:csv&sheet={quote(sheet2_sheetname)}"

with st.spinner("Carregando Planilha 2…"):
    try:
        df_extra_raw = carregar_csv(SHEET_URL_2)
    except Exception as e:
        st.error(f"❌ Erro ao abrir Planilha 2: {e}")
        df_extra_raw = pd.DataFrame()

# Detecta se é transacional: existe uma coluna de data válida com muitas entradas
date_candidates = [c for c in ["DATA","DATA DA COMPRA","DATA DE INÍCIO","DATA VENDA","DATA/HORA","DATA HORA"] if c in df_extra_raw.columns]
is_transacional = False
if date_candidates:
    try:
        dt = pd.to_datetime(df_extra_raw[date_candidates[0]], errors="coerce", dayfirst=True)
        is_transacional = dt.notna().sum() >= max(10, int(len(df_extra_raw)*0.2))
    except Exception:
        is_transacional = False

if is_transacional:
    df_hist = preparar_df_historico_transacional(df_extra_raw.copy())
else:
    df_hist = preparar_df_historico_resumo(df_extra_raw.copy(), valor_letter="D", compras_letter="F")

# =========================
# Topo: status e botão atualizar
# =========================
c_a, c_b, c_c = st.columns([1,1,2])
with c_a:
    if st.button("🔄 Atualizar dados"):
        st.cache_data.clear()
        time.sleep(0.3)
        st.rerun()
with c_b:
    st.success(f"✅ Dados atualizados às {time.strftime('%H:%M:%S')}")

ok1 = "✅" if not df_vendas.empty else "⚠️"
ok2 = "✅" if not df_hist.empty else "⚠️"
st.markdown(f"**Planilha 1 (Colaborador):** {ok1}  |  **Planilha 2 (Geral):** {ok2}")

# =========================
# Abas principais
# =========================
aba1, aba2 = st.tabs(["📊 Análises do Colaborador (Planilha 1)","📑 Histórico Geral (Planilha 2)"])

# ======================================================
# 🟢 ABA 1 — (sem filtros)
# ======================================================
with aba1:
    colab_detectado = None
    if not df_vendas.empty:
        for c in ["COLABORADOR","VENDEDOR","RESPONSÁVEL"]:
            if c in df_vendas.columns and not df_vendas[c].dropna().empty:
                vals = df_vendas[c].dropna().astype(str).unique().tolist()
                if len(vals) == 1:
                    colab_detectado = vals[0]
                break

    titulo = f"📦 Vendas do Colaborador {f'— {colab_detectado}' if colab_detectado else ''}".strip()
    st.subheader(titulo)

    if df_vendas.empty:
        st.warning("Sem dados na Planilha 1.")
    else:
        total_vendas = float(df_vendas.get("VALOR (R$)", pd.Series(dtype=float)).sum())
        clientes = int(df_vendas.get("NOME COMPLETO", pd.Series(dtype=str)).nunique())
        ticket = total_vendas / clientes if clientes > 0 else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Total de Vendas", _format_brl(total_vendas))
        c2.metric("👥 Clientes Únicos", clientes)
        c3.metric("🎯 Ticket Médio",    _format_brl(ticket))

        base = df_vendas[df_vendas.get("DATA DE INÍCIO").notna()] if "DATA DE INÍCIO" in df_vendas.columns else pd.DataFrame()
        if not base.empty:
            base = base[base["DATA DE INÍCIO"].dt.weekday != 6]  # exclui domingo

        st.subheader("📊 Vendas por Dia com Linha de Tendência")
        vendas_por_dia = (base.groupby("DATA DE INÍCIO", as_index=False)["VALOR (R$)"].sum().sort_values("DATA DE INÍCIO")) if not base.empty else pd.DataFrame()
        if not vendas_por_dia.empty:
            vendas_por_dia["Tendência"] = vendas_por_dia["VALOR (R$)"].rolling(window=7, min_periods=1).mean()
            graf1 = px.line(vendas_por_dia, x="DATA DE INÍCIO", y=["VALOR (R$)","Tendência"], markers=True,
                            labels={"DATA DE INÍCIO":"Data","value":"Vendas (R$)","variable":"Legenda"},
                            title="Vendas por Dia com Linha de Tendência")
            graf1.update_traces(selector=dict(name="VALOR (R$)"), line=dict(width=2, color="cyan"))
            graf1.update_traces(selector=dict(name="Tendência"),   line=dict(width=3, color="orange", dash="dash"))
            graf1.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf1, use_container_width=True)
        else:
            st.info("Não há dados de vendas diárias.")

        if "PRODUTO" in df_vendas.columns and "VALOR (R$)" in df_vendas.columns:
            st.subheader("Vendas por Produto")
            vendas_prod = df_vendas.groupby("PRODUTO", as_index=False)["VALOR (R$)"].sum().sort_values("VALOR (R$)", ascending=False)
            if not vendas_prod.empty:
                graf3 = px.bar(vendas_prod, x="PRODUTO", y="VALOR (R$)", title="Total de Vendas por Produto")
                graf3.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
                graf3.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                st.plotly_chart(graf3, use_container_width=True)

        if not base.empty:
            st.subheader("📈 Vendas Semanais")
            base_sem = base.assign(SEMANA=base["DATA DE INÍCIO"].dt.to_period("W").apply(lambda r: r.start_time))
            vendas_semanal = base_sem.groupby("SEMANA", as_index=False)["VALOR (R$)"].sum().sort_values("SEMANA")
            graf_semanal = px.line(vendas_semanal, x="SEMANA", y="VALOR (R$)", title="Vendas Semanais", markers=True)
            graf_semanal.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf_semanal, use_container_width=True)

            st.subheader("📊 Vendas por Dia da Semana (exclui domingo)")
            base_dia = base.assign(DIA=base["DATA DE INÍCIO"].dt.dayofweek.map(PT_WEEK_MAP))
            vendas_dia_semana = base_dia.groupby("DIA", as_index=False)["VALOR (R$)"].sum()
            vendas_dia_semana = vendas_dia_semana[vendas_dia_semana["DIA"].isin(PT_WEEK_ORDER)]
            vendas_dia_semana["DIA"] = pd.Categorical(vendas_dia_semana["DIA"], categories=PT_WEEK_ORDER, ordered=True)
            vendas_dia_semana = vendas_dia_semana.sort_values("DIA")
            graf_dia = px.bar(vendas_dia_semana, x="DIA", y="VALOR (R$)", title="Vendas por Dia da Semana")
            graf_dia.update_traces(marker_color="cyan")
            graf_dia.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf_dia, use_container_width=True)

        st.subheader("📈 Curva de Crescimento Acumulada de Vendas")
        if not vendas_por_dia.empty:
            vendas_acum = vendas_por_dia.copy()
            vendas_acum["Acumulado"] = vendas_acum["VALOR (R$)"].cumsum()
            graf_ac = px.line(vendas_acum, x="DATA DE INÍCIO", y="Acumulado", title="Curva de Crescimento Acumulada", markers=True)
            graf_ac.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf_ac, use_container_width=True)

        st.subheader("📊 Este Mês vs Mês Anterior (até hoje)")
        hoje = datetime.today()
        p_atual = hoje.replace(day=1)
        dia_atual = hoje.day
        p_ant   = (p_atual - timedelta(days=1)).replace(day=1)
        try:
            u_ant = p_ant.replace(day=dia_atual)
        except ValueError:
            u_ant = (p_atual - timedelta(days=1))
        vm_atual = base[(base["DATA DE INÍCIO"] >= p_atual) & (base["DATA DE INÍCIO"] <= hoje)]["VALOR (R$)"].sum() if not base.empty else 0.0
        vm_ant   = base[(base["DATA DE INÍCIO"] >= p_ant)   & (base["DATA DE INÍCIO"] <= u_ant)]["VALOR (R$)"].sum() if not base.empty else 0.0
        delta = ((vm_atual - vm_ant) / vm_ant) * 100 if vm_ant else 0.0
        st.metric(f"Vendas até {hoje.strftime('%d/%m')}", _format_brl(vm_atual), f"{delta:.2f}%")

# ======================================================
# 🔵 ABA 2 — Histórico Geral (auto: RESUMO ou TRANSACIONAL)
# ======================================================
with aba2:
    st.subheader("📑 Histórico Geral de Clientes")
    if df_hist.empty:
        st.info("Sem dados na Planilha 2.")
    else:
        if is_transacional:
            # -------- Filtro de DATA (no topo, sem sidebar) --------
            min_data = pd.to_datetime(df_hist["DATA_REF"]).min()
            max_data = pd.to_datetime(df_hist["DATA_REF"]).max()
            if pd.isna(min_data) or pd.isna(max_data):
                min_data = datetime.today() - timedelta(days=180)
                max_data = datetime.today()
            c1, c2 = st.columns(2)
            with c1:
                st.caption("Filtrar por período")
            periodo = st.date_input(
                "Período",
                value=(min_data.date(), max_data.date()),
                min_value=(min_data - timedelta(days=365)).date(),
                max_value=(max_data + timedelta(days=365)).date()
            )
            df_hist_filt = df_hist.copy()
            if isinstance(periodo, tuple) and len(periodo) == 2:
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

            st.subheader("🏆 Top Produtos (período)")
            prod_col = "PRODUTO_PAD" if "PRODUTO_PAD" in df_hist_filt.columns else None
            if prod_col and not df_hist_filt.empty:
                top_prod = (df_hist_filt.groupby(prod_col, as_index=False)["VALOR_PAD"].sum()
                            .sort_values("VALOR_PAD", ascending=False).head(15))
                graf_top = px.bar(top_prod, x=prod_col, y="VALOR_PAD", title="Top Produtos por Receita")
                graf_top.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
                graf_top.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                st.plotly_chart(graf_top, use_container_width=True)

            st.markdown("---")
            st.caption("Prévia (50 primeiras linhas)")
            st.dataframe(df_hist_filt.head(50), use_container_width=True)

        else:
            # -------- Resumo por cliente (sem data) --------
            receita_total = float(df_hist["VALOR_PAD"].sum())
            total_compras = int(df_hist["N_COMPRAS"].sum()) if "N_COMPRAS" in df_hist.columns else 0
            clientes = int(df_hist["CLIENTE_ID"].nunique()) if "CLIENTE_ID" in df_hist.columns else int(df_hist.shape[0])
            aov = receita_total / total_compras if total_compras > 0 else 0.0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Receita total (clientes)", _format_brl(receita_total))
            k2.metric("🧑‍🤝‍🧑 Clientes", clientes)
            k3.metric("🛒 Nº de compras", total_compras)
            k4.metric("🎯 Ticket médio", _format_brl(aov))

            st.subheader("🏆 Top Clientes por Valor Gasto")
            top = df_hist.sort_values("VALOR_PAD", ascending=False).head(20)
            graf = px.bar(top, x="CLIENTE_NOME", y="VALOR_PAD", text="VALOR_PAD", title="Top 20 Clientes")
            graf.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
            graf.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf, use_container_width=True)

            st.caption("Obs.: Esta aba usa planilha em formato RESUMO (sem datas). Para filtrar por período, use uma aba transacional (linhas = pedidos).")
            st.markdown("---")
            st.caption("Prévia (50 primeiras linhas)")
            st.dataframe(df_hist.head(50), use_container_width=True)
