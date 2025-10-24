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
@st.cache_data(ttl=120)
def carregar_csv(url: str) -> pd.DataFrame:
    """Lê CSV remoto e tenta consertar cabeçalho ruim."""
    df = pd.read_csv(
        url, sep=",", engine="python", on_bad_lines="skip",
        encoding="utf-8", na_values=["", "NA", "NaN", None]
    )
    unnamed = sum(str(c).startswith("Unnamed") for c in df.columns)
    if unnamed > len(df.columns) // 2:
        _raw = pd.read_csv(url, sep=",", header=None)
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

def _to_float_brl(series: pd.Series) -> pd.Series:
    """
    Conversor robusto para valores pt-BR:
    - Remove 'R$', espaços (inclui NBSP), e símbolos estranhos;
    - Caso haja '.' e ',' → assume formato BR ('.' milhar, ',' decimal);
    - Caso haja só ',' → se últimos 1-2 dígitos forem decimais, usa vírgula como decimal; senão remove vírgulas (milhar);
    - Caso haja só '.' → se últimos 1-2 dígitos forem decimais, usa ponto como decimal; senão remove pontos (milhar);
    - Fallback seguro: se ainda ficar estranho, usa estratégia "centavos" (últimos 2 dígitos).
    """

    def parse_one(x):
        if pd.isna(x):
            return float("nan")

        s_raw = str(x)
        s = s_raw.strip().replace("\u00A0", " ")              # NBSP -> espaço
        s = re.sub(r"[Rr]\$\s*", "", s)                       # remove R$
        s = re.sub(r"[^\d,.\-]", "", s)                       # mantém dígitos, , . e -

        def _as_float_safe(num_txt: str):
            try:
                return float(num_txt)
            except Exception:
                return None

        # Caso 1: tem ponto e vírgula (pt-BR típico: 1.234.567,89)
        if "," in s and "." in s:
            candidate = s.replace(".", "").replace(",", ".")
            val = _as_float_safe(candidate)
            if val is not None:
                return val

        # Caso 2: só vírgula
        if "," in s and "." not in s:
            left, right = s.rsplit(",", 1)
            if right.isdigit() and 1 <= len(right) <= 2:
                candidate = left.replace(",", "") + "." + right
                val = _as_float_safe(candidate)
                if val is not None:
                    return val
            # vírgula como milhar (ex: 1,234,567)
            candidate = (left + right).replace(",", "")
            val = _as_float_safe(candidate)
            if val is not None:
                return val

        # Caso 3: só ponto
        if "." in s and "," not in s:
            left, right = s.rsplit(".", 1)
            if right.isdigit() and 1 <= len(right) <= 2:
                # ponto como decimal
                candidate = left.replace(".", "") + "." + right
                val = _as_float_safe(candidate)
                if val is not None:
                    return val
            # ponto como milhar
            candidate = (left + right).replace(".", "")
            val = _as_float_safe(candidate)
            if val is not None:
                return val

        # Caso 4: apenas dígitos (ou algo falhou)
        digits = re.sub(r"\D", "", s_raw)
        if digits == "":
            return float("nan")
        # Estratégia "centavos": últimos 2 dígitos são centavos
        if len(digits) == 1:
            return float(digits) / 100.0
        if len(digits) == 2:
            return float(digits) / 100.0
        return float(digits[:-2] + "." + digits[-2:])

    out = series.astype("string").apply(parse_one)

    # Correção de escala defensiva:
    # Se 80%+ dos valores > 0 e a mediana > 0 e p95 > 100 * mediana,
    # é um forte indício de parse errado. Tenta reprocessar via "formato BR estrito".
    try:
        s_pos = out[out > 0]
        if len(s_pos) >= 10:
            med = s_pos.median()
            p95 = s_pos.quantile(0.95)
            if med > 0 and p95 > 100 * med:
                # Reprocessa assumindo sempre BR com '.' milhar e ',' decimal
                def br_strict(x):
                    s = str(x).strip().replace("\u00A0", " ")
                    s = re.sub(r"[Rr]\$\s*", "", s)
                    s = re.sub(r"[^\d,.\-]", "", s)
                    if "," in s:
                        s = s.replace(".", "").replace(",", ".")
                    else:
                        s = s.replace(".", "")
                    try:
                        return float(s)
                    except Exception:
                        return float("nan")
                out = series.astype("string").apply(br_strict)
    except Exception:
        pass

    return out

