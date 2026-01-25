import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from datetime import datetime
from twilio.rest import Client

# 1. CONFIGURAÇÕES INICIAIS
load_dotenv()
st.set_page_config(page_title="Elite Performance Dashboard", layout="wide")

def get_secret(key):
    return st.secrets.get(key) or os.getenv(key)

# Conexões
url = get_secret("SUPABASE_URL")
key = get_secret("SUPABASE_KEY")
supabase = create_client(url, key)

CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÃO DE ENVIO DE WHATSAPP ---
def enviar_whatsapp_twilio(mensagem):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        phone_from = get_secret("TWILIO_PHONE_NUMBER")
        phone_to = get_secret("MY_PHONE_NUMBER")
        
        if not all([sid, token, phone_from, phone_to]):
            st.error("❌ Erro: Credenciais do Twilio não configuradas nos Secrets.")
            return False

        client = Client(sid, token)
        p_from = f"whatsapp:{phone_from.replace('whatsapp:', '')}"
        p_to = f"whatsapp:{phone_to.replace('whatsapp:', '')}"

        message = client.messages.create(
            body=mensagem,
            from_=p_from,
            to=p_to
        )
        if message.sid:
            st.toast(f"✅ WhatsApp enviado!", icon="📲")
            return True
    except Exception as e:
        st.error(f"❌ Erro no Twilio: {e}")
        return False

# --- FUNÇÃO DE SINCRONIZAÇÃO COM MENSAGEM PERSONALIZADA ---
def sincronizar_atividades(strava_id, access_token, nome_atleta):
    url_atividades = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        atividades = requests.get(url_atividades, headers=headers, params={'per_page': 5}).json()
        
        if isinstance(atividades, list) and len(atividades) > 0:
            # Dados do treino mais recente para a mensagem
            recente = atividades[0]
            nome_atv = recente.get('name', 'Treino')
            distancia = recente.get('distance', 0) / 1000
            duracao = recente.get('moving_time', 0) / 60
            esforco = duracao # TRIMP simplificado baseado em tempo
            
            for atividade in atividades:
                payload = {
                    "id_atleta": int(strava_id),
                    "data_treino": atividade['start_date_local'],
                    "trimp_score": atividade['moving_time'] / 60,
                    "distancia": atividade['distance'] / 1000,
                    "duracao": int(atividade['moving_time'] / 60),
                    "tipo_esporte": atividade['type']
                }
                supabase.table("atividades_fisicas").upsert(payload, on_conflict="id_atleta, data_treino").execute()
            
            # --- FORMATAÇÃO DA MENSAGEM (CORPO DO WHATSAPP) ---
            corpo_mensagem = (
                f"🚀 *Treino Sincronizado!*\n\n"
                f"👤 *Atleta:* {nome_atleta}\n"
                f"🏃 *Atividade:* {nome_atv}\n"
                f"📏 *Distância:* {distancia:.2f} km\n"
                f"⏱️ *Duração:* {duracao:.1f} min\n"
                f"📊 *Carga:* {esforco:.1f} pts\n\n"
                f"🔗 _Acesse o painel para ver seu ACWR!_"
            )
            
            enviar_whatsapp_twilio(corpo_mensagem)
            return True
        return False
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")
        return False

# --- LÓGICA DE AUTENTICAÇÃO STRAVA ---
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
            sincronizar_atividades(user_data["strava_id"], user_data["access_token"], user_data["nome"])
            st.rerun()
    except Exception as e:
        st.error(f"Erro no login: {e}")

# --- INTERFACE (SIDEBAR) ---
st.sidebar.title("🚀 Elite Performance")
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.link_button("🟠 Conectar Strava", auth_url)

atleta_id, token_atleta, nome_sel = None, None, ""
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
    if sincronizar_atividades(atleta_id, token_atleta, nome_sel):
        st.sidebar.success("Dados e WhatsApp enviados!")
        st.rerun()

# --- PAINEL PRINCIPAL ---
st.title("📊 Painel de Controle de Carga")

if atleta_id:
    res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(atleta_id)).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')

        df['Aguda'] = df['trimp_score'].rolling(window=7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(window=28, min_periods=1).mean()
        df['ACWR'] = df['Aguda'] / df['Cronica']

        m1, m2, m3 = st.columns(3)
        ultimo_acwr = df['ACWR'].iloc[-1]
        
        with m1:
            st.metric("ACWR Atual", f"{ultimo_acwr:.2f}")
        with m2:
            status = "✅ Seguro" if 0.8 <= ultimo_acwr <= 1.3 else "⚠️ Risco"
            st.metric("Status", status)
            if ultimo_acwr > 1.3:
                if st.button("🚨 Enviar Alerta de Risco"):
                    enviar_whatsapp_twilio(f"🚨 *ALERTA DE RISCO*\n\n{nome_sel}, seu ACWR está em *{ultimo_acwr:.2f}*. Reduza a carga para evitar lesões!")
        with m3:
            st.metric("Total Treinos", len(df))

        st.subheader("Gráfico de Evolução de Carga")
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df['data_treino'], df['Aguda'], label="Aguda (Fadiga)", color="#1E90FF", lw=2)
        ax.plot(df['data_treino'], df['Cronica'], label="Crônica (Fitness)", color="#FF4500", ls="--")
        ax.fill_between(df['data_treino'], 0.8 * df['Cronica'], 1.3 * df['Cronica'], color='green', alpha=0.1, label="Zona Ótima")
        ax.legend()
        st.pyplot(fig)
    else:
        st.info("Nenhuma atividade no banco. Sincronize os dados.")
