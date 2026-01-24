import os
from dotenv import load_dotenv
from supabase import create_client
import math

load_dotenv()

# Conexão
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def processar_e_salvar_treino(id_atleta, duracao, fc_media):
    # 1. Busca os dados fisiológicos do atleta no banco (Folha 1)
    atleta = supabase.table("perfis_atletas").select("*").eq("id_user", id_atleta).single().execute()
    
    if not atleta.data:
        print("Atleta não encontrado!")
        return

    dados = atleta.data
    fc_repouso = dados['fc_repouso']
    fc_maxima = dados['fc_maxima']
    sexo = dados['sexo']

    # 2. Cálculo do TRIMP (Folha 2)
    fc_reserva = (fc_media - fc_repouso) / (fc_maxima - fc_repouso)
    k = 1.92 if sexo == 'M' else 1.67
    trimp_score = duracao * fc_reserva * (0.64 * math.exp(k * fc_reserva))
    trimp_score = round(trimp_score, 2)

    # 3. Salva na tabela de atividades (Onde a Folha 2 ganha vida)
    novo_treino = {
        "id_atleta": id_atleta,
        "duracao_min": duracao,
        "fc_media": fc_media,
        "trimp_score": trimp_score
    }

    try:
        res = supabase.table("atividades_fisicas").insert(novo_treino).execute()
        print(f"✅ Treino salvo com sucesso no banco de dados!")
        print(f"📊 Esforço Calculado: {trimp_score} TRIMP")
    except Exception as e:
        print(f"❌ Erro ao salvar treino: {e}")

if __name__ == "__main__":
    # COLOQUE O SEU ID AQUI:
    MEU_ID = "7b606745-96e8-446f-8576-a18a3b4abf30"
    
    # Simulando um treino intenso de 45 minutos
    processar_e_salvar_treino(MEU_ID, duracao=45, fc_media=165)