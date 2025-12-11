import streamlit as st
import pandas as pd
from urllib.parse import quote
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import time
import re

# =========================================================
# ⚙️ 1. CONFIGURAÇÃO INICIAL E CSS
# =========================================================
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #000000;
    color: #FFFFFF;
}

/* Remove bordas padrão de expander */
.streamlit-expanderHeader {
    background-color: #111 !important;
}

/* Ajuste tabelas */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* Cards */
.card {
    background-color: #101010;
    border: 1px solid #222;
    border-radius: 16px;
    padding: 18px;
    color: white;
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
    margin-bottom: 18px;
}

.card-header {
    background: linear-gradient(135deg, #0A40B0, #183b8c);
    padding: 14px;
    border-radius: 12px;
    font-size: 16px;
    margin-bottom: 14px;
    line-height: 1.5;
}

.card-title {
    margin-top: 8px;
    color: #cccccc;
    font-size: 14px;
    font-weight: 600;
}

.input-box {
    width: 100%;
    padding: 8px;
    border-radius: 8px;
    border: 1px solid #444;
    background-color: #1b1b1b;
    color: white;
    margin-top: 4px;
}

.submit-btn {
    margin-top: 12px;
    width: 100%;
    background-color: #0A40B0;
    color: white;
    padding: 10px;
    border-radius: 8px;
    text-align: center;
    font-weight: bold;
    cursor: pointer;
}

.submit-btn:hover {
    filter: brightness(1.15);
}

.small-label {
    font-size: 12px;
    color: #bbbbbb;
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# 🔑 2. UTILITÁRIOS & CONEXÃO (MODULAR)
# =========================================================

SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"


@st.cache_resource
def get_gsheet_client():
    """Cliente autenticado do Google Sheets (cacheado como recurso)."""
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(credentials)


def converte_dias(v):
    try:
        return int(round(float(str(v).replace(",", "."))))
    except Exception:
        return None


def safe_valor(v):
    try:
        if pd.isna(v):
            return "—"
        v = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return f"R$ {float(v):.2f}"
    except Exception:
        return "—"


def valor_num(v):
    try:
        if pd.isna(v):
            return None
        v = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(v)
    except Exception:
        return None


def limpar_telefone(v):
    return re.sub(r"\D", "", str(v))


# =========================================================
# 💾 3. FUNÇÕES DE CARREGAMENTO (BASE, AGENDAMENTOS, HISTÓRICO)
# =========================================================
@st.cache_data(ttl=60)
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)


@st.cache_data(ttl=60)
def load_agendamentos_ativos():
    """Carrega os telefones dos clientes que já estão sendo trabalhados."""
    try:
        client = get_gsheet_client()
        sh = client.open("Agendamentos")
        ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
        telefones = ws_ag.col_values(5)[1:]  # pula cabeçalho
        return set(telefones)
    except Exception as e:
        st.warning(f"Não foi possível carregar agendamentos ativos: {e}", icon="⚠️")
        return set()


@st.cache_data(ttl=5)
def load_df_agendamentos():
    """Carrega o DataFrame completo dos Agendamentos Ativos para exibição na Aba 1."""
    try:
        client = get_gsheet_client()
        sh = client.open("Agendamentos")
        ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
        data = ws_ag.get_all_records()
        df_ag = pd.DataFrame(data)
        return df_ag
    except Exception as e:
        st.error(f"Erro ao carregar Agendamentos Ativos: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def load_historico():
    """Carrega o histórico de contatos."""
    try:
        client = get_gsheet_client()
        sh = client.open("Agendamentos")
        ws_hist = sh.worksheet("HISTORICO")
        data = ws_hist.get_all_records()
        df_hist_local = pd.DataFrame(data)
        df_hist_local.columns = [col.replace(" ", "_") for col in df_hist_local.columns]
        return df_hist_local
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return pd.DataFrame()


# =========================================================
# 🧠 4. ESTADO DA SESSÃO
# =========================================================
def init_session_state():
    if "concluidos" not in st.session_state:
        st.session_state["concluidos"] = set()

    if "pulados" not in st.session_state:
        st.session_state["pulados"] = set()

    if "historico_stack" not in st.session_state:
        st.session_state["historico_stack"] = []


# =========================================================
# 🎨 5. COMPONENTE DE CARD DE ATENDIMENTO
# =========================================================
def card_component(id_fix, row):
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)

        dias_txt = (
            f"{row['Dias_num']} dias desde compra"
            if pd.notna(row["Dias_num"])
            else "Sem informação de dias"
        )

        st.markdown(
            f"""
            <div class="card-header">
                <b>{row['Cliente']}</b><br>
                📱 {row['Telefone']}<br>
                🏷 {row['Classificação']}<br>
                💰 {safe_valor(row['Valor'])}<br>
                ⏳ {dias_txt}
            </div>
            """,
            unsafe_allow_html=True
        )

        vendedor = st.selectbox(
            "Responsável",
            ["João", "Maria", "Patrick", "Outro"],
            key=f"vend_{id_fix}"
        )

        motivo = st.text_input("Motivo do contato", key=f"mot_{id_fix}")
        resumo = st.text_area("Resumo da conversa", key=f"res_{id_fix}", height=80)
        proxima = st.date_input("Próxima data", key=f"dt_{id_fix}")

        colA, colB = st.columns(2)
        acao = None

        with colA:
            if st.button("✅ Registrar e concluir", key=f"ok_{id_fix}"):
                acao = "concluir"

        with colB:
            if st.button("⏭ Pular cliente", key=f"skip_{id_fix}"):
                acao = "pular"

        st.markdown("</div>", unsafe_allow_html=True)

    return acao, motivo, resumo, proxima, vendedor


# =========================================================
# 🧾 6. AÇÕES: REMOVER CARD & REGISTRAR AGENDAMENTO
# =========================================================
def remover_card(telefone, concluido=True):
    tel = str(telefone)
    if concluido:
        st.session_state["concluidos"].add(tel)
    else:
        st.session_state["pulados"].add(tel)
    st.session_state["historico_stack"].append(tel)


def registrar_agendamento(row, comentario, motivo, proxima_data, vendedor):
    """
    Registra contato no HISTORICO e, se tiver próxima_data, em AGENDAMENTOS_ATIVOS.
    Inclui tratamento de erro e limpeza de cache específica.
    """
    try:
        client = get_gsheet_client()
        sh = client.open("Agendamentos")
        ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
        ws_hist = sh.worksheet("HISTORICO")

        time.sleep(0.5)

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        # HISTORICO (A → I)
        ws_hist.append_row([
            agora,
            row["Cliente"],
            row["Classificação"],
            safe_valor(row["Valor"]),
            row["Telefone"],
            comentario,
            motivo,
            proxima_data,
            vendedor
        ], value_input_option="USER_ENTERED")

        time.sleep(0.5)

        # AGENDAMENTOS_ATIVOS (A → I)
        if proxima_data:
            ws_ag.append_row([
                agora,
                row["Cliente"],
                row["Classificação"],
                safe_valor(row["Valor"]),
                row["Telefone"],
                comentario,
                motivo,
                proxima_data,
                vendedor
            ], value_input_option="USER_ENTERED")

        # Limpa apenas caches relacionados a agendamentos/histórico
        try:
            load_agendamentos_ativos.clear()
            load_df_agendamentos.clear()
            load_historico.clear()
        except Exception:
            st.cache_data.clear()

        st.success("✅ Agendamento registrado com sucesso!")

    except Exception as e:
        st.error(f"❌ Erro ao registrar agendamento: {e}")


# =========================================================
# 🧱 7. SIDEBAR: FILTROS + METAS + CONTROLES DE SESSÃO
# =========================================================
def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Filtros avançados")

        min_dias = st.number_input("Mínimo de dias desde a última compra", min_value=0, value=0)
        max_dias = st.number_input("Máximo de dias desde a última compra", min_value=0, value=365)

        min_valor = st.number_input("Valor mínimo (R$)", min_value=0.0, value=0.0, step=10.0)
        max_valor = st.number_input("Valor máximo (R$)", min_value=0.0, value=1000.0, step=10.0)

        telefone_busca = st.text_input("Buscar por telefone (qualquer parte)").strip()

        st.markdown("---")
        st.markdown("### 🔁 Controles da sessão")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("↩ Voltar último cliente"):
                if st.session_state["historico_stack"]:
                    ultimo = st.session_state["historico_stack"].pop()
                    st.session_state["concluidos"].discard(ultimo)
                    st.session_state["pulados"].discard(ultimo)
                st.rerun()
        with col_s2:
            if st.button("🧹 Resetar sessão"):
                st.session_state["concluidos"] = set()
                st.session_state["pulados"] = set()
                st.session_state["historico_stack"] = []
                st.rerun()

        st.markdown("---")
        st.markdown("### 🎯 Metas do Dia")

        meta_novos = st.number_input("Meta: Novos", value=10, min_value=0)
        meta_prom = st.number_input("Meta: Promissores", value=20, min_value=0)
        meta_leais = st.number_input("Meta: Leais/Campeões", value=10, min_value=0)
        meta_risco = st.number_input("Meta: Em risco", value=10, min_value=0)

    filtros = {
        "min_dias": min_dias,
        "max_dias": max_dias,
        "min_valor": min_valor,
        "max_valor": max_valor,
        "telefone_busca": telefone_busca,
    }

    metas = {
        "meta_novos": meta_novos,
        "meta_prom": meta_prom,
        "meta_leais": meta_leais,
        "meta_risco": meta_risco,
    }

    return filtros, metas


# =========================================================
# 🔍 8. FUNÇÃO CENTRAL: MONTAR df_dia (TAREFAS DO DIA)
# =========================================================
def build_daily_tasks_df(base, telefones_agendados, filtros, metas):
    base_para_checkin = base[~base["Telefone"].isin(telefones_agendados)].copy()

    # Seleção por classificação + metas (RFM simplificado)
    novos = base_para_checkin[
        (base_para_checkin["Classificação"] == "Novo") &
        (base_para_checkin["Dias_num"].fillna(0) >= 15)
    ].copy()
    novos = novos.sort_values("Dias_num", ascending=True).head(metas["meta_novos"])

    prom = base_para_checkin[base_para_checkin["Classificação"] == "Promissor"].copy()
    prom = prom.sort_values("Dias_num", ascending=False).head(metas["meta_prom"])

    leal_camp = base_para_checkin[
        base_para_checkin["Classificação"].isin(["Leal", "Campeão"])
    ].copy()
    leal_camp = leal_camp.sort_values("Dias_num", ascending=False).head(metas["meta_leais"])

    risco = base_para_checkin[base_para_checkin["Classificação"] == "Em risco"].copy()
    risco = risco.sort_values("Dias_num", ascending=True).head(metas["meta_risco"])

    frames = []
    if not novos.empty:
        novos["Grupo"] = "Novo"
        frames.append(novos)
    if not prom.empty:
        prom["Grupo"] = "Promissor"
        frames.append(prom)
    if not leal_camp.empty:
        leal_camp["Grupo"] = "Leal/Campeão"
        frames.append(leal_camp)
    if not risco.empty:
        risco["Grupo"] = "Em risco"
        frames.append(risco)

    if frames:
        df_dia = pd.concat(frames, ignore_index=True)
    else:
        df_dia = base_para_checkin.head(0).copy()
        df_dia["Grupo"] = pd.Series(dtype=str)

    df_dia["ID"] = df_dia["Telefone"].astype(str)

    # Remove concluídos/pulados da sessão
    todos_ocultos = st.session_state["concluidos"].union(st.session_state["pulados"])
    df_dia = df_dia[~df_dia["Telefone"].isin(todos_ocultos)]

    # Filtros de dias e valor
    df_dia = df_dia[
        df_dia["Dias_num"].fillna(0).between(filtros["min_dias"], filtros["max_dias"])
    ]
    df_dia = df_dia[
        df_dia["Valor_num"].fillna(0).between(filtros["min_valor"], filtros["max_valor"])
    ]

    # Filtro por telefone
    df_dia["Telefone_limpo"] = df_dia["Telefone"].astype(str).apply(limpar_telefone)
    telefone_busca = filtros["telefone_busca"]
    if telefone_busca:
        tel_busca_limpo = limpar_telefone(telefone_busca)
        if tel_busca_limpo:
            df_dia = df_dia[df_dia["Telefone_limpo"].str.contains(tel_busca_limpo, na=False)]
        else:
            df_dia = df_dia[df_dia["Telefone"].str.contains(telefone_busca, na=False)]

    # Contadores
    count_novos = len(df_dia[df_dia["Classificação"] == "Novo"])
    count_prom = len(df_dia[df_dia["Classificação"] == "Promissor"])
    count_leais = len(df_dia[df_dia["Classificação"].isin(["Leal", "Campeão"])])
    count_risco = len(df_dia[df_dia["Classificação"] == "Em risco"])
    total_tarefas = len(df_dia)

    contadores = {
        "count_novos": count_novos,
        "count_prom": count_prom,
        "count_leais": count_leais,
        "count_risco": count_risco,
        "total_tarefas": total_tarefas,
    }

    return df_dia, contadores


# =========================================================
# 🖥️ 9. UI – ABAS
# =========================================================
def render_aba1(aba, df_dia, metas):
    with aba:
        st.header("📅 Tarefas do dia")

        # Visão geral das metas & contagem atual
        colA, colB = st.columns([2, 2])

      # =========================================================
# 🎯 METAS DO DIA (AJUSTÁVEIS NA ABA 1)
# =========================================================
# =========================================================
# 🎯 METAS DO DIA (AJUSTÁVEIS NA ABA 1)
# =========================================================

colA, colB = st.columns([2, 2])

with colA:
    st.subheader("🎯 Seleção de Contatos do Dia")

    # Inicializa metas no session_state (caso ainda não existam)
    if "meta_novos" not in st.session_state:
        st.session_state["meta_novos"]  = metas["meta_novos"]
        st.session_state["meta_prom"]   = metas["meta_prom"]
        st.session_state["meta_leais"]  = metas["meta_leais"]
        st.session_state["meta_risco"]  = metas["meta_risco"]

    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    st.session_state["meta_novos"] = c1.number_input(
        "Novos do dia",
        value=st.session_state["meta_novos"],
        min_value=0,
        step=1
    )

    st.session_state["meta_prom"] = c2.number_input(
        "Promissores do dia",
        value=st.session_state["meta_prom"],
        min_value=0,
        step=1
    )

    st.session_state["meta_leais"] = c3.number_input(
        "Leais/Campeões do dia",
        value=st.session_state["meta_leais"],
        min_value=0,
        step=1
    )

    st.session_state["meta_risco"] = c4.number_input(
        "Em risco do dia",
        value=st.session_state["meta_risco"],
        min_value=0,
        step=1
    )

    # Atualiza o dicionário metas
    metas["meta_novos"] = st.session_state["meta_novos"]
    metas["meta_prom"] = st.session_state["meta_prom"]
    metas["meta_leais"] = st.session_state["meta_leais"]
    metas["meta_risco"] = st.session_state["meta_risco"]


with colB:
    st.subheader("📊 Resumo da Seleção Atual")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Novos", len(df_dia[df_dia["Classificação"] == "Novo"]))
    c2.metric("Promissores", len(df_dia[df_dia["Classificação"] == "Promissor"]))
    c3.metric("Leais/Campeões", len(df_dia[df_dia["Classificação"].isin(["Leal","Campeão"])]))
    c4.metric("Em risco", len(df_dia[df_dia["Classificação"] == "Em risco"]))

        st.markdown("---")

        modo_filtro = st.selectbox(
            "Modo de atendimento",
            ["Clientes para Check-in (Base de Leitura)", "Agendamentos Ativos"],
            key="modo_filtro_aba1"
        )

        st.markdown("---")

        # ================= MODO 1 – CHECK-IN =================
        if modo_filtro == "Clientes para Check-in (Base de Leitura)":
            class_filter = st.radio(
                "Filtrar por classificação:",
                ["Todos", "Novo", "Promissor", "Leal", "Campeão", "Em risco", "Dormente"],
                horizontal=True
            )

            df_checkin = df_dia.copy()
            if class_filter != "Todos":
                df_checkin = df_checkin[df_checkin["Classificação"] == class_filter]

            if df_checkin.empty:
                st.success("🎉 Tudo certo! Nenhum cliente pendente dentro dos filtros definidos.")
                return

            st.subheader("📌 Atendimentos do dia (Check-in)")

            csv = (
                df_checkin.drop(columns=["Telefone_limpo"], errors="ignore")
                .to_csv(index=False)
                .encode("utf-8-sig")
            )
            st.download_button(
                "📥 Baixar lista do dia (CSV)",
                data=csv,
                file_name="tarefas_checkin_dia.csv",
                mime="text/csv"
            )

            st.markdown("---")

            # Renderiza cards (2 por linha)
            for i in range(0, len(df_checkin), 2):
                col1, col2 = st.columns(2)

                # Card 1
                row1 = df_checkin.iloc[i]
                id1 = row1["ID"]

                with col1:
                    acao, motivo, resumo, proxima, vendedor = card_component(id1, row1)

                    if acao == "concluir":
                        if motivo.strip():
                            proxima_str = proxima.strftime("%d/%m/%Y") if proxima else ""
                            registrar_agendamento(row1, resumo, motivo, proxima_str, vendedor)
                            remover_card(row1["Telefone"], concluido=True)
                            st.rerun()
                        else:
                            st.warning("⚠️ Preencha o motivo do contato antes de concluir.", icon="🚨")

                    elif acao == "pular":
                        remover_card(row1["Telefone"], concluido=False)
                        st.rerun()

                # Card 2 (se existir)
                if i + 1 < len(df_checkin):
                    row2 = df_checkin.iloc[i + 1]
                    id2 = row2["ID"]

                    with col2:
                        acao2, motivo2, resumo2, proxima2, vendedor2 = card_component(id2, row2)

                        if acao2 == "concluir":
                            if motivo2.strip():
                                proxima2_str = proxima2.strftime("%d/%m/%Y") if proxima2 else ""
                                registrar_agendamento(row2, resumo2, motivo2, proxima2_str, vendedor2)
                                remover_card(row2["Telefone"], concluido=True)
                                st.rerun()
                            else:
                                st.warning("⚠️ Preencha o motivo do contato antes de concluir.", icon="🚨")

                        elif acao2 == "pular":
                            remover_card(row2["Telefone"], concluido=False)
                            st.rerun()

        # ================= MODO 2 – AGENDAMENTOS ATIVOS =================
        else:
            st.subheader("📂 Clientes com próximos contatos agendados")

            df_ag = load_df_agendamentos()

            if df_ag.empty:
                st.success("🎉 Nenhum agendamento pendente!")
                return

            cols_show = [
                "Data de chamada",
                "Nome",
                "Telefone",
                "Follow up",
                "Data de contato",
                "Relato da conversa"
            ]

            existing_cols = [c for c in cols_show if c in df_ag.columns]

            if not existing_cols:
                st.error("❌ A planilha AGENDAMENTOS_ATIVOS não contém as colunas esperadas.")
                return

            if "Data de chamada" in existing_cols:
                df_ag["Data de chamada"] = pd.to_datetime(df_ag["Data de chamada"], errors="ignore")
                df_ag = df_ag.sort_values("Data de chamada", ascending=True)

            st.dataframe(df_ag[existing_cols], use_container_width=True)
            st.caption("🔄 Lista carregada diretamente da planilha AGENDAMENTOS_ATIVOS.")


def render_aba2(aba, base, total_tarefas):
    with aba:
        st.header("📊 Indicadores de Performance")

        st.subheader("Progresso da Sessão Atual")

        concluidos_hoje = base[base["Telefone"].isin(st.session_state["concluidos"])]

        col_ind1, col_ind2 = st.columns(2)
        col_ind1.metric(
            "Tarefas Concluídas (Sessão)",
            len(concluidos_hoje),
            delta=f"Total na sessão: {len(st.session_state['concluidos'])}"
        )
        col_ind2.metric(
            "Clientes Pulados (Sessão)",
            len(st.session_state["pulados"]),
            delta=f"Tarefas restantes: {total_tarefas}"
        )

        st.markdown("---")

        st.subheader("Distribuição da Base Total por Classificação")
        df_count = base["Classificação"].value_counts().reset_index()
        df_count.columns = ["Classificação", "Quantidade"]

        st.bar_chart(df_count.set_index("Classificação"))


def render_aba3(aba):
    with aba:
        st.header("🔎 Pesquisa de Histórico de Contato")

        df_hist = load_historico()

        termo_busca = st.text_input("Buscar por Telefone ou Nome no Histórico")

        if not df_hist.empty and termo_busca:
            col_nome_hist = "Cliente"
            col_telefone_hist = "Telefone"

            filtro = pd.Series(False, index=df_hist.index)

            if col_telefone_hist in df_hist.columns:
                filtro |= df_hist[col_telefone_hist].astype(str).str.contains(
                    termo_busca, case=False, na=False
                )

            if col_nome_hist in df_hist.columns:
                filtro |= df_hist[col_nome_hist].astype(str).str.contains(
                    termo_busca, case=False, na=False
                )

            df_filtrado = df_hist[filtro]

            if not df_filtrado.empty:
                st.subheader(f"Histórico para '{termo_busca}'")

                if "Data_de_contato" in df_filtrado.columns:
                    df_filtrado = df_filtrado.sort_values("Data_de_contato", ascending=False)

                st.dataframe(
                    df_filtrado,
                    use_container_width=True
                )
            else:
                st.info("Nenhum registro encontrado no histórico.")
        elif not df_hist.empty:
            st.info("Digite um Nome ou Telefone para pesquisar no histórico de contatos.")


# =========================================================
# 🚀 10. MAIN APP FLOW
# =========================================================
def main():
    st.title("📅 CRM Sportech – Tarefas do Dia")

    init_session_state()

    # Carrega base principal
    df_raw = load_sheet(SHEET_ID, SHEET_NAME)

    # Mapeamento de colunas por índice (mantendo seu padrão atual)
    col_data = df_raw.iloc[:, 0]
    col_nome = df_raw.iloc[:, 1]
    col_email = df_raw.iloc[:, 2]
    col_valor = df_raw.iloc[:, 3]
    col_tel = df_raw.iloc[:, 4]
    col_compras = df_raw.iloc[:, 5]
    col_class = df_raw.iloc[:, 6]
    col_dias = df_raw.iloc[:, 8]

    base = pd.DataFrame({
        "Data": pd.to_datetime(col_data, errors="coerce"),
        "Cliente": col_nome,
        "Email": col_email,
        "Valor": col_valor,
        "Telefone": col_tel.astype(str),
        "Compras": col_compras,
        "Classificação": col_class,
        "Dias_num": col_dias.apply(converte_dias)
    })
    base["Valor_num"] = base["Valor"].apply(valor_num)

    telefones_agendados = load_agendamentos_ativos()

    # Sidebar → filtros + metas
    filtros, metas = render_sidebar()

    # Monta df_dia (tarefas do dia) com base em filtros + metas
    df_dia, contadores = build_daily_tasks_df(base, telefones_agendados, filtros, metas)

    # Tabs principais
    aba1, aba2, aba3 = st.tabs([
        "📅 Tarefas do dia",
        "📊 Indicadores",
        "🔎 Pesquisa de histórico"
    ])

    render_aba1(aba1, df_dia, metas)
    render_aba2(aba2, base, contadores["total_tarefas"])
    render_aba3(aba3)


if __name__ == "__main__":
    main()
