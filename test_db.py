import os
from dotenv import load_dotenv
from supabase import create_client

# Carrega as variáveis do arquivo .env
load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

# Inicializa o cliente do Supabase
supabase = create_client(url, key)

# Tenta ler a tabela para ver se a conexão está OK
try:
    response = supabase.table("perfis_atletas").select("*").execute()
    print("✅ Conexão com Supabase funcionando!")
    print(f"Dados atuais: {response.data}")
except Exception as e:
    print(f"❌ Erro na conexão: {e}")