import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from datetime import datetime
from twilio.rest import Client # Certifique-se que 'twilio' está no requirements.txt

# 1. Configurações e Conexão
load_dotenv()
st.set_page_config(page_title="Elite Performance Dashboard", layout="wide")

# Conectar ao Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Credenciais Strava
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÃO DE ENVIO DE SMS (TWILIO) ---
def enviar_aviso_twilio(mensagem):
    try:
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        phone_from = os.getenv("TWILIO_PHONE_NUMBER")
        phone_to = os.getenv("MY_PHONE_NUMBER")
        
        if sid and token:
            client = Client(sid, token)
            message = client.messages.create(
                body=mensagem,
                from_=phone_from,
                to=phone_to
            )
            return True
    except Exception as e:
        st.error(f"Erro ao enviar SMS: {e}")
    return False

# --- FUNÇÃO DE SINCRONIZAÇÃO ---
def sincronizar_atividades(strava_id, access_token):
    url_atividades = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        atividades = requests.get(url_atividades, headers=headers, params={'per_page': 5}).json()
        if isinstance(atividades, list):
            for atividade in atividades:
                payload = {
                    "id_atleta": int(strava_id),
                    "data_treino": atividade['start_date_local'],
                    "trimp_score": atividade['moving_time'] / 60,
                    "distancia": atividade['distance'] / 1000,
                    "duracao": int(atividade['moving_time'] / 60),
                    "tipo_esporte": atividade['type']
                }
                # Ao fazer upsert, o banco ignora se já existir
                supabase.table("atividades_fisicas").upsert(payload, on_conflict="id_atleta, data_treino").execute()
            
            # EXEMPLO: Enviar SMS ao terminar a sincronização
            enviar_aviso_twilio(f"🚀 Treinos de {strava_id} sincronizados no Dashboard!")
            return True
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")
    return False

# --- LÓGICA DE LOGIN ---
if "code" in st.query_params:
    code = st.query_params["code"]
    try:
        response = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "code": code, "grant_type": "authorization_code"
        }).json()
        if 'access_token' in response:
            user_data = {
                "strava_id": response['athlete']['id'],
                "nome": response['athlete']['firstname'],
                "access_token": response['access_token'],
                "refresh_token": response['refresh_token'],
                "expires_at": response['expires_at']
            }
            supabase.table("usuarios").upsert(user_data).execute()
            sincronizar_atividades(user_data["strava_id"], user_data["access_token"])
            st.rerun()
    except Exception as e:
        st.error(f"Erro no login: {e}")

# --- BARRA LATERAL ---
st.sidebar.title("🚀 Menu")
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.link_button("🟠 Conectar Strava", auth_url)

atleta_id = None
token_atleta = None
try:
    usuarios = supabase.table("usuarios").select("*").execute()
    if usuarios.data:
        opcoes = {u['nome']: u['strava_id'] for u in usuarios.data}
        nome_sel = st.sidebar.selectbox("👤 Atleta", list(opcoes.keys()))
        atleta_id = opcoes[nome_sel]
        token_atleta = next(u['access_token'] for u in usuarios.data if u['strava_id'] == atleta_id)
except:
    pass

if atleta_id and st.sidebar.button("🔄 Sincronizar Agora"):
    if sincronizar_atividades(atleta_id, token_atleta):
        st.sidebar.success("Atualizado!")
        st.rerun()

# --- ÁREA PRINCIPAL ---
st.title("📊 Painel de Controle de Carga")

if atleta_id:
    res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(atleta_id)).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')

        # Cálculos ACWR
        df['Aguda'] = df['trimp_score'].rolling(window=7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(window=28, min_periods=1).mean()
        df['ACWR'] = df['Aguda'] / df['Cronica']

        # Métricas
        m1, m2, m3 = st.columns(3)
        ultimo_acwr = df['ACWR'].iloc[-1]
        
        with m1:
            st.metric("ACWR Atual", f"{ultimo_acwr:.2f}")
        with m2:
            status = "✅ Seguro" if 0.8 <= ultimo_acwr <= 1.3 else "⚠️ Risco"
            st.metric("Status", status)
            # AVISO SMS AUTOMÁTICO DE RISCO
            if ultimo_acwr > 1.3 and st.sidebar.button("Enviar Alerta de Risco"):
                enviar_aviso_twilio(f"🚨 ALERTA: Carga Crítica ({ultimo_acwr:.2f}) para {nome_sel}. Risco de lesão!")

        with m3:
            st.metric("Total Treinos", len(df))

        # Gráfico
        fig_carga, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df['data_treino'], df['Aguda'], label="Carga Aguda", color="#1E90FF")
        ax.plot(df['data_treino'], df['Cronica'], label="Carga Crônica", color="#FF4500", ls="--")
        ax.fill_between(df['data_treino'], 0.8 * df['Cronica'], 1.3 * df['Cronica'], color='green', alpha=0.1)
        ax.legend()
        st.pyplot(fig_carga)

    else:
        st.info("Sem atividades. Clique em 'Sincronizar Agora'.")
