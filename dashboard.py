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

# DETECÇÃO AUTOMÁTICA DA URL (Evita o erro de redirect_uri invalid)
# Se estiver no ar, usa a URL do Streamlit. Se estiver no PC, usa localhost.
if st.secrets.get("SUPABASE_URL"):
    # AJUSTE MANUAL: Se o link do seu app for diferente deste, mude aqui embaixo:
    REDIRECT_URI = "https://projeto-treinador.streamlit.app"
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

# =================================================================
# 🔑 LOGIN E CALLBACK DO STRAVA
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False
data_hoje = datetime.now().date()

# Processa o retorno do Strava
params = st.query_params
if "code" in params and "state" in params:
    cod, email_aluno = params["code"], params["state"]
    with st.spinner("Conectando ao Strava..."):
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
            st.rerun()

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
                else: st.error("Login inválido.")
        with t_cad:
            # Simplificado para o exemplo
            st.info("O cadastro de novos alunos é realizado pelo treinador ou via formulário.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# Tratamento de Data para evitar o erro TypeError
v_str = user.get('data_vencimento')
if not v_str or not isinstance(v_str, str): v_str = "2000-01-01"
try:
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
except:
    venc_date = datetime(2000, 1, 1).date()

pago = user.get('status_pagamento', False) and data_hoje <= venc_date

if eh_admin:
    st.title("👨‍🏫 Painel Admin")
    res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in res_alunos.data:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            col1.write(f"**{aluno['nome']}** - Vence: {aluno['data_vencimento']}")
            if col2.button("Ativar/Desativar", key=aluno['id']):
                supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                st.rerun()
else:
    # VISÃO ATLETA
    st.title("🚀 Dashboard")
    
    if pago:
        res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
        if res_s.data:
            atleta_strava = res_s.data[0]
            # BOTÃO DE SINCRONIZAR NO TOPO
            if st.button("🔄 ATUALIZAR MEUS TREINOS", type="primary", use_container_width=True):
                with st.spinner("Sincronizando..."):
                    sincronizar_dados(atleta_strava['strava_id'], atleta_strava['access_token'])
                    st.rerun()
            
            res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta_strava['strava_id']).execute()
            if res_atv.data:
                df = pd.DataFrame(res_atv.data)
                st.subheader("Últimos Treinos")
                st.dataframe(df.sort_values(by='data_treino', ascending=False), use_container_width=True)
        else:
            st.warning("⚠️ Seu Strava ainda não está vinculado.")
            # Link de autorização formatado para evitar o erro de redirect_uri
            auth_url = (
                f"https://www.strava.com/oauth/authorize?"
                f"client_id={CLIENT_ID}&"
                f"redirect_uri={REDIRECT_URI}&"
                f"response_type=code&"
                f"approval_prompt=auto&"
                f"scope=read,activity:read&"
                f"state={user['email']}"
            )
            st.link_button("🔗 Vincular Strava Agora", auth_url, type="primary")
    else:
        st.error(f"🚨 Acesso suspenso. Vencimento: {venc_date.strftime('%d/%m/%Y')}")

with st.sidebar:
    st.write(f"Logado como: **{user['nome']}**")
    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()
