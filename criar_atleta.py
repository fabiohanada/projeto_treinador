import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def cadastrar_atleta_teste():
    atleta = {
        "nome": "Seu Nome de Atleta",
        "sexo": "M",  # Use 'M' ou 'F'
        "fc_repouso": 55,
        "fc_maxima": 190,
        "id_strava": "12345678", # Um ID fictício por enquanto
        "assinatura_ativa": True
    }

    try:
        # Insere e retorna o registro criado
        response = supabase.table("perfis_atletas").insert(atleta).execute()
        
        if response.data:
            id_gerado = response.data[0]['id_user']
            print(f"✅ Atleta cadastrado com sucesso!")
            print(f"🆔 ID do Atleta (Guarde este código): {id_gerado}")
            return id_gerado
    except Exception as e:
        print(f"❌ Erro ao cadastrar: {e}")

if __name__ == "__main__":
    cadastrar_atleta_teste()