def preparar_df_vendas(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "DATA DE INÍCIO" in df.columns:
        df["DATA DE INÍCIO"] = pd.to_datetime(df["DATA DE INÍCIO"], errors="coerce", dayfirst=True)
    if "VALOR (R$)" in df.columns:
        df["VALOR (R$)"] = _to_float_brl(df["VALOR (R$)"]).fillna(0.0)
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

    # Valor / Compras por LETRA
    col_val = _col_by_letter(df, valor_letter)   # D
    col_cmp = _col_by_letter(df, compras_letter) # F

    df["VALOR_PAD"] = _to_float_brl(df[col_val]).fillna(0.0) if col_val else 0.0
    df["N_COMPRAS"] = pd.to_numeric(df[col_cmp], errors="coerce").fillna(0).astype(int) if col_cmp else 0

    # Limpa linhas agregadoras (ex.: "Total/Subtotal/Geral")
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

    # Valor
    if not valor_col or valor_col not in df.columns:
        for c in ["VALOR (R$)","VALOR","TOTAL (R$)","TOTAL","PREÇO","PRECO"]:
            if c in df.columns: valor_col = c; break
    df["VALOR_PAD"] = _to_float_brl(df[valor_col]).fillna(0.0) if valor_col and valor_col in df.columns else 0.0

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
# Constantes auxiliares
# =========================
PT_WEEK_ORDER = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado"]
PT_WEEK_MAP   = {0:"Segunda",1:"Terça",2:"Quarta",3:"Quinta",4:"Sexta",5:"Sábado",6:"Domingo"}

# =========================
# Carrega Planilha 1
# =========================
with st.spinner("Carregando Planilha 1 (colaborador)…"):
    df_vendas_raw = carregar_csv(SHEET_URL_1)
df_vendas = preparar_df_vendas(df_vendas_raw.copy())

# =========================
# Carrega Planilha 2 (sem UI lateral)
# =========================
sheet2_sheetname = DEFAULT_SHEET2_SHEETNAME
SHEET_URL_2 = f"https://docs.google.com/spreadsheets/d/{SHEET2_ID}/gviz/tq?tqx=out:csv&sheet={quote(sheet2_sheetname)}"

with st.spinner("Carregando Planilha 2…"):
    try:
        df_extra_raw = carregar_csv(SHEET_URL_2)
    except Exception as e:
        st.error(f"❌ Erro ao abrir Planilha 2: {e}")
        df_extra_raw = pd.DataFrame()

# =========================
# Preparo Planilha 2 (modo padrão: Resumo por cliente D/F)
# =========================
df_historico = preparar_df_historico_resumo(df_extra_raw.copy(), valor_letter="D", compras_letter="F")

# =========================
# Status topo + ações
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
ok2 = "✅" if not df_historico.empty else "⚠️"
st.markdown(f"**Planilha 1 (Colaborador):** {ok1}  |  **Planilha 2 (Geral):** {ok2}")

# =========================
# Abas principais (sem filtros)
# =========================
aba1, aba2 = st.tabs(["📊 Análises do Colaborador (Planilha 1)","📑 Histórico Geral (Planilha 2)"])

# ======================================================
# 🟢 ABA 1 — análises do colaborador (sem filtros)
# ======================================================
with aba1:
    # Detecta nome do colaborador automaticamente (se houver coluna)
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
        df_filtrado = df_vendas.copy()  # sem filtros

        total_vendas = float(df_filtrado["VALOR (R$)"].sum()) if "VALOR (R$)" in df_filtrado.columns else 0.0
        clientes = int(df_filtrado.get("NOME COMPLETO", pd.Series(dtype=str)).nunique()) if "NOME COMPLETO" in df_filtrado.columns else 0
        ticket = total_vendas / clientes if clientes > 0 else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Total de Vendas", f"R$ {total_vendas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        c2.metric("👥 Clientes Únicos", clientes)
        c3.metric("🎯 Ticket Médio",    f"R$ {ticket:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        base = df_filtrado[df_filtrado.get("DATA DE INÍCIO").notna()] if "DATA DE INÍCIO" in df_filtrado.columns else pd.DataFrame()
        if not base.empty:
            base = base[base["DATA DE INÍCIO"].dt.weekday != 6]  # exclui domingo

        # Vendas por Dia + Tendência
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

        # Vendas por Produto (se existir coluna)
        st.subheader("Vendas por Produto")
        if "PRODUTO" in df_filtrado.columns and "VALOR (R$)" in df_filtrado.columns:
            vendas_prod = df_filtrado.groupby("PRODUTO", as_index=False)["VALOR (R$)"].sum().sort_values("VALOR (R$)", ascending=False)
            if not vendas_prod.empty:
                graf3 = px.bar(vendas_prod, x="PRODUTO", y="VALOR (R$)", title="Total de Vendas por Produto")
                graf3.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
                graf3.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                st.plotly_chart(graf3, use_container_width=True)
            else:
                st.info("Sem dados de produtos.")

        # Vendas Semanais
        st.subheader("📈 Vendas Semanais")
        if not base.empty:
            base_sem = base.assign(SEMANA=base["DATA DE INÍCIO"].dt.to_period("W").apply(lambda r: r.start_time))
            vendas_semanal = base_sem.groupby("SEMANA", as_index=False)["VALOR (R$)"].sum().sort_values("SEMANA")
            graf_semanal = px.line(vendas_semanal, x="SEMANA", y="VALOR (R$)", title="Vendas Semanais", markers=True)
            graf_semanal.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf_semanal, use_container_width=True)
        else:
            st.info("Sem dados semanais.")

        # Vendas por Dia da Semana (sem domingo)
        st.subheader("📊 Vendas por Dia da Semana (exclui domingo)")
        if not base.empty:
            base_dia = base.assign(DIA=base["DATA DE INÍCIO"].dt.dayofweek.map(PT_WEEK_MAP))
            vendas_dia_semana = base_dia.groupby("DIA", as_index=False)["VALOR (R$)"].sum()
            vendas_dia_semana = vendas_dia_semana[vendas_dia_semana["DIA"].isin(PT_WEEK_ORDER)]
            vendas_dia_semana["DIA"] = pd.Categorical(vendas_dia_semana["DIA"], categories=PT_WEEK_ORDER, ordered=True)
            vendas_dia_semana = vendas_dia_semana.sort_values("DIA")
            graf_dia = px.bar(vendas_dia_semana, x="DIA", y="VALOR (R$)", title="Vendas por Dia da Semana")
            graf_dia.update_traces(marker_color="cyan")
            graf_dia.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf_dia, use_container_width=True)
        else:
            st.info("Sem dados por dia da semana.")

        # Curva acumulada
        st.subheader("📈 Curva de Crescimento Acumulada de Vendas")
        if not vendas_por_dia.empty:
            vendas_acum = vendas_por_dia.copy()
            vendas_acum["Acumulado"] = vendas_acum["VALOR (R$)"].cumsum()
            graf_ac = px.line(vendas_acum, x="DATA DE INÍCIO", y="Acumulado", title="Curva de Crescimento Acumulada", markers=True)
            graf_ac.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf_ac, use_container_width=True)
        else:
            st.info("Sem dados suficientes para curva acumulada.")

        # Comparação mês atual vs mês anterior (até hoje)
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
        st.metric(f"Vendas até {hoje.strftime('%d/%m')}", f"R$ {vm_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), f"{delta:.2f}%")

# ======================================================
# 🔵 ABA 2 — Histórico Geral (Resumo por cliente, sem filtros)
# ======================================================
with aba2:
    st.subheader("📑 Histórico Geral de Clientes")
    if df_historico.empty:
        st.info("Sem dados na Planilha 2.")
    else:
        receita_total = float(df_historico["VALOR_PAD"].sum())
        total_compras = int(df_historico["N_COMPRAS"].sum()) if "N_COMPRAS" in df_historico.columns else 0
        clientes = int(df_historico["CLIENTE_ID"].nunique()) if "CLIENTE_ID" in df_historico.columns else int(df_historico.shape[0])
        aov = receita_total / total_compras if total_compras > 0 else 0.0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 Receita total (clientes)", f"R$ {receita_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        k2.metric("🧑‍🤝‍🧑 Clientes", clientes)
        k3.metric("🛒 Nº de compras", total_compras)
        k4.metric("🎯 Ticket médio", f"R$ {aov:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        st.subheader("🏆 Top Clientes por Valor Gasto")
        top = df_historico.sort_values("VALOR_PAD", ascending=False).head(20)
        graf = px.bar(top, x="CLIENTE_NOME", y="VALOR_PAD", text="VALOR_PAD", title="Top 20 Clientes")
        graf.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
        graf.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
        st.plotly_chart(graf, use_container_width=True)

        st.markdown("---")
        st.caption("Prévia (50 primeiras linhas)")
        st.dataframe(df_historico.head(50), use_container_width=True)
