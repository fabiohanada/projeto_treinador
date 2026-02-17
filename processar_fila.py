import time
import requests
import math
from supabase import create_client, Client

# --- CONFIGURAÇÕES DA API (MANTIDAS) ---
CLIENT_ID = '197487' 
CLIENT_SECRET = '2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f'
REFRESH_TOKEN = '66d330e7bbc52f701ca02fc4192b2975269120f8' 

SUPABASE_URL = 'https://gddseopytaabdxmgubzc.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdkZHNlb3B5dGFhYmR4bWd1YnpjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTExNjk2MSwiZXhwIjoyMDg0NjkyOTYxfQ.8R_j1Zg3JB0_VXViRAzYndYmsHJAIyCZN2v3qwk45-4' 

# --- FUNÇÃO DE CÁLCULO TRIMP DINÂMICO ---
def calcular_trimp_personalizado(duracao_minutos, fc_media, fc_max, fc_rep, genero='masculino'):
    if not fc_media or fc_media == 0 or not fc_max or not fc_rep:
        return 0
    
    # Intensidade Relativa (HRR)
    hr_r = (fc_media - fc_rep) / (fc_max - fc_rep)
    
    # Ajuste da constante por gênero (Fórmula de Banister)
    # Masculino: 1.92 | Feminino: 1.67
    k = 1.92 if genero.lower() == 'masculino' else 1.67
    
    trimp = duracao_minutos * hr_r * 0.64 * math.exp(k * hr_r)
    return int(trimp)

def get_strava_token():
    response = requests.post(
        'https://www.strava.com/oauth/token',
        data={'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 
              'refresh_token': REFRESH_TOKEN, 'grant_type': 'refresh_token'}
    )
    return response.json().get('access_token') if response.status_code == 200 else None

def main():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("🤖 Robô v15.0 - Processamento Inteligente Iniciado...")

    # 1. Buscar avisos pendentes
    eventos = supabase.table('webhook_events').select('*').eq('processed', False).execute().data
    
    if not eventos:
        print("💤 Fila vazia.")
        return

    access_token = get_strava_token()
    if not access_token: return

    for evento in eventos:
        data = evento['event_data']
        strava_id = data.get('object_id')
        atleta_strava_id = data.get('owner_id') # ID do aluno no Strava

        if data.get('aspect_type') == 'create' and data.get('object_type') == 'activity':
            print(f"--> Processando treino {strava_id} do atleta {atleta_strava_id}...")
            
            # 2. BUSCAR PERFIL DO ALUNO NO BANCO
            perfil = supabase.table('perfis_atletas').select('*').eq('strava_athlete_id', atleta_strava_id).execute().data
            
            # Valores padrão caso o aluno não tenha configurado o perfil ainda
            fc_max, fc_rep, genero, id_atleta_interno = 190, 60, 'masculino', None
            
            if perfil:
                p = perfil[0]
                fc_max = p.get('fc_maxima', 190)
                fc_rep = p.get('fc_repouso', 60)
                genero = p.get('genero', 'masculino')
                id_atleta_interno = p.get('id_atleta')
            else:
                # Se não achamos perfil pelo ID do Strava, tentamos achar o dono da conta
                print(f"⚠️ Perfil não configurado para o atleta {atleta_strava_id}. Usando padrões.")

            # 3. BUSCAR DADOS NO STRAVA
            headers = {'Authorization': f'Bearer {access_token}'}
            r_strava = requests.get(f'https://www.strava.com/api/v3/activities/{strava_id}', headers=headers)
            
            if r_strava.status_code == 200:
                treino = r_strava.json()
                dur_min = treino['moving_time'] / 60
                
                # --- LÓGICA DE VALOR PADRÃO (v15.1) ---
                # Pegamos o batimento real do Strava
                fc_media_bruta = treino.get('average_heartrate', 0)
                
                # Se for 0 (sem relógio), forçamos 130 bpm para o aluno não ficar sem TRIMP
                if fc_media_bruta == 0:
                    fc_media = 130
                    print(f"   ℹ️ Atleta sem relógio. Usando padrão comercial: {fc_media} bpm")
                else:
                    fc_media = fc_media_bruta
                    print(f"   ❤️ FC Média real detectada: {fc_media} bpm")
                
                # CÁLCULO PERSONALIZADO (usando os 130 fixos ou a FC real)
                trimp = calcular_trimp_personalizado(dur_min, fc_media, fc_max, fc_rep, genero)
                
                # SALVAR NA TABELA OFICIAL (UPSERT)
                novo_treino = {
                    'strava_id': str(treino['id']),
                    'id_atleta': id_atleta_interno,
                    'data_treino': treino['start_date'],
                    'tipo_esporte': treino['type'],
                    'distancia': treino['distance'] / 1000,
                    'duracao': int(dur_min),
                    'trimp_score': trimp,
                    'name': treino['name']
                }
                
                supabase.table('atividades_fisicas').upsert(novo_treino, on_conflict='strava_id').execute()
                print(f"✅ Treino '{treino['name']}' processado com TRIMP {trimp}!")
            
        # Marcar evento como lido
        supabase.table('webhook_events').update({'processed': True}).eq('id', evento['id']).execute()

if __name__ == "__main__":
    main()