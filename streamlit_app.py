import os

credenciais_json = os.getenv("PLANILHA_CRM_POSVENDAS")

if not credenciais_json:
    import streamlit as st
    st.error("⚠️ A variável PLANILHA_CRM_POSVENDAS não está definida!")
else:
    print("Variável encontrada")
