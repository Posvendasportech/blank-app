import streamlit as st
import pandas as pd
from urllib.parse import quote
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import time
import re

# =========================================================
# (1) ⚙️ CONFIGURAÇÃO INICIAL + CSS (INTERFACE DO SISTEMA)
# =========================================================
# Função do bloco:
# - Configura layout do app
# - Injeta CSS para personalização visual
# - Define tema escuro, cards, tabelas e fontes

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
</style>
""", unsafe_allow_html=True)



# =========================================================
# (2) 🔑 CONEXÃO + FUNÇÕES UTILITÁRIAS (NÚCLEO)
# =========================================================
# Função do bloco:
# - Criar cliente Google Sheets
# - Fazer conversões de valor, dias, telefone
# - Funções auxiliares globais usadas por todo o sistema

SHEET_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
SHEET_NAME = "Total"

@st.cache_resource
def get_gsheet_client():
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
    except:
        return None

def safe_valor(v):
    try:
        if pd.isna(v):
            return "—"
        v = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return f"R$ {float(v):.2f}"
    except:
        return "—"

def valor_num(v):
    try:
        if pd.isna(v):
            return None
        v = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(v)
    except:
        return None

def limpar_telefone(v):
    return re.sub(r"\D", "", str(v))



# =========================================================
# (3) 💾 FUNÇÕES DE CARREGAMENTO (BASES)
# =========================================================
# Função do bloco:
# - Carregar planilha TOTAL
# - Carregar AGENDAMENTOS_ATIVOS
# - Carregar HISTORICO
# - Manter cache para performance

@st.cache_data(ttl=60)
def load_sheet(sheet_id, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    return pd.read_csv(url)

@st.cache_data(ttl=60)
def load_agendamentos_ativos():
    try:
        client = get_gsheet_client()
        ws = client.open("Agendamentos").worksheet("AGENDAMENTOS_ATIVOS")
        return set(ws.col_values(5)[1:])
    except:
        return set()

@st.cache_data(ttl=5)
def load_df_agendamentos():
    try:
        client = get_gsheet_client()
        ws = client.open("Agendamentos").worksheet("AGENDAMENTOS_ATIVOS")
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_historico():
    try:
        client = get_gsheet_client()
        ws = client.open("Agendamentos").worksheet("HISTORICO")
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [c.replace(" ", "_") for c in df.columns]
        return df
    except:
        return pd.DataFrame()



# =========================================================
# (4) 🧠 ESTADO DA SESSÃO
# =========================================================
# Função do bloco:
# - Concluídos da sessão
# - Pulados da sessão
# - Pilha reversível para voltar clientes

def init_session_state():
    if "concluidos" not in st.session_state:
        st.session_state["concluidos"] = set()

    if "pulados" not in st.session_state:
        st.session_state["pulados"] = set()

    if "historico_stack" not in st.session_state:
        st.session_state["historico_stack"] = []



# =========================================================
# (5) 🎨 COMPONENTE CARD DE ATENDIMENTO
# =========================================================
# Onde editar:
# - Campos que aparecem no card
# - Estética ou personalização
# - Inputs de resumo, motivo, próxima data

def card_component(id_fix, row):
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)

        dias_txt = f"{row['Dias_num']} dias desde compra" if pd.notna(row["Dias_num"]) else "Sem informação"

        st.markdown(f"""
            <div class="card-header">
                <b>{row['Cliente']}</b><br>
                📱 {row['Telefone']}<br>
                🏷 {row['Classificação']}<br>
                💰 {safe_valor(row['Valor'])}<br>
                ⏳ {dias_txt}
            </div>
        """, unsafe_allow_html=True)

        vendedor = st.selectbox("Responsável", ["João", "Maria", "Patrick", "Outro"], key=f"vend_{id_fix}")
        motivo = st.text_input("Motivo do contato", key=f"mot_{id_fix}")
        resumo = st.text_area("Resumo da conversa", key=f"res_{id_fix}", height=80)
        proxima = st.date_input("Próxima data", key=f"dt_{id_fix}")

        col1, col2 = st.columns(2)
        acao = None

        if col1.button("✅ Registrar e concluir", key=f"ok_{id_fix}"):
            acao = "concluir"

        if col2.button("⏭ Pular cliente", key=f"skip_{id_fix}"):
            acao = "pular"

        st.markdown("</div>", unsafe_allow_html=True)

    return acao, motivo, resumo, proxima, vendedor



# =========================================================
# (6) 🧾 AÇÕES — SALVAR, REMOVER, REGISTRAR
# =========================================================
# Onde alterar:
# - Mudança no formato de registro no Google Sheets
# - Editar o que vai para o histórico / agendamento

def remover_card(telefone, concluido=True):
    telefone = str(telefone)
    if concluido:
        st.session_state["concluidos"].add(telefone)
    else:
        st.session_state["pulados"].add(telefone)

    st.session_state["historico_stack"].append(telefone)


def registrar_agendamento(row, comentario, motivo, proxima_data, vendedor):
    try:
        client = get_gsheet_client()
        sh = client.open("Agendamentos")
        ws_ag = sh.worksheet("AGENDAMENTOS_ATIVOS")
        ws_hist = sh.worksheet("HISTORICO")

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        ws_hist.append_row([
            agora, row["Cliente"], row["Classificação"],
            safe_valor(row["Valor"]), row["Telefone"],
            comentario, motivo, proxima_data, vendedor
        ], value_input_option="USER_ENTERED")

        if proxima_data:
            ws_ag.append_row([
                agora, row["Cliente"], row["Classificação"],
                safe_valor(row["Valor"]), row["Telefone"],
                comentario, motivo, proxima_data, vendedor
            ], value_input_option="USER_ENTERED")

        load_agendamentos_ativos.clear()
        load_df_agendamentos.clear()
        load_historico.clear()

        st.success("✅ Agendamento registrado!")
    except Exception as e:
        st.error(f"Erro ao registrar: {e}")



# =========================================================
# (7) 🧱 SIDEBAR — FILTROS + METAS + CONTROLES DE SESSÃO
# ---------------------------------------------------------
# Função:
# - Renderiza toda a barra lateral (filtros, controles, metas)
# - Retorna dois dicionários:
#     filtros = usados no build_daily_tasks_df()
#     metas   = usadas na montagem das metas e seleção de clientes
#
# ONDE ALTERAR:
# - Quer mudar filtros? -> mexa na parte "BLOCO 1 — FILTROS"
# - Quer mudar os botões de controle? -> "BLOCO 2 — CONTROLES"
# - Quer mudar metas padrão? -> "BLOCO 3 — METAS DO DIA"
# =========================================================
def render_sidebar():
    with st.sidebar:

        # ===========================
        # BLOCO 1 — FILTROS AVANÇADOS
        # ===========================
        st.markdown(
            """
            <div style="font-size:18px; font-weight:700; margin-bottom:4px;">
                ⚙️ Filtros avançados
            </div>
            <p style="font-size:12px; color:#bbbbbb; margin-top:0;">
                Ajuste quem aparece na lista de tarefas do dia.
            </p>
            """,
            unsafe_allow_html=True
        )

        # 👉 FILTRO POR DIAS DESDE A COMPRA
        min_dias = st.number_input("Mínimo de dias desde a última compra", min_value=0, value=0)
        max_dias = st.number_input("Máximo de dias desde a última compra", min_value=0, value=365)

        # 👉 FILTRO POR VALOR
        min_val = st.number_input("Valor mínimo (R$)", value=0.0, min_value=0.0, step=10.0)
        max_val = st.number_input("Valor máximo (R$)", value=1000.0, min_value=0.0, step=10.0)

        # 👉 BUSCA POR TELEFONE
        telefone = st.text_input("Buscar por telefone (qualquer parte)").strip()

        st.markdown("<hr>", unsafe_allow_html=True)

        # ===========================
        # BLOCO 2 — CONTROLES DA SESSÃO
        # ===========================
        st.markdown(
            """
            <div style="font-size:16px; font-weight:600; margin-bottom:4px;">
                🔁 Controles da sessão
            </div>
            <p style="font-size:12px; color:#bbbbbb; margin-top:0;">
                Use estes botões para desfazer o último atendimento ou reiniciar a lista.
            </p>
            """,
            unsafe_allow_html=True
        )

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

        st.markdown("<hr>", unsafe_allow_html=True)

        # ===========================
        # BLOCO 3 — METAS DO DIA
        # ===========================
        st.markdown(
            """
            <div style="font-size:16px; font-weight:600; margin-bottom:4px;">
                🎯 Metas do dia
            </div>
            <p style="font-size:12px; color:#bbbbbb; margin-top:0;">
                Defina quantos contatos de cada grupo você quer trabalhar hoje.
            </p>
            """,
            unsafe_allow_html=True
        )

        # 👉 AQUI VOCÊ AJUSTA AS METAS PADRÃO
        meta_novos = st.number_input("Meta: Novos", value=10, min_value=0, step=1)
        meta_prom = st.number_input("Meta: Promissores", value=20, min_value=0, step=1)
        meta_leais = st.number_input("Meta: Leais/Campeões", value=10, min_value=0, step=1)
        meta_risco = st.number_input("Meta: Em risco", value=10, min_value=0, step=1)

    # 🔙 dicionário de filtros que será usado no build_daily_tasks_df()
    filtros = {
        "min_dias": min_dias,
        "max_dias": max_dias,
        "min_valor": min_val,
        "max_valor": max_val,
        "telefone": telefone,
    }

    # 🎯 dicionário de metas usado no cálculo das tarefas
    metas = {
        "meta_novos": meta_novos,
        "meta_prom": meta_prom,
        "meta_leais": meta_leais,
        "meta_risco": meta_risco,
    }

    return filtros, metas




# =========================================================
# (8) 🔍 BUILDER — MONTAR df_dia (o que aparece para atender)
# =========================================================
# Onde alterar:
# - Regras de seleção por classificação
# - Lógica de prioridade
# - Critérios de corte

def build_daily_tasks_df(base, telefones_agendados, filtros, metas):
    base_ck = base[~base["Telefone"].isin(telefones_agendados)].copy()

    novos = base_ck[(base_ck["Classificação"] == "Novo") &
                    (base_ck["Dias_num"].fillna(0) >= 15)].sort_values("Dias_num").head(metas["meta_novos"])

    prom = base_ck[base_ck["Classificação"] == "Promissor"].sort_values("Dias_num", ascending=False).head(metas["meta_prom"])

    leais = base_ck[base_ck["Classificação"].isin(["Leal","Campeão"])].sort_values("Dias_num", ascending=False).head(metas["meta_leais"])

    risco = base_ck[base_ck["Classificação"] == "Em risco"].sort_values("Dias_num").head(metas["meta_risco"])

    frames = []

    for df in [novos, prom, leais, risco]:
        if not df.empty:
            frames.append(df)

    df_dia = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=base.columns)

    df_dia["ID"] = df_dia["Telefone"].astype(str)

    ocultos = st.session_state["concluidos"].union(st.session_state["pulados"])
    df_dia = df_dia[~df_dia["Telefone"].isin(ocultos)]

    df_dia = df_dia[df_dia["Dias_num"].fillna(0).between(filtros["min_dias"], filtros["max_dias"])]
    df_dia = df_dia[df_dia["Valor_num"].fillna(0).between(filtros["min_valor"], filtros["max_valor"])]

    if filtros["telefone"]:
        clean = limpar_telefone(filtros["telefone"])
        df_dia = df_dia[df_dia["Telefone"].str.contains(clean)]

    return df_dia



# =========================================================
# (9) 🖥️ UI — ABAS PRINCIPAIS
# =========================================================
# Onde alterar:
# - Comportamento visual das abas
# - O que aparece em cada aba

# ----------- ABA 1 -----------
def render_aba1(aba, df_dia, metas):
    with aba:
        st.header("📅 Tarefas do dia")

        colA, colB = st.columns(2)

        with colA:
            st.subheader("🎯 Metas do Dia (Resumo)")
            st.write(metas)

        with colB:
            st.subheader("📊 Quantidade encontrada")
            st.write(len(df_dia))

        st.markdown("---")

        st.subheader("🔄 Modo de Atendimento")
        modo = st.selectbox("Selecione:", ["Check-in", "Agendamentos"])

        if modo == "Check-in":
            if df_dia.empty:
                st.success("🎉 Nenhum cliente pendente!")
                return

            for i in range(0, len(df_dia), 2):
                col1, col2 = st.columns(2)

                row = df_dia.iloc[i]
                with col1:
                    acao, motivo, resumo, proxima, vend = card_component(row["ID"], row)

                    if acao == "concluir":
                        if motivo.strip():
                            registrar_agendamento(row, resumo, motivo, proxima.strftime("%d/%m/%Y"), vend)
                            remover_card(row["Telefone"], True)
                            st.rerun()
                        else:
                            st.warning("Motivo obrigatório.")

                    elif acao == "pular":
                        remover_card(row["Telefone"], False)
                        st.rerun()

                if i + 1 < len(df_dia):
                    row2 = df_dia.iloc[i + 1]
                    with col2:
                        acao, motivo, resumo, proxima, vend = card_component(row2["ID"], row2)

                        if acao == "concluir":
                            if motivo.strip():
                                registrar_agendamento(row2, resumo, motivo, proxima.strftime("%d/%m/%Y"), vend)
                                remover_card(row2["Telefone"], True)
                                st.rerun()
                            else:
                                st.warning("Motivo obrigatório.")

                        elif acao == "pular":
                            remover_card(row2["Telefone"], False)
                            st.rerun()

        else:
            st.subheader("📂 Agendamentos Ativos")
            df_ag = load_df_agendamentos()
            if df_ag.empty:
                st.info("Sem agendamentos ativos.")
            else:
                st.dataframe(df_ag, use_container_width=True)



# ----------- ABA 2 -----------
def render_aba2(aba, base, total):
    with aba:
        st.header("📊 Indicadores")

        col1, col2 = st.columns(2)
        col1.metric("Concluídos na sessão", len(st.session_state["concluidos"]))
        col2.metric("Pulados na sessão", len(st.session_state["pulados"]))

        st.subheader("Distribuição por Classificação")
        dfcount = base["Classificação"].value_counts()
        st.bar_chart(dfcount)



# ----------- ABA 3 -----------
def render_aba3(aba):
    with aba:
        st.header("🔎 Pesquisa no Histórico")

        df = load_historico()
        termo = st.text_input("Buscar")

        if termo:
            filt = df[df.apply(lambda x: termo.lower() in str(x).lower(), axis=1)]
            st.dataframe(filt, use_container_width=True)
        else:
            st.info("Digite um termo para pesquisar.")



# =========================================================
# (10) 🚀 MAIN FLOW — EXECUÇÃO DO APP
# =========================================================
# Onde alterar:
# - Ordem de carregamento
# - Comportamento global do app

def main():
    st.title("📅 CRM Sportech – Tarefas do Dia")

    init_session_state()

    df_raw = load_sheet(SHEET_ID, SHEET_NAME)

    df = pd.DataFrame({
        "Data": pd.to_datetime(df_raw.iloc[:,0], errors="coerce"),
        "Cliente": df_raw.iloc[:,1],
        "Email": df_raw.iloc[:,2],
        "Valor": df_raw.iloc[:,3],
        "Telefone": df_raw.iloc[:,4].astype(str),
        "Compras": df_raw.iloc[:,5],
        "Classificação": df_raw.iloc[:,6],
        "Dias_num": df_raw.iloc[:,8].apply(converte_dias),
    })
    df["Valor_num"] = df["Valor"].apply(valor_num)

    telefones_ag = load_agendamentos_ativos()

    filtros, metas = render_sidebar()

    df_dia = build_daily_tasks_df(df, telefones_ag, filtros, metas)

    aba1, aba2, aba3 = st.tabs([
        "📅 Tarefas do dia",
        "📊 Indicadores",
        "🔎 Histórico"
    ])

    render_aba1(aba1, df_dia, metas)
    render_aba2(aba2, df, len(df_dia))
    render_aba3(aba3)


if __name__ == "__main__":
    main()
