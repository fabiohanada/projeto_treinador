import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from datetime import datetime
from twilio.rest import Client

# 1. Configurações Iniciais
load_dotenv()
st.set_page_config(page_title="Elite Performance Dashboard", layout="wide")

# Função para obter segredos de forma segura (Secrets ou Env)
def get_secret(key):
    return st.secrets.get(key) or os.getenv(key)

# Conexões
url = get_secret("SUPABASE_URL")
key = get_secret("SUPABASE_KEY")
supabase = create_client(url, key)

CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÃO DE ENVIO DE WHATSAPP (COM DIAGNÓSTICO) ---
def enviar_whatsapp_twilio(mensagem):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        phone_from = get_secret("TWILIO_PHONE_NUMBER")
        phone_to = get_secret("MY_PHONE_NUMBER")
        
        if not all([sid, token, phone_from, phone_to]):
            st.error("❌ Credenciais do Twilio incompletas nos Secrets.")
            return False

        client = Client(sid, token)
        
        # Garante o formato 'whatsapp:+number'
        p_from = f"whatsapp:{phone_from.replace('whatsapp:', '')}"
        p_to = f"whatsapp:{phone_to.replace('whatsapp:', '')}"

        message = client.messages.create(
            body=mensagem,
            from_=p_from,
            to=p_to
        )
        
        if message.sid:
            st.toast(f"✅ WhatsApp enviado! Status: {message.status}", icon="📲")
            return True
    except Exception as e:
        st.error(f"❌ Erro no Twilio: {e}")
        return False

# --- FUNÇÃO DE SINCRONIZAÇÃO DE ATIVIDADES ---
def sincronizar_atividades(strava_id, access_token, nome_atleta):
    url_atividades = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        atividades = requests.get(url_atividades, headers=headers, params={'per_page': 10}).json()
        
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
                # Upsert evita duplicados baseados na constraint (id_atleta, data_treino)
                supabase.table("atividades_fisicas").upsert(payload, on_conflict="id_atleta, data_treino").execute()
            
            # Notificação de sucesso
            enviar_whatsapp_twilio(f"✅ *Elite Performance*\nTreinos de *{nome_atleta}* atualizados com sucesso!")
            return True
        else:
            st.error("Não foi possível obter a lista de atividades do Strava.")
            return False
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")
        return False

# --- LÓGICA DE LOGIN STRAVA ---
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
            st.success("Atleta conectado!")
            st.rerun()
    except Exception as e:
        st.error(f"Erro no login: {e}")

# --- BARRA LATERAL ---
st.sidebar.title("🚀 Elite Performance")
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.link_button("🟠 Conectar Strava", auth_url)

atleta_id = None
token_atleta = None
nome_selecionado = ""

try:
    usuarios = supabase.table("usuarios").select("*").execute()
    if usuarios.data:
        opcoes = {u['nome']: u['strava_id'] for u in usuarios.data}
        nome_selecionado = st.sidebar.selectbox("👤 Selecionar Atleta", list(opcoes.keys()))
        atleta_id = opcoes[nome_selecionado]
        token_atleta = next(u['access_token'] for u in usuarios.data if u['strava_id'] == atleta_id)
except Exception:
    st.sidebar.warning("Nenhum atleta cadastrado.")

if atleta_id and st.sidebar.button("🔄 Sincronizar Agora"):
    with st.spinner("Sincronizando..."):
        if sincronizar_atividades(atleta_id, token_atleta, nome_selecionado):
            st.rerun()

# --- ÁREA PRINCIPAL ---
st.title("📊 Painel de Controle de Carga")

if atleta_id:
    res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(atleta_id)).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')

        # Cálculos de Carga ACWR
        df['Aguda'] = df['trimp_score'].rolling(window=7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(window=28, min_periods=1).mean()
        df['ACWR'] = df['Aguda'] / df['Cronica']

        # Métricas em colunas
        m1, m2, m3 = st.columns(3)
        ultimo_acwr = df['ACWR'].iloc[-1]
        
        with m1:
            st.metric("ACWR Atual", f"{ultimo_acwr:.2f}")
        with m2:
            status = "✅ Seguro" if 0.8 <= ultimo_acwr <= 1.3 else "⚠️ Risco"
            st.metric("Status", status)
        with m3:
            st.metric("Total Treinos", len(df))

        # Alerta Automático via Interface
        if ultimo_acwr > 1.3:
            st.error(f"🚨 Atenção: {nome_selecionado} está em zona de risco de lesão!")
            if st.button("Enviar Alerta Urgente via WhatsApp"):
                enviar_whatsapp_twilio(f"🚨 *ALERTA CRÍTICO*: {nome_selecionado}, sua carga de treino ({ultimo_acwr:.2f}) indica alto risco de lesão. Descanse!")

        # Gráfico de Carga
        st.subheader("Gráfico de Evolução (TL)")
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df['data_treino'], df['Aguda'], label="Carga Aguda (7d)", color="#1E90FF", lw=2)
        ax.plot(df['data_treino'], df['Cronica'], label="Carga Crônica (28d)", color="#FF4500", ls="--")
        ax.fill_between(df['data_treino'], 0.8 * df['Cronica'], 1.3 * df['Cronica'], color='green', alpha=0.1, label="Sweet Spot")
        ax.set_ylabel("Carga (Score)")
        ax.legend()
        plt.xticks(rotation=45)
        st.pyplot(fig)
        
        with st.expander("Ver dados brutos"):
            st.write(df.tail(10))
    else:
        st.info("Nenhum dado encontrado para este atleta. Clique em sincronizar.")
else:
    st.info("Aguardando seleção de atleta na barra lateral.")
