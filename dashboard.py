import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client

# CONFIG E CONEXÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-app.streamlit.app"

# FUNÇÕES AUXILIARES
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    try:
        sid, token = get_secret("TWILIO_ACCOUNT_SID"), get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        client.messages.create(body=mensagem, from_=p_from, to=f"whatsapp:+{telefone}")
        return True
    except: return False

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 30})
    if res.status_code == 200:
        for atv in res.json():
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), "data_treino": atv['start_date_local'],
                "distancia": atv['distance'] / 1000, "tipo_esporte": atv['type']
            }).execute()
        return True
    return False

# AUTH E LOGIN
if "logado" not in st.session_state: st.session_state.logado = False
data_hoje = datetime.now().date()

if not st.session_state.logado:
    # ... (Mantenha aqui aquele bloco de Login/Cadastro com o texto de LGPD que criamos anteriormente)
    # No cadastro, inclua o enviar_whatsapp(msg_welcome) como mostrei acima.
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# SIDEBAR UNIVERSAL
with st.sidebar:
    st.title(f"👋 {user['nome']}")
    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()

# DASHBOARD DO ATLETA
if not eh_admin:
    venc_date = datetime.strptime(user.get('data_vencimento', '2000-01-01'), '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and data_hoje <= venc_date

    t1, t2 = st.tabs(["📈 Performance", "💳 Pagamento"])
    
    with t1:
        if pago:
            res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
            if res_s.data:
                atleta = res_s.data[0]
                if st.button("🔄 Atualizar Treinos"):
                    sincronizar_dados(atleta['strava_id'], atleta['access_token'])
                    st.rerun()
                
                # CÁLCULO ACWR
                res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).execute()
                if res_atv.data:
                    df = pd.DataFrame(res_atv.data)
                    df['data_treino'] = pd.to_datetime(df['data_treino'])
                    df_res = df.groupby(df['data_treino'].dt.date)['distancia'].sum().resample('D').sum().fillna(0).to_frame()
                    df_res['acwr'] = df_res['distancia'].rolling(7).mean() / df_res['distancia'].rolling(28).mean()
                    
                    val = df_res['acwr'].iloc[-1]
                    st.metric("Seu Índice ACWR", f"{val:.2f}", delta_color="inverse")
                    st.line_chart(df_res['acwr'])
            else:
                st.link_button("🔗 Conectar Strava", f"https://www.strava.com/oauth/authorize?...")
        else:
            st.error("Acesso suspenso. Verifique seu pagamento.")
