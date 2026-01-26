import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib
from datetime import datetime

# 1. Configurações Iniciais
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        if key in st.secrets: return st.secrets[key]
    except: pass
    return os.getenv(key)

# Conexões
url = get_secret("SUPABASE_URL")
key = get_secret("SUPABASE_KEY")
supabase = create_client(url, key)

CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES AUXILIARES ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone_destino):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        phone_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        client.messages.create(body=mensagem, from_=phone_from, to=f"whatsapp:{telefone_destino}")
        return True
    except: return False

# --- LÓGICA DE RENOVAÇÃO DE TOKEN (ADEUS ERRO 401) ---
def atualizar_token_strava(refresh_token, strava_id):
    url_token = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    res = requests.post(url_token, data=payload)
    if res.status_code == 200:
        dados = res.json()
        novo_access = dados['access_token']
        # Atualiza no banco para não expirar de novo logo em seguida
        supabase.table("usuarios").update({"access_token": novo_access}).eq("strava_id", strava_id).execute()
        return novo_access
    return None

def sincronizar_dados(strava_id, access_token, refresh_token, nome_atleta, telefone):
    url_atv = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    res = requests.get(url_atv, headers=headers, params={'per_page': 10})
    
    # Se der erro 401, tenta renovar o token e repetir a busca
    if res.status_code == 401:
        st.info("Renovando acesso ao Strava...")
        novo_token = atualizar_token_strava(refresh_token, strava_id)
        if novo_token:
            headers = {'Authorization': f'Bearer {novo_token}'}
            res = requests.get(url_atv, headers=headers, params={'per_page': 10})
        else:
            st.error("Erro crítico: Reconecte ao Strava pelo botão laranja.")
            return False

    if res.status_code == 200:
        atividades = res.json()
        if not atividades: return False
        
        for atv in atividades:
            payload = {
                "id_atleta": int(strava_id),
                "data_treino": atv['start_date_local'],
                "trimp_score": atv['moving_time'] / 60,
                "distancia": atv['distance'] / 1000,
                "tipo_esporte": atv['type']
            }
            supabase.table("atividades_fisicas").upsert(payload).execute()
        
        # WhatsApp do último treino
        ultimo = atividades[0]
        msg = f"✅ Treino Sincronizado!\nAtleta: {nome_atleta}\nDistância: {ultimo['distance']/1000:.2f}km"
        enviar_whatsapp(msg, telefone)
        return True
    return False

# --- LOGIN / SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    # (Mantenha aqui seu código de login e cadastro conforme as versões anteriores)
    # Use o botão de cadastrar_usuario e validar_login que já funcionam
    st.title("🏃‍♂️ Bem-vindo ao Seu Treino App")
    # ... (Omitido para brevidade, mantenha o seu bloco de login/cadastro)
    st.stop()

# --- SIDEBAR E DASHBOARD ---
st.sidebar.title(f"Olá, {st.session_state.user_info['nome']}")

# Menu Admin/Dashboard
menu = ["Dashboard"]
if st.session_state.user_info.get('is_admin'): menu.append("👑 Admin")
escolha = st.sidebar.selectbox("Navegação", menu)

if escolha == "👑 Admin":
    st.title("Painel de Controle Admin")
    res = supabase.table("usuarios_app").select("*").execute()
    st.dataframe(pd.DataFrame(res.data))
    st.stop()

# Botão Laranja Strava
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR AO STRAVA</div></a>', unsafe_allow_html=True)

# Busca atletas vinculados
res_strava = supabase.table("usuarios").select("*").execute()

if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    nome_sel = st.sidebar.selectbox("Atleta", list(atletas.keys()))
    dados_atleta = atletas[nome_sel]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        if sincronizar_dados(dados_atleta['strava_id'], dados_atleta['access_token'], dados_atleta['refresh_token'], nome_sel, st.session_state.user_info['telefone']):
            st.toast("Sincronizado!")
            st.rerun()

    # --- GRÁFICOS ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", dados_atleta['strava_id']).execute()
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
