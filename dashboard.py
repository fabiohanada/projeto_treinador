import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib

# 1. CONFIGURAÇÕES
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
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        tel_limpo = ''.join(filter(str.isdigit, str(telefone)))
        client.messages.create(body=mensagem, from_=p_from, to=f"whatsapp:+{tel_limpo}")
        return True
    except: return False

def sincronizar_dados(strava_id, access_token, refresh_token, nome, telefone):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
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
                try: supabase.table("atividades_fisicas").upsert(payload).execute()
                except: continue
            return True
        return False
    except: return False

# --- LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    st.title("🏃‍♂️ Acesso ao Sistema")
    e = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
        if u.data:
            st.session_state.logado, st.session_state.user_info = True, u.data[0]
            st.rerun()
    st.stop()

# --- SIDEBAR (Botão Strava agora é fixo aqui) ---
st.sidebar.title(f"Treinador: {st.session_state.user_info['nome']}")

# O BOTÃO FICA AQUI FORA DE QUALQUER CONDIÇÃO
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'''
    <a href="{auth_url}" target="_self" style="text-decoration:none;">
        <div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-top:10px;margin-bottom:20px;">
            🟠 CONECTAR NOVO ATLETA (STRAVA)
        </div>
    </a>
''', unsafe_allow_html=True)

# --- LISTA DE ATLETAS E DASHBOARD ---
res_strava = supabase.table("usuarios").select("*").execute()

if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    sel = st.sidebar.selectbox("Selecionar Atleta", list(atletas.keys()))
    d = atletas[sel]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token'), sel, st.session_state.user_info['telefone']):
            st.toast("Dados atualizados!")
            st.rerun()

    # --- CÁLCULOS E ALERTAS ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['dt'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('dt')
        df['data_f'] = df['dt'].dt.strftime('%d/%m/%Y')
        df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
        
        # Alerta ACWR
        ratio = df['Aguda'].iloc[-1] / df['Cronica'].iloc[-1] if df['Cronica'].iloc[-1] > 0 else 0
        
        st.subheader(f"Análise: {sel}")
        if ratio > 1.5:
            st.error(f"⚠️ RISCO DE LESÃO: Rácio em {ratio:.2f}!")
        
        # Gráficos
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🗓️ Atividades/Dia")
            st.bar_chart(df.groupby('data_f').size())
        with c2:
            st.subheader("📈 Carga Aguda vs Crônica")
            st.line_chart(df.set_index('data_f')[['Aguda', 'Cronica']])
else:
    st.sidebar.info("Nenhum atleta conectado ainda.")
    st.info("Utilize o botão laranja na barra lateral para conectar o primeiro atleta via Strava.")

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
