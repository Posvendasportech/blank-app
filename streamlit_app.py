st.subheader("DEBUG — Verificando colunas da planilha")

st.write("Quantidade de colunas:", len(df.columns))
st.write("Nomes das colunas:", df.columns.tolist())
st.write(df.head())
