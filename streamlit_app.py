import os
import json
import gspread
from google.oauth2.service_account import Credentials

credenciais_json = os.getenv("PLANILHA_CRM_POSVENDAS")
credenciais_dict = json.loads(credenciais_json)

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(credenciais_dict, scopes=scope)
client = gspread.authorize(creds)

sheet = client.open("Controle de Vendas").worksheet("Base")
dados = sheet.get_all_records()
print(f"Planilha carregada com {len(dados)} linhas.")
