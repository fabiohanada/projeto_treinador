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
    except Exception as e:
        st.warning(f"Aviso WhatsApp: {e}")
        return False

def sincronizar_dados(strava_id, access_token, refresh_token, nome, telefone):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        res = requests.get(url, headers=headers, params={'per_page': 10})
        
        # Se o token expirou (Erro 401)
        if res.status_code == 401:
            st.warning("Token expirado. Tentando renovar...")
            if not refresh_token:
                st.error("Erro: Você não tem um 'refresh_token' no banco. Clique no botão laranja do Strava novamente.")
                return False
            
            # Lógica de renovação
            r = requests.post("https://www.strava.com/oauth/token", data={
                'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
                'grant_type': 'refresh_token', 'refresh_token': refresh_token
            })
            if r.status_code == 200:
                access_token = r.json()['access_token']
                supabase.table("usuarios").update({"access_token": access_token}).eq("strava_id", strava_id).execute()
                headers = {'Authorization': f'Bearer {access_token}'}
                res = requests.get(url, headers=headers, params={'per_page': 10})
            else:
                st.error(f"Falha ao renovar token: {r.text}")
                return False

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
                supabase.table("atividades_fisicas").upsert(payload).execute()
            
            enviar_whatsapp(f"✅ Treinos de {nome} atualizados!", telefone)
            return True
        else:
            st.error(f"Erro Strava: {res.status_code}")
            return False

    except Exception as e:
        # ISSO VAI FAZER O ERRO PARAR NA TELA PARA VOCÊ LER
        st.exception(e) 
        return False

# --- LOGIN (Simplificado para o teste) ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🏃‍♂️ Login")
    e = st.text_input("E-mail", key="l_e")
    s = st.text_input("Senha", type="password", key="l_s")
    if st.button("Entrar"):
        u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
        if u.data:
            st.session_state.logado, st.session_state.user_info = True, u.data[0]
            st.rerun()
    st.stop()

# --- DASHBOARD ---
st.sidebar.markdown(f'<a href="https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR AO STRAVA</div></a>', unsafe_allow_html=True)

res_strava = supabase.table("usuarios").select("*").execute()
if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    sel = st.sidebar.selectbox("Atleta", list(atletas.keys()))
    d = atletas[sel]

    if st.sidebar.button("🔄 Sincronizar Agora"):
        # Adicionamos um log visual para ver o que está sendo enviado
        st.write(f"Tentando sincronizar {sel}...")
        
        # O erro costuma ser aqui: d.get('refresh_token')
        if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token'), sel, st.session_state.user_info['telefone']):
            st.success("Sincronizado! Agora clique no botão abaixo para atualizar os gráficos.")
            if st.button("Ver Gráficos Atualizados"):
                st.rerun()

    # --- GRÁFICOS ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['dt'] = pd.to_datetime(df['data_treino'])
        df['data_limpa'] = df['dt'].dt.strftime('%d/%m/%Y')
        df = df.sort_values('dt')
        
        st.subheader("🗓️ Atividades por Dia")
        st.bar_chart(df.groupby('data_limpa').size())
        
        st.subheader("📈 Carga Aguda vs Crônica")
        df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
        st.line_chart(df.set_index('data_limpa')[['Aguda', 'Cronica']])
