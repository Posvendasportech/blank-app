import os
import streamlit as st

credenciais_json = os.getenv("PLANILHA_CRM_POSVENDAS")

if not credenciais_json:
    st.error("⚠️ A variável PLANILHA_CRM_POSVENDAS não está definida!")
else:
    st.success("✅ Variável encontrada e pronta para uso")
