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
    Parser por célula:
    - Tem '.' e ',' → assume BR ('.' milhar, ',' decimal): remove '.' e troca ',' por '.'
    - Só ',' → se pós-última vírgula tem 1–2 dígitos, é decimal; senão remove vírgulas
    - Só '.' → se pós-último ponto tem 1–2 dígitos, é decimal; senão remove pontos
    - Remove 'R$', espaços, e outros símbolos
    """
    def parse_one(x):
        s = str(x).strip().replace("\u00A0", " ")
        s = re.sub(r"[Rr]\$\s*", "", s)
        s = re.sub(r"[^\d,.\-]", "", s)

        if s.count(",") > 0 and s.count(".") > 0:
            s = s.replace(".", "").replace(",", ".")
        elif s.count(",") > 0:
            left, right = s.rsplit(",", 1)
            if right.isdigit() and 1 <= len(right) <= 2:
                s = left.replace(",", "") + "." + right
            else:
                s = (left + right).replace(",", "")
        elif s.count(".") > 0:
            left, right = s.rsplit(".", 1)
            if right.isdigit() and 1 <= len(right) <= 2:
                s = left.replace(".", "") + "." + right
            else:
                s = (left + right).replace(".", "")
        try:
            val = float(s)
            # Sanidade: se número veio MUITO grande por parse errado, tente outro caminho
            # (ex.: "1.234,56" -> 123456 ok; mas se ficar >1e10 por linha, provavelmente bug de parse)
            if abs(val) > 1e10 and re.search(r"[\.,]", str(x)):
                # fallback: remove tudo que não for dígito e tenta interpretar últimos 2 como centavos
                digits = re.sub(r"\D", "", str(x))
                if len(digits) >= 3:
                    val = float(digits[:-2] + "." + digits[-2:])
            return val
        except:
            return float("nan")
    return series.apply(parse_one)

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

    # Limpa linhas agregadoras (ex.: "Total")
    mask_total = df[nome_col].astype(str).str.lower().str.contains("total|subtotal|geral", regex=True, na=False) if nome_col else False
    df.loc[mask_total, ["VALOR_PAD","N_COMPRAS"]] = 0

    # Auditoria: se 95º percentil > 100x mediana, assume outliers de parse e limita visualmente (não altera dados)
    if df["VALOR_PAD"].notna().sum() > 5:
        med = df["VALOR_PAD"].median(skipna=True)
        p95 = df["VALOR_PAD"].quantile(0.95)
        if med > 0 and p95 > 100 * med:
            st.sidebar.warning("⚠️ Detectei valores muito fora do padrão na coluna de 'Valor'. Confira o mapeamento D/F e a coluna de origem.")
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
# Sidebar / Controles
# =========================
st.sidebar.title("⚙️ Controles")

# Abas / URL Planilha 2
sheet2_sheetname = st.sidebar.text_input("📄 Nome da aba (Planilha 2)", value=DEFAULT_SHEET2_SHEETNAME)
SHEET_URL_2 = f"https://docs.google.com/spreadsheets/d/{SHEET2_ID}/gviz/tq?tqx=out:csv&sheet={quote(sheet2_sheetname)}"

# Modo da Planilha 2
modo_planilha2 = st.sidebar.radio(
    "Formato da Planilha 2",
    options=["Resumo por Cliente (D=Valor, F=Compras)", "Transacional (linhas = pedidos)"],
    index=0
)

# Mapeamentos Planilha 2
if modo_planilha2.startswith("Resumo"):
    st.sidebar.subheader("Mapeamento por letra (Planilha 2)")
    valor_letter   = st.sidebar.text_input("Letra da coluna de Valor", "D")
    compras_letter = st.sidebar.text_input("Letra da coluna de Compras", "F")
else:
    st.sidebar.subheader("Mapear colunas (Transacional)")
    # esses selects serão preenchidos depois de carregar df_extra_raw
    valor_letter, compras_letter = None, None  # não usados nesse modo

if st.sidebar.button("🔄 Atualizar dados agora"):
    st.cache_data.clear()
    time.sleep(0.3)
    st.rerun()
st.sidebar.success(f"✅ Dados atualizados às {time.strftime('%H:%M:%S')}")

# Nome/label do colaborador
colab_detectado = None
if not df_vendas.empty:
    for c in ["COLABORADOR","VENDEDOR","RESPONSÁVEL"]:
        if c in df_vendas.columns and not df_vendas[c].dropna().empty:
            vals = df_vendas[c].dropna().astype(str).unique().tolist()
            if len(vals) == 1:
                colab_detectado = vals[0]
            break
colaborador = st.sidebar.text_input("👤 Nome do colaborador (rótulo)", value=colab_detectado or "")

# =========================
# Carrega Planilha 2
# =========================
with st.spinner("Carregando Planilha 2…"):
    try:
        df_extra_raw = carregar_csv(SHEET_URL_2)
    except Exception as e:
        st.error(f"❌ Erro ao abrir Planilha 2: {e}")
        df_extra_raw = pd.DataFrame()

# Preparo Planilha 2 conforme modo
if modo_planilha2.startswith("Resumo"):
    df_historico = preparar_df_historico_resumo(df_extra_raw.copy(), valor_letter=valor_letter, compras_letter=compras_letter)
    # AUDITORIA de conversão (mostra 15 linhas)
    try:
        col_val_name = _col_by_letter(df_extra_raw, valor_letter)
        if col_val_name:
            audit = pd.DataFrame({
                "Valor (texto)": df_extra_raw[col_val_name].astype(str).head(15),
                "Valor (num)": _to_float_brl(df_extra_raw[col_val_name]).head(15)
            })
            st.sidebar.markdown("**🔎 Auditoria (conversão de Valor — primeiras 15):**")
            st.sidebar.dataframe(audit, use_container_width=True)
    except Exception:
        pass
else:
    # mapeamento por nome para transacional
    cols = df_extra_raw.columns.tolist()
    valor_col  = st.sidebar.selectbox("Coluna de VALOR",  options=cols) if cols else None
    date_col   = st.sidebar.selectbox("Coluna de DATA",   options=cols) if cols else None
    produto_col= st.sidebar.selectbox("Coluna de PRODUTO",options=cols) if cols else None
    df_historico = preparar_df_historico_transacional(df_extra_raw.copy(), valor_col=valor_col, date_col=date_col, produto_col=produto_col)

# Status topo
ok1 = "✅" if not df_vendas.empty else "⚠️"
ok2 = "✅" if not df_historico.empty else "⚠️"
st.markdown(f"**Planilha 1 (Colaborador):** {ok1}  |  **Planilha 2 (Geral):** {ok2}")

# =========================
# Abas principais
# =========================
aba1, aba2 = st.tabs(["📊 Análises do Colaborador (Planilha 1)","📑 Histórico Geral (Planilha 2)"])

# ======================================================
# 🟢 ABA 1 — (mantém todos os gráficos antigos)
# ======================================================
with aba1:
    titulo = f"📦 Vendas do Colaborador {f'— {colaborador}' if colaborador else ''}".strip()
    st.subheader(titulo)

    if df_vendas.empty:
        st.warning("Sem dados na Planilha 1.")
    else:
        st.sidebar.header("🔎 Filtros (Colaborador)")
        grupos_opts   = sorted(df_vendas.get("GRUPO RFM", pd.Series(dtype=str)).dropna().unique().tolist())
        produtos_opts = sorted(df_vendas.get("PRODUTO",   pd.Series(dtype=str)).dropna().unique().tolist())
        grupos   = st.sidebar.multiselect("Grupo RFM", grupos_opts)
        produtos = st.sidebar.multiselect("Produto",    produtos_opts)

        df_filtrado = df_vendas.copy()
        if grupos and "GRUPO RFM" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["GRUPO RFM"].isin(grupos)]
        if produtos and "PRODUTO" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["PRODUTO"].isin(produtos)]

        if df_filtrado.empty:
            st.info("A combinação de filtros não retornou resultados.")
        else:
            total_vendas = float(df_filtrado["VALOR (R$)"].sum())
            clientes = int(df_filtrado.get("NOME COMPLETO", pd.Series(dtype=str)).nunique())
            ticket = total_vendas / clientes if clientes > 0 else 0.0

            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Total de Vendas", f"R$ {total_vendas:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            c2.metric("👥 Clientes Únicos", clientes)
            c3.metric("🎯 Ticket Médio",    f"R$ {ticket:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            base = df_filtrado[df_filtrado["DATA DE INÍCIO"].notna()].copy()
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
                st.info("Não há dados de vendas diárias após aplicar filtros.")

            colg1, colg2 = st.columns(2)
            with colg1:
                st.subheader("Distribuição por Grupo RFM")
                if "GRUPO RFM" in df_filtrado.columns and not df_filtrado["GRUPO RFM"].dropna().empty:
                    graf2 = px.pie(df_filtrado, names="GRUPO RFM", title="Grupos RFM")
                    graf2.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                    st.plotly_chart(graf2, use_container_width=True)
                else:
                    st.info("Sem dados de GRUPO RFM.")
            with colg2:
                st.subheader("Vendas por Produto")
                if "PRODUTO" in df_filtrado.columns:
                    vendas_prod = df_filtrado.groupby("PRODUTO", as_index=False)["VALOR (R$)"].sum().sort_values("VALOR (R$)", ascending=False)
                    if not vendas_prod.empty:
                        graf3 = px.bar(vendas_prod, x="PRODUTO", y="VALOR (R$)", title="Total de Vendas por Produto")
                        graf3.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
                        graf3.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                        st.plotly_chart(graf3, use_container_width=True)
                    else:
                        st.info("Sem dados de produtos.")
                else:
                    st.info("Coluna 'PRODUTO' não encontrada.")

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
# 🔵 ABA 2 — Histórico Geral (mantém gráficos transacionais quando aplicável)
# ======================================================
with aba2:
    st.subheader("📑 Histórico Geral de Clientes")
    if df_historico.empty:
        st.info("Sem dados na Planilha 2.")
    else:
        if modo_planilha2.startswith("Resumo"):
            receita_total = float(df_historico["VALOR_PAD"].sum())
            total_compras = int(df_historico["N_COMPRAS"].sum())
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

        else:
            # Transacional: mantém filtros e gráficos antigos
            st.sidebar.header("🔎 Filtros (Histórico transacional)")
            min_data = pd.to_datetime(df_historico["DATA_REF"]).min()
            max_data = pd.to_datetime(df_historico["DATA_REF"]).max()
            if pd.isna(min_data) or pd.isna(max_data):
                min_data = datetime.today() - timedelta(days=180)
                max_data = datetime.today()
            periodo = st.sidebar.date_input("Período (Histórico)", value=(min_data.date(), max_data.date()))

            prod_col = "PRODUTO_PAD" if "PRODUTO_PAD" in df_historico.columns else None
            prod_opts = sorted(df_historico[prod_col].dropna().unique().tolist()) if prod_col else []
            produtos_hist = st.sidebar.multiselect("Produto (Histórico)", prod_opts) if prod_col else []

            df_hist_filt = df_historico.copy()
            if isinstance(periodo, tuple) and len(periodo) == 2:
                di, df_ = periodo
                di = datetime.combine(di, datetime.min.time())
                df_ = datetime.combine(df_, datetime.max.time())
                df_hist_filt = df_hist_filt[(df_hist_filt["DATA_REF"] >= di) & (df_hist_filt["DATA_REF"] <= df_)]
            if prod_col and produtos_hist:
                df_hist_filt = df_hist_filt[df_hist_filt[prod_col].isin(produtos_hist)]

            total_geral = float(df_hist_filt["VALOR_PAD"].sum())
            clientes_geral = int(df_hist_filt["CLIENTE_ID"].nunique())
            pedidos_geral = int(df_hist_filt.shape[0])
            aov = total_geral / pedidos_geral if pedidos_geral > 0 else 0.0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Receita (período)", f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            k2.metric("🧑‍🤝‍🧑 Clientes únicos", clientes_geral)
            k3.metric("🧾 Pedidos", pedidos_geral)
            k4.metric("🧮 Ticket médio (AOV)", f"R$ {aov:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            st.subheader("📈 Recência e Frequência")
            rf = (df_hist_filt.sort_values("DATA_REF")
                  .groupby("CLIENTE_ID")
                  .agg(ultima_compra=("DATA_REF","max"), n_pedidos=("CLIENTE_ID","count"), ltv=("VALOR_PAD","sum"))
                  .reset_index())
            if not rf.empty:
                rf["dias_desde_ultima"] = (datetime.today() - rf["ultima_compra"]).dt.days
                colA, colB = st.columns(2)
                with colA:
                    top_ltv = rf.sort_values("ltv", ascending=False).head(15)
                    st.markdown("**Top 15 LTV (período filtrado)**")
                    st.dataframe(top_ltv[["CLIENTE_ID","ltv","n_pedidos","ultima_compra"]], use_container_width=True)
                with colB:
                    hist_freq = rf["n_pedidos"].value_counts().reset_index()
                    hist_freq.columns = ["Número de pedidos","Clientes"]
                    graf_freq = px.bar(hist_freq, x="Número de pedidos", y="Clientes", title="Distribuição de Frequência de Compra")
                    graf_freq.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                    st.plotly_chart(graf_freq, use_container_width=True)

            st.subheader("🔁 Primeira compra vs. recorrente")
            if not df_hist_filt.empty:
                primeira = df_hist_filt.sort_values(["CLIENTE_ID","DATA_REF"]).drop_duplicates("CLIENTE_ID", keep="first")
                ids_primeira_periodo = set(primeira["CLIENTE_ID"])
                ids_todos = set(df_hist_filt["CLIENTE_ID"])
                recorrentes = len(ids_todos - ids_primeira_periodo)
                primeiro = len(ids_primeira_periodo)
                p1, p2 = st.columns(2)
                p1.metric("🆕 Primeira compra (no período)", primeiro)
                p2.metric("🔁 Recorrentes (no período)", recorrentes)

            st.subheader("🏆 Top Produtos (Histórico)")
            if prod_col and not df_hist_filt.empty:
                top_prod = (df_hist_filt.groupby(prod_col, as_index=False)["VALOR_PAD"].sum()
                            .sort_values("VALOR_PAD", ascending=False).head(15))
                graf_top = px.bar(top_prod, x=prod_col, y="VALOR_PAD", title="Top Produtos por Receita")
                graf_top.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
                graf_top.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                st.plotly_chart(graf_top, use_container_width=True)

            st.markdown("---")
            st.caption("Prévia do histórico bruto (50 linhas)")
            st.dataframe(df_hist_filt.head(50), use_container_width=True)
