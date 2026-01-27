import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide")

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")

# --- LÓGICA DE URL DINÂMICA (Para matar o erro de Redirect de vez) ---
# Esta função pega a URL exata que você está usando no momento
def get_redirect_uri():
    if st.secrets.get("SUPABASE_URL"):
        # Se estiver no Streamlit Cloud, pegamos a URL da barra de endereços
        # Mas para garantir, você pode fixar a URL do seu app aqui:
        return "https://projeto-treinador.streamlit.app"
    return "http://localhost:8501"

REDIRECT_URI = get_redirect_uri()

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 10})
    if res.status_code == 200:
        for atv in res.json():
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), "data_treino": atv['start_date_local'],
                "distancia": atv['distance'] / 1000, "tipo_esporte": atv['type']
            }).execute()
        return True
    return False

# =================================================================
# 🔑 LOGIN E CALLBACK
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

# Processa o retorno do Strava
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
        st.rerun()

if not st.session_state.logado:
    st.title("🏃‍♂️ Fábio Assessoria - Login")
    e = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True, type="primary"):
        u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
        if u.data:
            st.session_state.logado = True
            st.session_state.user_info = u.data[0]
            st.rerun()
        else: st.error("Login inválido.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# Dados de pagamento
v_str = user.get('data_vencimento', "2000-01-01")
venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
pago = user.get('status_pagamento', False) and datetime.now().date() <= venc_date

if eh_admin:
    st.title("👨‍🏫 Painel Admin")
    st.write("Gerencie seus alunos no Supabase ou adicione lógica aqui.")
    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    
    if pago:
        # Verifica se já tem Strava vinculado
        res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
        
        if res_s.data:
            atleta = res_s.data[0]
            if st.button("🔄 Sincronizar Treinos", type="primary"):
                sincronizar_dados(atleta['strava_id'], atleta['access_token'])
                st.success("Dados atualizados!")
            
            # Mostra dados
            res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).execute()
            if res_atv.data:
                st.dataframe(pd.DataFrame(res_atv.data), use_container_width=True)
        else:
            st.warning("Vincule seu Strava para começar.")
            # O LINK QUE CAUSA O ERRO - AGORA BLINDADO
            auth_url = (
                f"https://www.strava.com/oauth/authorize?"
                f"client_id={CLIENT_ID}&"
                f"response_type=code&"
                f"redirect_uri={REDIRECT_URI}&"
                f"approval_prompt=auto&"
                f"scope=read,activity:read&"
                f"state={user['email']}"
            )
            st.link_button("🔗 Conectar Strava", auth_url)
            # Ajuda visual para o admin:
            with st.expander("Debug de Conexão"):
                st.write(f"Sua Redirect URI enviada é: `{REDIRECT_URI}`")
                st.write("Certifique-se que no painel do Strava o domínio é apenas: `projeto-treinador.streamlit.app` (sem https)")
    else:
        st.error("Assinatura inativa. Fale com o Fábio.")

    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()
