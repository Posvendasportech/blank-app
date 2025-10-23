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

# ------------------------------
# 🧩 Funções utilitárias
# ------------------------------
@st.cache_data(ttl=120)
def carregar_csv(url: str) -> pd.DataFrame:
    """Carrega CSV remoto e tenta corrigir cabeçalho 'torto' (muitos 'Unnamed')."""
    # Leitura padrão
    df = pd.read_csv(
        url,
        sep=",",
        engine="python",
        on_bad_lines="skip",
        encoding="utf-8",
        na_values=["", "NA", "NaN", None],
    )

    # Se metade ou mais das colunas são 'Unnamed', promover linha adequada a header
    def _fix_header(_df: pd.DataFrame) -> pd.DataFrame:
        unnamed = sum(str(c).startswith("Unnamed") for c in _df.columns)
        if unnamed <= len(_df.columns) // 2:
            return _df  # cabeçalho parece OK

        # Releitura sem header para escolher a melhor linha como cabeçalho
        _raw = pd.read_csv(
            url, sep=",", engine="python", on_bad_lines="skip", encoding="utf-8", header=None
        )

        # Scora as 10 primeiras linhas pela quantidade de células com letras (tendem a ser nomes de colunas)
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


def preparar_df_historico(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara a planilha do histórico: datas/valores/chaves de cliente (detecção por nome ou conteúdo)."""
    if df.empty:
        return df
    df.columns = [c.strip() for c in df.columns]

    # ---- DATA_REF (por nome; se não achar, detecta por conteúdo)
    date_cols_hint = ["DATA", "DATA DA COMPRA", "DATA DE INÍCIO", "DATA VENDA", "DATA/HORA", "DATA HORA"]
    date_col = next((c for c in date_cols_hint if c in df.columns), None)
    if date_col is None:
        best, best_rate = None, 0
        sample = df.head(200)
        for c in df.columns:
            parsed = pd.to_datetime(sample[c], errors="coerce", dayfirst=True)
            rate = parsed.notna().mean()
            if rate > best_rate:
                best, best_rate = c, rate
        date_col = best if best_rate >= 0.40 else None  # precisa ≥ 40% parseável
    df["DATA_REF"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True) if date_col else pd.NaT

    # ---- VALOR_PAD (por nome; se não achar, detecta por conteúdo)
    valor_cols_hint = ["VALOR (R$)", "VALOR", "TOTAL (R$)", "TOTAL", "PREÇO", "PRECO", "AMOUNT", "PRICE"]
    valor_col = next((c for c in valor_cols_hint if c in df.columns), None)
    if valor_col is None:
        money_re = re.compile(r"^\s*(R\$\s*)?[\d\.\,]+(\s*)$")
        best, best_hits = None, -1
        sample = df.head(200)
        for c in df.columns:
            hits = sample[c].astype(str).str.match(money_re).sum()
            if hits > best_hits:
                best, best_hits = c, hits
        valor_col = best

    def to_float(series: pd.Series) -> pd.Series:
        s = series.astype(str)
        s = s.str.replace("\u00A0", " ", regex=False)   # NBSP → espaço
        s = s.str.replace(r"[Rr]\$\s*", "", regex=True) # remove R$
        s = s.str.replace(" ", "", regex=False)

        # Heurística: vírgula é decimal?
        comma_as_decimal = ((s.str.count(",") >= 1) & (s.str.count("\.") >= 0)).mean() >= 0.5
        if comma_as_decimal:
            s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        else:
            s = s.str.replace(",", "", regex=False)

        return pd.to_numeric(s, errors="coerce")

    df["VALOR_PAD"] = to_float(df[valor_col]) if valor_col in df.columns else 0.0
    df["VALOR_PAD"] = df["VALOR_PAD"].fillna(0.0)

    # ---- Identificação de cliente (email > nome; se tiver CPF/ID_CLIENTE, adapte aqui)
    nome_col = next((c for c in ["NOME COMPLETO", "CLIENTE", "NOME", "Nome"] if c in df.columns), None)
    df["CLIENTE_NOME"] = df[nome_col].astype(str).str.strip() if nome_col else ""

    email_col = next((c for c in ["E-MAIL", "EMAIL", "Email", "e-mail"] if c in df.columns), None)
    df["CLIENTE_EMAIL"] = df[email_col].astype(str).str.strip().str.lower() if email_col else ""

    # ID canônico (se tiver CPF/ID, priorize)
    id_col = next((c for c in ["CPF", "ID_CLIENTE", "ID"] if c in df.columns), None)
    if id_col:
        df["CLIENTE_ID"] = df[id_col].astype(str).str.strip()
    else:
        df["CLIENTE_ID"] = df["CLIENTE_EMAIL"].where(df["CLIENTE_EMAIL"] != "", df["CLIENTE_NOME"])

    return df

# Dias da semana (sem domingo)
PT_WEEK_ORDER = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
PT_WEEK_MAP = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}

# ------------------------------
# 📥 Carregamento da PLANILHA 1 (sempre funciona por export CSV)
# ------------------------------
with st.spinner("Carregando Planilha 1 (colaborador)…"):
    df_vendas_raw = carregar_csv(SHEET_URL_1)
df_vendas = preparar_df_vendas(df_vendas_raw.copy())

# ------------------------------
# 🧭 Barra lateral (monta a URL da PLANILHA 2 e só então lê)
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

colaborador = st.sidebar.text_input(
    "👤 Nome do colaborador (rótulo do relatório)",
    value=colab_detectado or ""
)

# ------------------------------
# 📥 Carregamento da PLANILHA 2 (só agora a URL existe)
# ------------------------------
with st.spinner("Carregando Planilha 2 (histórico)…"):
    try:
        df_extra_raw = carregar_csv(SHEET_URL_2)
    except Exception as e:
        # Fallback: se não estiver compartilhada, tente modo "Publicar na Web"
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

df_historico = preparar_df_historico(df_extra_raw.copy())

# Status rápido no topo
ok1 = "✅" if not df_vendas.empty else "⚠️"
ok2 = "✅" if not df_historico.empty else "⚠️"
st.markdown(f"**Planilha 1 (Colaborador):** {ok1}  |  **Planilha 2 (Histórico):** {ok2}")


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
        # 🧩 Filtros (somente da planilha 1)
        # ------------------------------
        st.sidebar.header("🔎 Filtros (Colaborador)")

        grupos_opts = sorted(df_vendas.get("GRUPO RFM", pd.Series(dtype=str)).dropna().unique().tolist())
        produtos_opts = sorted(df_vendas.get("PRODUTO", pd.Series(dtype=str)).dropna().unique().tolist())

        grupos = st.sidebar.multiselect("Grupo RFM", grupos_opts)
        produtos = st.sidebar.multiselect("Produto", produtos_opts)

        # Aplica filtros
        df_filtrado = df_vendas.copy()
        if grupos and "GRUPO RFM" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["GRUPO RFM"].isin(grupos)]
        if produtos and "PRODUTO" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["PRODUTO"].isin(produtos)]

        # ------------------------------
        # 🎯 KPIs Colaborador + Comparativo com Geral
        # ------------------------------
        if df_filtrado.empty:
            st.info("A combinação de filtros não retornou resultados.")
        else:
            total_colab = float(df_filtrado["VALOR (R$)"].sum())
            clientes_colab = int(df_filtrado.get("NOME COMPLETO", pd.Series(dtype=str)).nunique())
            ticket_medio_colab = total_colab / clientes_colab if clientes_colab > 0 else 0.0

            # KPIs do colaborador
            col1, col2, col3 = st.columns(3)
            col1.metric("💰 Vendas do Colaborador", f"R$ {total_colab:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col2.metric("👥 Clientes Únicos", clientes_colab)
            col3.metric("🎯 Ticket Médio", f"R$ {ticket_medio_colab:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            # === NOVO: KPIs do histórico geral, para comparação
            if not df_historico.empty:
                total_geral = float(df_historico["VALOR_PAD"].sum())
                clientes_geral = int(df_historico["CLIENTE_ID"].nunique())
                colA, colB = st.columns(2)
                colA.metric("🌎 Vendas Totais (Geral)", f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                colB.metric("🧑‍🤝‍🧑 Clientes Totais (Geral)", clientes_geral)

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
                        )
                        # Mostra o valor formatado no topo das barras
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
                # Caso o mês anterior não tenha esse dia
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

            # === NOVO: Interseção de clientes (colaborador ∩ histórico geral)
            st.subheader("🔗 Clientes do colaborador dentro do histórico geral")
            if not df_historico.empty:
                df_colab = df_filtrado.copy()
                # Monta o ID na planilha 1 para bater com histórico (AJUSTE SE PRECISAR)
                colunas_email = [c for c in df_colab.columns if c.upper() in ["E-MAIL", "EMAIL"]]
                email_col = colunas_email[0] if colunas_email else None

                df_colab["CLIENTE_NOME"] = df_colab.get("NOME COMPLETO", pd.Series("", index=df_colab.index)).astype(str).str.strip()
                if email_col:
                    df_colab["CLIENTE_EMAIL"] = df_colab[email_col].astype(str).str.strip().str.lower()
                else:
                    df_colab["CLIENTE_EMAIL"] = ""
                df_colab["CLIENTE_ID"] = df_colab["CLIENTE_EMAIL"].where(df_colab["CLIENTE_EMAIL"] != "", df_colab["CLIENTE_NOME"])

                ids_colab = set(df_colab["CLIENTE_ID"].dropna().astype(str))
                df_hist_clientes = df_historico[df_historico["CLIENTE_ID"].isin(ids_colab)]

                total_ltv = df_hist_clientes.groupby("CLIENTE_ID")["VALOR_PAD"].sum().reset_index(name="LTV")
                top_clientes = total_ltv.sort_values("LTV", ascending=False).head(10)

                c1, c2 = st.columns([1, 2])
                c1.metric("Clientes em comum", len(ids_colab & set(df_historico["CLIENTE_ID"])))
                if not top_clientes.empty:
                    c2.dataframe(top_clientes, use_container_width=True)
            else:
                st.info("Sem dados suficientes para cruzar clientes do colaborador com o histórico geral.")

# ======================================================
# 🔵 ABA 2 — HISTÓRICO GERAL (Clientes)
# ======================================================
with aba2:
    st.subheader("📑 Histórico Geral de Clientes")

    if df_historico.empty:
        st.info("Ainda não há dados na planilha de histórico para exibir.")
    else:
        # ------------------------------
        # Filtros da base geral
        # ------------------------------
        st.sidebar.header("🔎 Filtros (Histórico Geral)")

        # Período
        min_data = pd.to_datetime(df_historico["DATA_REF"]).min()
        max_data = pd.to_datetime(df_historico["DATA_REF"]).max()
        if pd.isna(min_data) or pd.isna(max_data):
            min_data = datetime.today() - timedelta(days=180)
            max_data = datetime.today()

        periodo = st.sidebar.date_input(
            "Período (Histórico)",
            value=(min_data.date(), max_data.date())
        )

        # Produto (detecta coluna automaticamente)
        prod_col = None
        for c in ["PRODUTO", "ITEM", "SKU", "DESCRIÇÃO"]:
            if c in df_historico.columns:
                prod_col = c
                break

        prod_opts = sorted(df_historico[prod_col].dropna().unique().tolist()) if prod_col else []
        produtos_hist = st.sidebar.multiselect("Produto (Histórico)", prod_opts) if prod_col else []

        # Aplica filtros
        df_hist_filt = df_historico.copy()
        if isinstance(periodo, tuple) and len(periodo) == 2:
            di, df_ = periodo
            di = datetime.combine(di, datetime.min.time())
            df_ = datetime.combine(df_, datetime.max.time())
            df_hist_filt = df_hist_filt[(df_hist_filt["DATA_REF"] >= di) & (df_hist_filt["DATA_REF"] <= df_)]

        if prod_col and produtos_hist:
            df_hist_filt = df_hist_filt[df_hist_filt[prod_col].isin(produtos_hist)]

        # ------------------------------
        # KPIs gerais
        # ------------------------------
        total_geral = float(df_hist_filt["VALOR_PAD"].sum())
        clientes_geral = int(df_hist_filt["CLIENTE_ID"].nunique())
        pedidos_geral = int(df_hist_filt.shape[0])
        aov = total_geral / pedidos_geral if pedidos_geral > 0 else 0.0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 Receita (período)", f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        k2.metric("🧑‍🤝‍🧑 Clientes únicos", clientes_geral)
        k3.metric("🧾 Pedidos", pedidos_geral)
        k4.metric("🧮 Ticket médio (AOV)", f"R$ {aov:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        # ------------------------------
        # Recência & Frequência (RF) + LTV
        # ------------------------------
        st.subheader("📈 Recência e Frequência")
        rf = (
            df_hist_filt.sort_values("DATA_REF")
            .groupby("CLIENTE_ID")
            .agg(
                ultima_compra=("DATA_REF", "max"),
                n_pedidos=("CLIENTE_ID", "count"),
                ltv=("VALOR_PAD", "sum"),
            )
            .reset_index()
        )
        if not rf.empty:
            rf["dias_desde_ultima"] = (datetime.today() - rf["ultima_compra"]).dt.days
            colA, colB = st.columns(2)

            with colA:
                top_ltv = rf.sort_values("ltv", ascending=False).head(15)
                st.markdown("**Top 15 LTV (período filtrado)**")
                st.dataframe(top_ltv[["CLIENTE_ID", "ltv", "n_pedidos", "ultima_compra"]], use_container_width=True)

            with colB:
                hist_freq = rf["n_pedidos"].value_counts().reset_index()
                hist_freq.columns = ["Número de pedidos", "Clientes"]
                graf_freq = px.bar(hist_freq, x="Número de pedidos", y="Clientes", title="Distribuição de Frequência de Compra")
                graf_freq.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
                st.plotly_chart(graf_freq, use_container_width=True)

        # ------------------------------
        # Primeira vs recorrente
        # ------------------------------
        st.subheader("🔁 Primeira compra vs. recorrente")
        if not df_hist_filt.empty:
            primeira = df_hist_filt.sort_values(["CLIENTE_ID", "DATA_REF"]).drop_duplicates("CLIENTE_ID", keep="first")
            ids_primeira_periodo = set(primeira["CLIENTE_ID"])
            ids_todos = set(df_hist_filt["CLIENTE_ID"])
            recorrentes = len(ids_todos - ids_primeira_periodo)
            primeiro = len(ids_primeira_periodo)

            p1, p2 = st.columns(2)
            p1.metric("🆕 Clientes de primeira compra (no período)", primeiro)
            p2.metric("🔁 Clientes recorrentes (no período)", recorrentes)

        # ------------------------------
        # Top produtos
        # ------------------------------
        st.subheader("🏆 Top Produtos (Histórico)")
        if prod_col and not df_hist_filt.empty:
            top_prod = (
                df_hist_filt.groupby(prod_col, as_index=False)["VALOR_PAD"]
                .sum()
                .sort_values("VALOR_PAD", ascending=False)
                .head(15)
            )
            graf_top = px.bar(top_prod, x=prod_col, y="VALOR_PAD", title="Top Produtos por Receita")
            graf_top.update_traces(marker_color="cyan", texttemplate="R$ %{y:,.2f}", textposition="outside")
            graf_top.update_layout(plot_bgcolor="black", paper_bgcolor="black", font=dict(color="white"))
            st.plotly_chart(graf_top, use_container_width=True)

        st.markdown("---")
        st.caption("Prévia do histórico bruto (50 primeiras linhas)")
        st.dataframe(df_hist_filt.head(50), use_container_width=True)
