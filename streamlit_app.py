# streamlit_app.py
import streamlit as st
import pandas as pd
import time
import plotly.express as px
import plotly.graph_objects as go
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
# Planilha 1 (vendas de UM colaborador) — já no formato export CSV
SHEET_URL_1 = "https://docs.google.com/spreadsheets/d/1d07rdyAfCzyV2go0V4CJkXd53wUmoA058WeqaHfGPBk/export?format=csv"

# Planilha 2 (histórico geral de TODOS os clientes)
SHEET2_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
DEFAULT_SHEET2_SHEETNAME = "Total"  # altere se sua aba tiver outro nome

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

        _raw = pd.read_csv(
            url, sep=",", engine="python", on_bad_lines="skip", encoding="utf-8", header=None
        )
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

    df = _fix_header(df)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _to_float_brl(series: pd.Series) -> pd.Series:
    """Converte 'R$ 1.234,56' / '1.234,56' / '1234.56' em float."""
    s = series.astype(str)
    s = s.str.replace("\u00A0", " ", regex=False)          # NBSP
    s = s.str.replace(r"[Rr]\$\s*", "", regex=True)        # remove R$
    s = s.str.replace(" ", "", regex=False)                # remove espaços
    # Heurística: vírgula como decimal?
    comma_as_decimal = ((s.str.count(",") >= 1) & (s.str.count("\.") >= 0)).mean() >= 0.5
    if comma_as_decimal:
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    else:
        s = s.str.replace(",", "", regex=False)
    return pd.to_numeric(s, errors="coerce")


