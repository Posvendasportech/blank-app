df = load_sheet(SHEET_ID, SHEET_NAME)

# Debug
st.subheader("DEBUG — Verificando colunas da planilha")
st.write("Quantidade de colunas:", len(df.columns))
st.write("Nomes das colunas:", df.columns.tolist())
st.write("Prévia dos dados:")
st.write(df.head())
