import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client

# 1. CONFIGURAÇÕES E CONEXÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")

# Detecta automaticamente se o app está local ou no ar para o Redirect do Strava
if st.secrets.get("SUPABASE_URL"):
    REDIRECT_URI = "https://seu-projeto.streamlit.app" # <--- AJUSTE PARA SUA URL REAL
else:
    REDIRECT_URI = "http://localhost:8501"

# --- FUNÇÕES CORE ---
def hash_senha(senha): 
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    try:
        sid, token = get_secret("TWILIO_ACCOUNT_SID"), get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        tel_destino = ''.join(filter(str.isdigit, str(telefone)))
        client.messages.create(body=mensagem, from_=p_from, to=f"whatsapp:+{tel_destino}")
        return True
    except: return False

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 30})
    if res.status_code == 200:
        for atv in res.json():
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), "data_treino": atv['start_date_local'],
                "distancia": atv['distance'] / 1000, "tipo_esporte": atv['type'],
                "trimp_score": atv['moving_time'] / 60
            }).execute()
        return True
    return False

# --- LÓGICA DE CALLBACK DO STRAVA ---
params = st.query_params
if "code" in params and "state" in params:
    cod, email_aluno = params["code"], params["state"]
    res_t = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": cod, "grant_type": "authorization_code"
    }).json()
    if "access_token" in res_t:
        supabase.table("usuarios").upsert({
            "email": email_aluno, "strava_id": res_t["athlete"]["id"],
            "access_token": res_t["access_token"], "refresh_token": res_t["refresh_token"],
            "nome": res_t["athlete"]["firstname"]
        }).execute()
        st.success("✅ Strava vinculado!")
        st.query_params.clear()

# =================================================================
# 🔑 TELA DE LOGIN
# =================================================================
if "logado" not in st.session_state: 
    st.session_state.logado = False

data_hoje = datetime.now().date()

if not st.session_state.logado:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🏃‍♂️ Fábio Assessoria")
        t_log, t_cad = st.tabs(["Entrar", "Novo Cadastro"])
        with t_log:
            e = st.text_input("E-mail", key="l_email")
            s = st.text_input("Senha", type="password", key="l_senha")
            if st.button("Entrar", use_container_width=True, type="primary"):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.rerun()
                else: st.error("E-mail ou senha inválidos.")
        with t_cad:
            # ... (seu código de cadastro aqui)
            st.info("Utilize a aba Entrar se já possuir conta.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.header(f"👋 {user['nome']}")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# --- 🛠 CORREÇÃO DO ERRO DE DATA (LINHA 120) ---
v_str = user.get('data_vencimento')
# Se a data for nula, vazia ou não for string, define uma data padrão antiga
if not v_str or not isinstance(v_str, str):
    v_str = "2000-01-01"

try:
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
except ValueError:
    venc_date = datetime(2000, 1, 1).date()

pago = user.get('status_pagamento', False) and data_hoje <= venc_date

# --- DIVISÃO DE TELAS ---
if eh_admin:
    st.title("👨‍🏫 Painel do Treinador")
    tab_f, tab_p = st.tabs(["💰 Financeiro", "📊 Performance"])
    
    with tab_f:
        res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
        if res_alunos.data:
            for aluno in res_alunos.data:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.write(f"**{aluno['nome']}**")
                    status_txt = "Ativo" if aluno['status_pagamento'] else "Bloqueado"
                    c2.write(f"Status: {status_txt}")
                    if c3.button("Inverter Status", key=f"inv_{aluno['id']}"):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()
else:
    # VISÃO ATLETA
    st.title("🚀 Dashboard")
    # ... (restante do código do atleta que já enviamos anteriormente)
    if not pago:
        st.warning(f"Sua assinatura expirou ou está inativa (Data: {venc_date})")
