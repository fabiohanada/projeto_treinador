import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import math
from supabase import create_client
from twilio.rest import Client
import os
import streamlit as st

# ============================================================================
# 🔐 CONFIGURAÇÕES (Lendo do segredo do Streamlit para manter padrão)
# ============================================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

TWILIO_SID = st.secrets["TWILIO_SID"]
TWILIO_TOKEN = st.secrets["TWILIO_TOKEN"]
TWILIO_PHONE_FROM = f"whatsapp:+{st.secrets['TWILIO_PHONE_NUMBER']}"

# Conexão com Supabase
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"⚠️ ERRO ao conectar Supabase: {e}")

# ============================================================================

def calcular_trimp_banister(duracao_min, fc_media, fc_max, fc_repouso=60):
    if not fc_media or fc_media <= 0: return int(duracao_min * 1.5)
    if fc_max <= fc_repouso: fc_max = 190
    reserva = (fc_media - fc_repouso) / (fc_max - fc_repouso)
    try:
        trimp = duracao_min * reserva * 0.64 * math.exp(1.92 * reserva)
        return int(trimp)
    except: return int(duracao_min * 1.5)

def buscar_fc_maxima(atleta_id):
    try:
        res = supabase.table("usuarios_app").select("data_nascimento").eq("id", atleta_id).execute()
        if res.data and res.data[0].get('data_nascimento'):
            ano_nasc = int(res.data[0]['data_nascimento'].split('-')[0])
            return 220 - (datetime.now().year - ano_nasc)
    except: pass
    return 190

def enviar_whatsapp_robo(dados, telefone):
    try:
        import re
        apenas_numeros = re.sub(r'\D', '', str(telefone))
        if len(apenas_numeros) <= 11: apenas_numeros = "55" + apenas_numeros
        to_number = f"whatsapp:+{apenas_numeros}"

        client = Client(TWILIO_SID, TWILIO_TOKEN)
        
        # Lógica de Manutenção vs Treino
        if dados.get("manutencao"):
            corpo_msg = "🤖 *DataPace Online*\nSistema monitorando seu Strava ativamente! ✅"
        else:
            corpo_msg = (
                f"🤖 *Novo Treino Detectado!*\n\n"
                f"🏃‍♂️ {dados['name']}\n"
                f"📏 {dados['distancia']:.2f} km\n"
                f"⏱️ {dados['duracao']} min\n"
                f"❤️ Carga (TRIMP): *{dados['trimp_score']}*"
            )
        
        msg = client.messages.create(body=corpo_msg, from_=TWILIO_PHONE_FROM, to=to_number)
        return True
    except Exception as e:
        print(f"❌ Erro Zap: {e}")
        return False

def processar_novos_treinos(user_id_especifico=None):
    """Busca treinos novos e renova o acesso ao Strava automaticamente se necessário."""
    print(f"🤖 Escaneando Strava... {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        query = supabase.table("auth_strava").select("*")
        if user_id_especifico:
            query = query.eq("user_id", user_id_especifico)
        
        usuarios = query.execute().data
        if not usuarios: return

        for u in usuarios:
            user_id = u['user_id']
            token = u['access_token']
            agora = time.time()

            # 🚀 LÓGICA DE RENOVAÇÃO AUTOMÁTICA (Refresh Token)
            # Se o token expirar em menos de 10 minutos, pedimos um novo.
            if u.get('expires_at') and agora > (u['expires_at'] - 600):
                print(f"🔄 Renovando acesso para o usuário {user_id}...")
                try:
                    res_refresh = requests.post("https://www.strava.com/api/v3/oauth/token",
                        data={
                            'client_id': st.secrets["STRAVA_CLIENT_ID"],
                            'client_secret': st.secrets["STRAVA_CLIENT_SECRET"],
                            'refresh_token': u['refresh_token'],
                            'grant_type': 'refresh_token'
                        }).json()
                    
                    if 'access_token' in res_refresh:
                        token = res_refresh['access_token']
                        # Atualiza o banco com as novas chaves
                        supabase.table("auth_strava").update({
                            "access_token": token,
                            "refresh_token": res_refresh.get('refresh_token', u['refresh_token']),
                            "expires_at": res_refresh.get('expires_at')
                        }).eq("user_id", user_id).execute()
                        print(f"✅ Token renovado com sucesso!")
                except Exception as e:
                    print(f"❌ Falha crítica ao renovar token de {user_id}: {e}")
                    continue 

            # Busca atividades com o token (novo ou antigo ainda válido)
            headers = {'Authorization': f'Bearer {token}'}
            after_date = int((datetime.now() - timedelta(days=2)).timestamp())
            
            try:
                url = f"https://www.strava.com/api/v3/athlete/activities?after={after_date}"
                atividades = requests.get(url, headers=headers).json()
                
                if isinstance(atividades, list):
                    fc_max_real = buscar_fc_maxima(user_id)
                    for act in atividades:
                        strava_id = str(act['id'])
                        existe = supabase.table("atividades_fisicas").select("id").eq("strava_id", strava_id).execute()
                        
                        if not existe.data:
                            dist = act.get('distance', 0) / 1000
                            dur_min = int(act.get('moving_time', 0) / 60)
                            trimp = calcular_trimp_banister(dur_min, act.get('average_heartrate', 0), fc_max_real)
                            
                            novo_treino = {
                                "id_atleta": user_id, "strava_id": strava_id,
                                "tipo_esporte": act['type'], "distancia": dist,
                                "duracao": dur_min, "data_treino": act['start_date_local'][:10],
                                "name": act.get('name', 'Treino'), "trimp_score": trimp
                            }
                            
                            supabase.table("atividades_fisicas").insert(novo_treino).execute()
                            
                            # Busca o telefone e avisa via WhatsApp
                            u_info = supabase.table("usuarios_app").select("telefone").eq("id", user_id).execute()
                            if u_info.data and u_info.data[0].get('telefone'):
                                enviar_whatsapp_robo(novo_treino, u_info.data[0]['telefone'])
                                
            except Exception as e:
                print(f"Erro na API Strava para o usuário {user_id}: {e}")
                
    except Exception as e:
        print(f"Erro geral no processamento: {e}")

if __name__ == "__main__":
    # Quando rodar o arquivo diretamente pelo terminal
    while True:
        processar_novos_treinos()
        print("💤 Aguardando 5 min para a próxima verificação...")
        time.sleep(300)