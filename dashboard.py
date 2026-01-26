import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib
from datetime import datetime

# 1. Configurações e Conexão
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

# --- FUNÇÕES DE SEGURANÇA E WHATSAPP ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    try:
        client = Client(get_secret("TWILIO_ACCOUNT_SID"), get_secret("TWILIO_AUTH_TOKEN"))
        client.messages.create(body=mensagem, from_=get_secret("TWILIO_PHONE_NUMBER"), to=f"whatsapp:{telefone}")
        return True
    except: return False

# --- SINCRONIZAÇÃO COM PROTEÇÃO ---
def atualizar_token_strava(refresh_token, strava_id):
    url = "https://www.strava.com/oauth/token"
    p = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'refresh_token', 'refresh_token': refresh_token}
    res = requests.post(url, data=p)
    if res.status_code == 200:
        novo = res.json()['access_token']
        supabase.table("usuarios").update({"access_token": novo}).eq("strava_id", strava_id).execute()
        return novo
    return None

def sincronizar_dados(strava_id, access_token, refresh_token, nome, telefone):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get(url, headers=headers, params={'per_page': 10})
    
    if res.status_code == 401:
        access_token = atualizar_token_strava(refresh_token, strava_id)
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
            try:
                # O try/except aqui impede que o erro de banco apareça na tela
                supabase.table("atividades_fisicas").upsert(payload).execute()
            except:
                continue 
        
        if atividades:
            enviar_whatsapp(f"✅ Treino de {atividades[0]['distance']/1000:.2f}km sincronizado!", telefone)
        return True
    return False

# --- INTERFACE ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🏃‍♂️ Seu Treino App")
        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            e = st.text_input("E-mail", key="l_e")
            s = st.text_input("Senha", type="password", key="l_s")
            if st.button("Acessar", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.rerun()
                else: st.error("Erro de login.")
        with t2:
            n_c = st.text_input("Nome", key="c_n")
            e_c = st.text_input("E-mail", key="c_e")
            t_c = st.text_input("WhatsApp (55...)", key="c_t")
            s_c = st.text_input("Senha", type="password", key="c_s")
            if st.button("Cadastrar", use_container_width=True):
                payload = {"nome": n_c, "email": e_c, "senha": hash_senha(s_c), "telefone": t_c, "is_admin": False}
                supabase.table("usuarios_app").insert(payload).execute()
                st.success("Conta criada!")
    st.stop()

# --- DASHBOARD LOGADO ---
st.sidebar.title(f"Olá, {st.session_state.user_info['nome']}")
# Botão Strava
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR AO STRAVA</div></a>', unsafe_allow_html=True)

res_strava = supabase.table("usuarios").select("*").execute()
if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    sel = st.sidebar.selectbox("Atleta", list(atletas.keys()))
    d = atletas[sel]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token'), sel, st.session_state.user_info['telefone']):
            st.toast("Sincronizado!")
            st.rerun()

    # --- GRÁFICOS ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['data_treino'] = pd.to_datetime(df['data_treino']).dt.date
        df = df.sort_values('data_treino')

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🗓️ Atividades por Dia")
            st.bar_chart(df['data_treino'].value_counts().sort_index())
        with c2:
            st.subheader("📈 Carga Aguda (7d) vs Crônica (28d)")
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            st.line_chart(df.set_index('data_treino')[['Aguda', 'Cronica']])

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
