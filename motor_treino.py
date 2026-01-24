import os
import math
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Conexão
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def calcular_trimp(duracao_min, fc_media, fc_repouso, fc_maxima, sexo):
    """Implementa a fórmula da Folha 2"""
    # 1. Calcular a FC de Reserva
    fc_reserva = (fc_media - fc_repouso) / (fc_maxima - fc_repouso)
    
    # 2. Fator de Intensidade (Constante de Morton)
    # 1.92 para Homens, 1.67 para Mulheres
    k = 1.92 if sexo == 'M' else 1.67
    
    # 3. Cálculo Final do TRIMP
    trimp = duracao_min * fc_reserva * (0.64 * math.exp(k * fc_reserva))
    return round(trimp, 2)

# --- TESTE MANUAL (Simulando um treino do Strava) ---
if __name__ == "__main__":
    # Simulando dados que viriam do Perfil do Atleta (Folha 1)
    DURACAO = 60  # 1 hora de treino
    FC_MEDIA = 155
    FC_REPOUSO = 55
    FC_MAXIMA = 190
    SEXO = 'M'

    score = calcular_trimp(DURACAO, FC_MEDIA, FC_REPOUSO, FC_MAXIMA, SEXO)
    print(f"🚀 Treino Processado! Carga Biológica (TRIMP): {score}")