def preparar_df_vendas(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara a planilha do colaborador: datas e valores."""
    if df.empty:
        return df
    df.columns = [c.strip() for c in df.columns]

    # DATA
    if "DATA DE INÍCIO" in df.columns:
        df["DATA DE INÍCIO"] = pd.to_datetime(df["DATA DE INÍCIO"], errors="coerce", dayfirst=True)

    # VALOR
    if "VALOR (R$)" in df.columns:
        df["VALOR (R$)"] = (
            df["VALOR (R$)"].astype(str)
            .str.replace(r"R\$\s*", "", regex=True)
            .str.replace(".", "", regex=False)   # milhar
            .str.replace(",", ".", regex=False)  # decimal
        )
        df["VALOR (R$)"] = pd.to_numeric(df["VALOR (R$)"], errors="coerce").fillna(0.0)

    return df


def preparar_df_historico_clientes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara a Planilha 2 como RESUMO POR CLIENTE (uma linha = um cliente).
    Expectativas:
      - Coluna 'Valor'  = gasto total do cliente (BRL)
      - Coluna 'Compras' = número de compras do cliente (inteiro)
    """
    if df.empty:
        return df.copy()

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # localizar colunas por nome (case-insensitive mas prioriza exatamente 'Valor'/'Compras')
    def find_col(df, preferred):
        cols = {c.lower(): c for c in df.columns}
        for p in preferred:
            if p.lower() in cols:
                return cols[p.lower()]
        return None

    col_val = find_col(df, ["Valor"])
    col_cmp = find_col(df, ["Compras"])

    if col_val is None:
        st.error("❌ A planilha 2 não tem a coluna **'Valor'**. Verifique o cabeçalho.")
        df["VALOR_PAD"] = 0.0
    else:
        df["VALOR_PAD"] = _to_float_brl(df[col_val]).fillna(0.0)

    if col_cmp is None:
        st.warning("⚠️ A planilha 2 não tem a coluna **'Compras'**. Usando 0.")
        df["N_COMPRAS"] = 0
    else:
        df["N_COMPRAS"] = pd.to_numeric(df[col_cmp], errors="coerce").fillna(0).astype(int)

    # Identificação de cliente
    nome_col = find_col(df, ["NOME COMPLETO", "CLIENTE", "NOME", "Nome"])
    email_col = find_col(df, ["E-MAIL", "EMAIL", "Email", "e-mail"])

    df["CLIENTE_NOME"] = df[nome_col].astype(str).str.strip() if nome_col else ""
    df["CLIENTE_EMAIL"] = df[email_col].astype(str).str.strip().str.lower() if email_col else ""
    df["CLIENTE_ID"] = df["CLIENTE_EMAIL"].where(df["CLIENTE_EMAIL"] != "", df["CLIENTE_NOME"])

    # nesse formato, não há DATA_REF transacional
    df["DATA_REF"] = pd.NaT
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
df_vendas = preparar_df_vendas(df_vendas_raw.copy())

# ------------------------------
# 🧭 Sidebar / Controles
# ------------------------------
st.sidebar.title("⚙️ Controles")

# Nome da aba da Planilha 2 (evita depender de gid)
sheet2_sheetname = st.sidebar.text_input(
    "📄 Nome da aba (Planilha 2)",
    value=DEFAULT_SHEET2_SHEETNAME,
    help="Ex.: Total (tem que ser exatamente como aparece na guia do Google Sheets)"
)
# Monta a URL por NOME da aba (gviz)
SHEET_URL_2 = f"https://docs.google.com/spreadsheets/d/{SHEET2_ID}/gviz/tq?tqx=out:csv&sheet={quote(sheet2_sheetname)}"

# Botão de refresh
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
    except Exception as e:
        fallback_pub = f"https://docs.google.com/spreadsheets/d/{SHEET2_ID}/pub?output=csv"
        st.warning("Não consegui pela URL da aba. Tentando fallback 'Publicar na Web'…")
        try:
            df_extra_raw = carregar_csv(fallback_pub)
        except Exception as e2:
            st.error(
                "❌ Não consegui abrir a Planilha 2.\n\n"
                "Verifique:\n"
                "• Nome da aba digitado (igual ao do Google Sheets)\n"
                "• Permissões: 'Qualquer pessoa com o link — Leitor'\n"
                "• (Opcional) Arquivo → Compartilhar → Publicar na Web\n\n"
                f"Erros: {e} | fallback: {e2}"
            )
            df_extra_raw = pd.DataFrame()

# Preparo ESPECÍFICO: Valor/Compras (resumo por cliente)
df_historico = preparar_df_historico_clientes(df_extra_raw.copy())

# Status rápido no topo
ok1 = "✅" if isinstance(df_vendas, pd.DataFrame) and not df_vendas.empty else "⚠️"
ok2 = "✅" if isinstance(df_historico, pd.DataFrame) and not df_historico.empty else "⚠️"
st.markdown(f"**Planilha 1 (Colaborador):** {ok1}  |  **Planilha 2 (Histórico):** {ok2}")

# ------------------------------
# 🗂️ Abas principais (criar antes de usar)
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
        # ------------------------------
        # Filtros (somente da planilha 1)
        # ------------------------------
        st.sidebar.header("🔎 Filtros (Colaborador)")
        grupos_opts = sorted(df_vendas.get("GRUPO RFM", pd.Series(dtype=str)).dropna().unique().tolist())
        produtos_opts = sorted(df_vendas.get("PRODUTO", pd.Series(dtype=str)).dropna().unique().tolist())
        grupos = st.sidebar.multiselect("Grupo RFM", grupos_opts)
        produtos = st.sidebar.multiselect("Produto", produtos_opts)

        df_filtrado = df_vendas.copy()
        if grupos and "GRUPO RFM" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["GRUPO RFM"].isin(grupos)]
        if produtos and "PRODUTO" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["PRODUTO"].isin(produtos)]

        if df_filtrado.empty:
            st.info("A combinação de filtros não retornou resultados.")
        else:
            total_colab = float(df_filtrado["VALOR (R$)"].sum())
            clientes_colab = int(df_filtrado.get("NOME COMPLETO", pd.Series(dtype=str)).nunique())
            ticket_medio_colab = total_colab / clientes_colab if clientes_colab > 0 else 0.0

            col1, col2, col3 = st.columns(3)
            col1.metric("💰 Vendas do Colaborador", f"R$ {total_colab:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col2.metric("👥 Clientes Únicos", clientes_colab)
            col3.metric("🎯 Ticket Médio", f"R$ {ticket_medio_colab:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            # Base temporal sem domingo
            base = df_filtrado[df_filtrado["DATA DE INÍCIO"].notna()].copy()
            if not base.empty:
                base = base[base["DATA DE INÍCIO"].dt.weekday != 6]

            # Vendas por dia + tendência
            st.subheader("📊 Vendas por Dia com Linha de Tendência")
            vendas_por_dia = (
                base.groupby("DATA DE INÍCIO", as_index=False)["VALOR (R$)"].sum().sort_values("DATA DE INÍCIO")
            ) if not base.empty else pd.DataFrame()
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
                graf1.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"),
                                    xaxis=dict(showgrid=True, gridcolor="gray"),
                                    yaxis=dict(showgrid=True, gridcolor="gray"))
                st.plotly_chart(graf1, use_container_width=True)
            else:
                st.info("Não há dados de vendas diárias após aplicar filtros.")

            # Distribuição por Grupo RFM e Produto
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
                            vendas_prod, x="PRODUTO", y="VALOR (R$)", title="Total de Vendas por Produto",
                        )
                        graf3.update_traces(
                            marker_color="cyan",
                            texttemplate="R$ %{y:,.2f}",
                            textposition="outside",
                            hovertemplate="<b>%{x}</b><br>Vendas: R$ %{y:,.2f}<extra></extra>"
                        )
                        graf3.update_yaxes(tickformat=",.2f")
                        graf3.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                        st.plotly_chart(graf3, use_container_width=True)
                    else:
                        st.info("Sem dados de produtos após os filtros.")
                else:
                    st.info("Coluna 'PRODUTO' não encontrada na planilha.")

