# streamlit_app.py 
import streamlit as st
import pandas as pd
from urllib.parse import quote

# ----------------------------------------
# ⚙️ Configuração da página
# ----------------------------------------
st.set_page_config(page_title="CRM Sportech", page_icon="📅", layout="wide")

# ----------------------------------------
# 🔗 IDs / padrões das planilhas
# ----------------------------------------
SHEET2_ID = "1UD2_Q9oua4OCqYls-Is4zVKwTc9LjucLjPUgmVmyLBc"
DEFAULT_SHEET2_SHEETNAME = "Total"

# ----------------------------------------
# 📌 Função para carregar planilhas
# ----------------------------------------
@st.cache_data
def load_sheet(sheet_id, sheet_name):
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?"
        f"tqx=out:csv&sheet={quote(sheet_name)}"
    )
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        return pd.DataFrame()

# ----------------------------------------
# 📌 Carregar planilha de leads
# ----------------------------------------
df_leads = load_sheet(SHEET2_ID, DEFAULT_SHEET2_SHEETNAME)

# ----------------------------------------
# 📌 Título da página
# ----------------------------------------
st.title("📅 Tarefas do Dia – CRM Sportech")

if df_leads.empty:
    st.warning("⚠️ A planilha de leads não pôde ser carregada.")
else:
    st.subheader("Lista de tarefas (baseada na planilha de leads)")

    # ----------------------------------------
    # 📝 Mapeamento das colunas por índice
    # ----------------------------------------
    col_data = df_leads.iloc[:, 0]          # A - Data
    col_nome = df_leads.iloc[:, 1]          # B - Nome
    col_email = df_leads.iloc[:, 2]         # C - Email
    col_valor = df_leads.iloc[:, 3]         # D - Valor total gasto
    col_telefone = df_leads.iloc[:, 4]      # E - Telefone
    col_compras = df_leads.iloc[:, 5]       # F - Nº de compras
    col_classificacao = df_leads.iloc[:, 6] # G - Classificação

    # ----------------------------------------
    # 🛠 Criar a lista de tarefas iniciais
    # ----------------------------------------
    df_tasks = pd.DataFrame({
        "Cliente": col_nome.head(10),
        "Telefone": col_telefone.head(10),
        "Compras": col_compras.head(10),
        "Total gasto": col_valor.head(10),
        "Classificação": col_classificacao.head(10),
        "Tarefa": ["Check-in inicial"] * 10,
        "Prioridade": ["Alta"] * 10,
        "Status": ["Pendente"] * 10
    })

    # ----------------------------------------
    # 🖥️ Exibir cada tarefa com botão de concluir
    # ----------------------------------------
    for idx, row in df_tasks.iterrows():
        cols = st.columns([2, 2, 1, 1, 2, 1, 1])  # Layout de colunas

        cols[0].write(row["Cliente"])
        cols[1].write(row["Telefone"])
        cols[2].write(row["Compras"])
        cols[3].write(f"R$ {row['Total gasto']}")
        cols[4].write(row["Tarefa"])
        cols[5].write(row["Prioridade"])
        cols[6].write(row["Status"])

        # Botão de concluir tarefa
        if cols[6].button("Concluir", key=f"done_{idx}"):
            st.success(
                f"✔️ Tarefa concluída para: {row['Cliente']} ({row['Telefone']})"
            )
            # Depois, aqui vamos remover da lista e registrar na planilha de agendamentos
