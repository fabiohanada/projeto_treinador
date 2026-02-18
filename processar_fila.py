import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import math
from supabase import create_client
from twilio.rest import Client # <--- Importante: Instale com 'pip install twilio' se der erro
import os

# ============================================================================
# 🔐 CONFIGURAÇÕES DE CREDENCIAIS (PREENCHA AQUI)
# ============================================================================
# Copie esses valores do seu arquivo .streamlit/secrets.toml

# 1. SUPABASE
SUPABASE_URL = 'https://gddseopytaabdxmgubzc.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdkZHNlb3B5dGFhYmR4bWd1YnpjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTExNjk2MSwiZXhwIjoyMDg0NjkyOTYxfQ.8R_j1Zg3JB0_VXViRAzYndYmsHJAIyCZN2v3qwk45-4'

# 2. TWILIO (WHATSAPP)
TWILIO_SID = "ACa4021ac5afa057dcfcfdd0126fbfaa2e"
TWILIO_TOKEN = "18ee37a12b39555c915fcfe3f914390e"
TWILIO_PHONE_FROM = "whatsapp:+14155238886" # Ou o seu número oficial

# ============================================================================

# Conexão com Supabase
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    print("⚠️ ERRO: Configure as credenciais do Supabase no topo do arquivo!")
    exit()

def calcular_trimp_banister(duracao_min, fc_media, fc_max, fc_repouso=60):
    """ Cálculo Científico de TRIMP (Banister) """
    if not fc_media or fc_media <= 0:
        return int(duracao_min * 1.5)
        
    if fc_max <= fc_repouso: fc_max = 190
    b = 1.92
    reserva = (fc_media - fc_repouso) / (fc_max - fc_repouso)
    
    try:
        trimp = duracao_min * reserva * 0.64 * math.exp(b * reserva)
        return int(trimp)
    except:
        return int(duracao_min * 1.5)

def buscar_fc_maxima(atleta_id):
    try:
        res = supabase.table("usuarios_app").select("data_nascimento").eq("id", atleta_id).execute()
        if res.data and res.data[0].get('data_nascimento'):
            nasc_str = res.data[0]['data_nascimento']
            ano_nasc = int(nasc_str.split('-')[0])
            idade = datetime.now().year - ano_nasc
            return 220 - idade
    except:
        pass
    return 190

def enviar_whatsapp_robo(dados, telefone):
    try:
        print(f"📲 Tentando enviar para {telefone}...")
        
        # Limpeza do telefone (Garanta o +55)
        import re
        apenas_numeros = re.sub(r'\D', '', str(telefone))
        if len(apenas_numeros) <= 11: # Se for ex: 11999999999 vira 5511999999999
            apenas_numeros = "55" + apenas_numeros
            
        to_number = f"whatsapp:+{apenas_numeros}"
        
        # Conexão Twilio
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        
        corpo_msg = (
            f"🤖 *Novo Treino Detectado!*\n\n"
            f"🏃‍♂️ {dados['name']}\n"
            f"📏 {dados['distancia']:.2f} km\n"
            f"⏱️ {dados['duracao']} min\n"
            f"❤️ Carga (TRIMP): *{dados['trimp_score']}*"
        )
        
        msg = client.messages.create(
            body=corpo_msg,
            from_=TWILIO_PHONE_FROM,
            to=to_number
        )
        print(f"✅ Sucesso! Message SID: {msg.sid}")
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar Zap: {e}")
        return False

def processar_novos_treinos():
    print("🤖 Robô v16.0 escaneando Strava...")
    
    try:
        # Busca tokens salvos
        usuarios = supabase.table("auth_strava").select("*").execute().data
        
        for u in usuarios:
            user_id = u['user_id']
            token = u['access_token']
            
            # (Opcional) Aqui entraria a lógica de renovar token se expires_at < agora
            
            headers = {'Authorization': f'Bearer {token}'}
            
            # Pega atividades de hoje e ontem (para não pegar histórico muito antigo)
            after_date = int((datetime.now() - timedelta(days=2)).timestamp())
            
            try:
                url = f"https://www.strava.com/api/v3/athlete/activities?after={after_date}"
                atividades = requests.get(url, headers=headers).json()
                
                if isinstance(atividades, list):
                    fc_max_real = buscar_fc_maxima(user_id)
                    
                    for act in atividades:
                        strava_id = str(act['id'])
                        
                        # Verifica duplicidade
                        existe = supabase.table("atividades_fisicas").select("id").eq("strava_id", strava_id).execute()
                        
                        if not existe.data:
                            print(f"⚡ Processando: {act['name']}")
                            
                            dist = act.get('distance', 0) / 1000
                            dur_min = act.get('moving_time', 0) / 60
                            fc_med = act.get('average_heartrate', 0)
                            
                            trimp = calcular_trimp_banister(dur_min, fc_med, fc_max_real)
                            
                            novo_treino = {
                                "id_atleta": user_id,
                                "strava_id": strava_id,
                                "tipo_esporte": act['type'],
                                "distancia": dist,
                                "duracao": int(dur_min),
                                "data_treino": act['start_date_local'][:10],
                                "name": act.get('name', 'Treino'),
                                "trimp_score": trimp
                            }
                            
                            # Salva no banco
                            supabase.table("atividades_fisicas").insert(novo_treino).execute()
                            
                            # Busca telefone e envia
                            user_info = supabase.table("usuarios_app").select("telefone").eq("id", user_id).execute()
                            if user_info.data:
                                fone = user_info.data[0].get('telefone')
                                if fone:
                                    enviar_whatsapp_robo(novo_treino, fone)
            except Exception as e_req:
                print(f"Erro na requisição Strava: {e_req}")
                
    except Exception as e:
        print(f"Erro geral no loop: {e}")

if __name__ == "__main__":
    while True:
        processar_novos_treinos()
        print("💤 Dormindo 5 minutos...") # Rápido para teste
        time.sleep(300)