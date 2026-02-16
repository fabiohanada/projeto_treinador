import time
import requests
import math
from supabase import create_client, Client

# --- 1. CONFIGURAÇÕES PESSOAIS (AJUSTE AQUI!) ---
FC_MAXIMA = 190   # Sua Frequência Cardíaca Máxima
FC_REPOUSO = 60   # Sua Frequência Cardíaca de Repouso
# ------------------------------------------------

# --- 2. CREDENCIAIS ---
CLIENT_ID = '197487' 
CLIENT_SECRET = '2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f'
REFRESH_TOKEN = '66d330e7bbc52f701ca02fc4192b2975269120f8'  # <--- SEU TOKEN ETERNO

SUPABASE_URL = 'https://gddseopytaabdxmgubzc.supabase.co'
# Use a Service Role Key (aquela que começa com eyJhbGciOiJIUzI1Ni...)
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdkZHNlb3B5dGFhYmR4bWd1YnpjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTExNjk2MSwiZXhwIjoyMDg0NjkyOTYxfQ.8R_j1Zg3JB0_VXViRAzYndYmsHJAIyCZN2v3qwk45-4' 

# Seu ID fixo
MEU_ID_ATLETA = '238ad51a-2e15-4ca2-99e0-57aca51d67d5'

# --- 3. FUNÇÕES ---

def calcular_trimp(duracao_minutos, fc_media):
    """
    Calcula o TRIMP usando o método de Banister.
    TRIMP = Duração(min) * HR_R * 0.64 * e^(1.92 * HR_R)
    Onde HR_R = (FC_Media - FC_Repouso) / (FC_Maxima - FC_Repouso)
    """
    if not fc_media or fc_media == 0:
        return 0 # Sem batimentos, sem TRIMP
    
    # Frequência de Reserva (Intensidade relativa)
    hr_r = (fc_media - FC_REPOUSO) / (FC_MAXIMA - FC_REPOUSO)
    
    # Fórmula de Banister (para homens)
    trimp = duracao_minutos * hr_r * 0.64 * math.exp(1.92 * hr_r)
    
    return int(trimp)

def get_strava_token():
    print("🔄 Renovando token...")
    try:
        response = requests.post(
            'https://www.strava.com/oauth/token',
            data={
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'refresh_token': REFRESH_TOKEN,
                'grant_type': 'refresh_token'
            }
        )
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            print("❌ Erro token:", response.text)
            return None
    except Exception as e:
        print(f"❌ Erro conexão: {e}")
        return None

def main():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("🤖 Robô TRIMP v2.0 iniciado...")

    # Buscar eventos não processados
    response = supabase.table('webhook_events')\
        .select('*')\
        .eq('processed', False)\
        .execute()
    
    eventos = response.data
    
    if not eventos:
        print("💤 Nenhum treino novo na fila.")
        return

    print(f"🔥 Processando {len(eventos)} treino(s)...")
    access_token = get_strava_token()
    if not access_token: return

    for evento in eventos:
        data = evento['event_data']
        event_id_banco = evento['id']
        strava_id = data.get('object_id')
        tipo = data.get('aspect_type')
        objeto = data.get('object_type')

        if tipo == 'create' and objeto == 'activity':
            print(f"--> Baixando treino {strava_id}...")
            
            headers = {'Authorization': f'Bearer {access_token}'}
            r_strava = requests.get(
                f'https://www.strava.com/api/v3/activities/{strava_id}',
                headers=headers
            )
            
            if r_strava.status_code == 200:
                treino = r_strava.json()
                
                # Conversões Básicas
                distancia_km = treino['distance'] / 1000
                duracao_min = int(treino['moving_time'] / 60)
                fc_media = treino.get('average_heartrate', 0) # Pega batimentos (se tiver)
                
                # CÁLCULO DO TRIMP
                trimp_calculado = calcular_trimp(duracao_min, fc_media)
                print(f"   ❤️ FC Média: {fc_media} bpm -> TRIMP: {trimp_calculado}")

                novo_treino = {
                    'strava_id': treino['id'],
                    'id_atleta': MEU_ID_ATLETA,
                    'data_treino': treino['start_date'],
                    'tipo_esporte': treino['type'],
                    'distancia': distancia_km,
                    'duracao': duracao_min,
                    
                    # AQUI ENTRA O TRIMP CALCULADO
                    'trimp_score': trimp_calculado,
                    
                    'name': treino['name'],
                    'average_speed': treino['average_speed'],
                    'total_elevation_gain': treino['total_elevation_gain'],
                    'calories': treino.get('calories', 0)
                }

                # Salvar no banco
                supabase.table('atividades_fisicas').insert(novo_treino).execute()
                print(f"✅ Treino salvo com TRIMP!")

            else:
                print(f"⚠️ Erro Strava: {r_strava.status_code}")

        # Marca como lido
        supabase.table('webhook_events')\
            .update({'processed': True})\
            .eq('id', event_id_banco)\
            .execute()
            
    print("🏁 Finalizado.")

if __name__ == "__main__":
    main()