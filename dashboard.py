import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib

# 1. Configurações
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        if key in st.secrets: return st.secrets[key]
    except: pass
    return os.getenv(key)

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    try:
        client = Client(get_secret("TWILIO_ACCOUNT_SID"), get_secret("TWILIO_AUTH_TOKEN"))
        tel_limpo = ''.join(filter(str.isdigit, telefone))
        client.messages.create(body=mensagem, from_=get_secret("TWILIO_PHONE_NUMBER"), to=f"whatsapp:+{tel_limpo}")
        return True
    except: return False

def sincronizar_dados(strava_id, access_token, refresh_token, nome, telefone):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        res = requests.get(url, headers=headers, params={'per_page': 10})
        
        if res.status_code == 401: # Token expirado
            r = requests.post("https://www.strava.com/oauth/token", data={
                'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
                'grant_type': 'refresh_token', 'refresh_token': refresh_token
            })
            if r.status_code == 200:
                access_token = r.json()['access_token']
                supabase.table("usuarios").update({"access_token": access_token}).eq("strava_id", strava_id).execute()
                headers = {'Authorization': f'Bearer {access_token}'}
                res = requests.get(url, headers=headers, params={'per_page': 10})

        if res.status_code == 200:
            atividades = res.json()
            for atv in atividades:
                payload = {
                    "id_atleta": int(strava_id),
                    "data_treino": atv['start_date_local'],
                    "trimp_score": atv['moving_time'] / 60,
                    "distancia": atv['distance'] / 1000,
                    "tipo_esporte": atv['type']
                }
                # TRATAMENTO DE ERRO ESPECÍFICO PARA O UPSERT
                try:
                    supabase.table("atividades_fisicas").upsert(payload).execute()
                except Exception as e:
                    # Se der erro no banco, ele apenas avisa no log interno e pula para o próximo
                    print(f"Erro ao salvar treino de {atv['start_date_local']}: {e}")
                    continue
            
            enviar_whatsapp(f"✅ Treinos de {nome} sincronizados!", telefone)
            return True
    except Exception as e:
        st.error(f"Erro na conexão: {e}")
        return False

# --- LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🏃‍♂️ Acesso")
    e = st.text_input("E-mail", key="l_e")
    s = st.text_input("Senha", type="password", key="l_s")
    if st.button("Entrar"):
        u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
        if u.data:
            st.session_state.logado, st.session_state.user_info = True, u.data[0]
            st.rerun()
    st.stop()

# --- DASHBOARD ---
st.sidebar.markdown(f"### Olá, {st.session_state.user_info['nome']}")
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR AO STRAVA</div></a>', unsafe_allow_html=True)

res_strava = supabase.table("usuarios").select("*").execute()
if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    sel = st.sidebar.selectbox("Atleta", list(atletas.keys()))
    d = atletas[sel]

    if st.sidebar.button("🔄 Sincronizar Agora"):
        if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token'), sel, st.session_state.user_info['telefone']):
            st.toast("Sincronizado!")
            st.rerun()

    # --- GRÁFICOS ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['dt'] = pd.to_datetime(df['data_treino'])
        df['data_formatada'] = df['dt'].dt.strftime('%d/%m/%Y')
        df = df.sort_values('dt')
        
        st.subheader("🗓️ Atividades por Dia")
        st.bar_chart(df.groupby('data_formatada').size())
        
        st.subheader("📈 Carga Aguda vs Crônica")
        df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
        st.line_chart(df.set_index('data_formatada')[['Aguda', 'Cronica']])
