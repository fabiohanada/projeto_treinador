import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

MEU_ID = "7b606745-96e8-446f-8576-a18a3b4abf30"

def gerar_treinos_ficticios():
    # Simulando treinos dos últimos 4 dias
    treinos = [
        {"duracao": 30, "fc": 140, "dias_atras": 4},
        {"duracao": 50, "fc": 150, "dias_atras": 3},
        {"duracao": 20, "fc": 130, "dias_atras": 2},
        {"duracao": 60, "fc": 160, "dias_atras": 1},
    ]

    for t in treinos:
        data_fake = (datetime.now() - timedelta(days=t['dias_atras'])).isoformat()
        
        # Inserindo direto com um TRIMP estimado para o teste
        payload = {
            "id_atleta": MEU_ID,
            "duracao_min": t['duracao'],
            "fc_media": t['fc'],
            "trimp_score": t['duracao'] * 1.5, # Simplificado para o seed
            "data_treino": data_fake
        }
        supabase.table("atividades_fisicas").insert(payload).execute()
    
    print("✅ Histórico de 4 dias gerado com sucesso!")

if __name__ == "__main__":
    gerar_treinos_ficticios()