# ======================================================
# 🔵 ABA 2 — HISTÓRICO GERAL (Clientes) — RESUMO POR CLIENTE
# ======================================================
with aba2:
    st.subheader("📑 Histórico Geral de Clientes (Resumo por Cliente)")

    if df_historico.empty:
        st.info("Ainda não há dados na planilha de histórico para exibir.")
    else:
        # KPIs (usando Valor/Compras por cliente)
        receita_total = float(df_historico["VALOR_PAD"].sum()) if "VALOR_PAD" in df_historico.columns else 0.0
        total_compras = int(df_historico["N_COMPRAS"].sum()) if "N_COMPRAS" in df_historico.columns else int(df_historico.shape[0])
        clientes_unicos = int(df_historico["CLIENTE_ID"].nunique()) if "CLIENTE_ID" in df_historico.columns else int(df_historico.shape[0])
        aov = receita_total / total_compras if total_compras > 0 else 0.0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 Receita total (clientes)", f"R$ {receita_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        k2.metric("🧑‍🤝‍🧑 Clientes", clientes_unicos)
        k3.metric("🧾 Nº de compras", total_compras)
        k4.metric("🧮 Ticket médio", f"R$ {aov:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        # Top clientes por Valor gasto
        st.subheader("🏆 Top Clientes por Valor Gasto")
        top_clientes = (
            df_historico[["CLIENTE_ID", "CLIENTE_NOME", "VALOR_PAD", "N_COMPRAS"]]
            .sort_values("VALOR_PAD", ascending=False)
            .head(20)
        )
        graf_top = px.bar(
            top_clientes,
            x="CLIENTE_NOME",
            y="VALOR_PAD",
            title="Top 20 Clientes por Valor Gasto",
        )
        graf_top.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
        graf_top.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
        st.plotly_chart(graf_top, use_container_width=True)

        st.markdown("---")
        st.caption("Prévia do histórico bruto (50 primeiras linhas)")
        st.dataframe(df_historico.head(50), use_container_width=True)
