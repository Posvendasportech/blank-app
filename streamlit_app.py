import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st

# ============================
# Configurações iniciais
# ============================
st.set_page_config(page_title="Dashboard de Vendas", layout="wide")

# ============================
# Conexão com Google Sheets
# ============================
credenciais_json = os.getenv("PLANILHA_CRM_POSVENDAS")  # variável secret do GitHub

if not credenciais_json:
    st.error("⚠️ Variável PLANILHA_CRM_POSVENDAS não encontrada. Verifique secrets do repositório.")
else:
    credenciais_dict = json.loads(credenciais_json)
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(credenciais_dict, scopes=scope)
    client = gspread.authorize(creds)

    # Abrir planilha e carregar dados
    try:
        sheet = client.open("Controle de Vendas").worksheet("Base")
        dados = sheet.get_all_records()
        df = pd.DataFrame(dados)

        # Selecionar apenas as colunas desejadas: A=0, B=1, I=8
        df = df.iloc[:, [0,1,8]]
        df.columns = ["Data", "Classificacao", "Valor"]

        # Converter tipos corretos
        df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

        st.success("✅ Dados carregados com sucesso!")

    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        df = pd.DataFrame(columns=["Data","Classificacao","Valor"])

# ============================
# Cabeçalho estilizado
# ============================
st.markdown("""
<div style="background-color:#4B8BBE; padding:25px; border-radius:10px; text-align:center;">
    <h1 style="color:white; font-family:sans-serif;">📊 Dashboard de Vendas e Pós-Vendas</h1>
    <p style="color:white; font-size:16px;">Controle e visualize todas suas vendas em um só lugar</p>
</div>
""", unsafe_allow_html=True)

# ============================
# Cards de métricas
# ============================
if not df.empty:
    total_vendas = len(df)
    receita_total = df["Valor"].sum()
    num_classificacoes = df["Classificacao"].nunique()

    st.markdown(f"""
    <div style="display:flex; justify-content:space-around; margin-top:20px; gap:20px;">
        <div style="background-color:#4B8BBE; padding:20px; border-radius:10px; flex:1; text-align:center;">
            <h3>Total de Vendas</h3>
            <p style="font-size:28px; font-weight:bold;">{total_vendas}</p>
        </div>
        <div style="background-color:#57d9ff; padding:20px; border-radius:10px; flex:1; text-align:center;">
            <h3>Receita Total</h3>
            <p style="font-size:28px; font-weight:bold;">R$ {receita_total:,.2f}</p>
        </div>
        <div style="background-color:#ff6b6b; padding:20px; border-radius:10px; flex:1; text-align:center;">
            <h3>Classificações Únicas</h3>
            <p style="font-size:28px; font-weight:bold;">{num_classificacoes}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================
# Seção de filtros (visual)
# ============================
st.markdown("""
<div style="background-color:#e0e0e0; padding:15px; border-left:5px solid #4B8BBE; margin-top:30px;">
    <h3 style="margin-bottom:10px;">🔍 Filtros de análise</h3>
    <p>Filtre os dados por Classificação ou Data para analisar suas vendas.</p>
</div>
""", unsafe_allow_html=True)

# ============================
# Tabela de vendas
# ============================
st.markdown("""
<div style="margin-top:30px; background-color:#f0f0f0; padding:15px; border-radius:10px;">
<h3 style="margin-bottom:15px;">📋 Vendas Recentes</h3>
</div>
""", unsafe_allow_html=True)

if not df.empty:
    st.dataframe(df, use_container_width=True)

# ============================
# Gráfico de receita por classificação
# ============================
st.markdown("<h3>📊 Receita por Classificação</h3>", unsafe_allow_html=True)

if not df.empty:
    receita_por_classificacao = df.groupby("Classificacao")["Valor"].sum().reset_index()
    st.bar_chart(data=receita_por_classificacao.set_index("Classificacao"))
