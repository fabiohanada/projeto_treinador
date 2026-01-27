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

# --- ⚠️ AJUSTE MANUAL OBRIGATÓRIO AQUI ⚠️ ---
# Cole aqui a URL exata do seu app (ex: "https://seu-app.streamlit.app")
REDIRECT_URI = "https://seu-projeto-fabio.streamlit.app" 
# --------------------------------------------

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
if "logado" not in st.session_state: 
    st.session_state.logado = False

data_hoje = datetime.now().date()

# Processamento do Retorno do Strava
params = st.query_params
if "code" in params and "state" in params:
    cod = params["code"]
    email_aluno = params["state"]
    with st.spinner("Conectando ao Strava..."):
        try:
            res_t = requests.post("https://www.strava.com/oauth/token", data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": cod,
                "grant_type": "authorization_code"
            })
            dados_token = res_t.json()
            if res_t.status_code == 200:
                supabase.table("usuarios").upsert({
                    "email": email_aluno, 
                    "strava_id": dados_token["athlete"]["id"],
                    "access_token": dados_token["access_token"], 
                    "refresh_token": dados_token["refresh_token"],
                    "nome": dados_token["athlete"]["firstname"]
                }).execute()
                st.success("✅ Strava vinculado com sucesso!")
                st.query_params.clear()
                st.rerun()
            else:
                st.error(f"Erro na troca de token: {dados_token.get('message')}")
        except Exception as e:
            st.error(f"Erro de conexão: {e}")

# Tela de Login
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
                else: st.error("E-mail ou senha incorretos.")
        with t_cad:
            n_nome = st.text_input("Nome Completo")
            n_email = st.text_input("E-mail do Aluno")
            n_tel = st.text_input("WhatsApp (Ex: 5511999999999)")
            n_senha = st.text_input("Senha", type="password")
            if st.button("Criar Conta Aluno", use_container_width=True):
                payload = {"nome": n_nome, "email": n_email, "telefone": n_tel, "senha": hash_senha(n_senha), 
                           "is_admin": False, "status_pagamento": False, "data_vencimento": str(data_hoje)}
                supabase.table("usuarios_app").insert(payload).execute()
                st.success("Conta criada! Faça login.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.header(f"👋 {user['nome']}")
    if st.button("🚪 Sair"):
        st.session_state.logado = False
        st.rerun()

# Tratamento de Data Blindado
v_str = user.get('data_vencimento')
if not v_str or not isinstance(v_str, str): v_str = "2000-01-01"
try:
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
except:
    venc_date = datetime(2000, 1, 1).date()

pago = user.get('status_pagamento', False) and data_hoje <= venc_date

if eh_admin:
    st.title("👨‍🏫 Painel Treinador")
    # Código financeiro simplificado
    res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in res_alunos.data:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{aluno['nome']}** - Vence: {aluno['data_vencimento']}")
            if c2.button("Ativar/Desativar", key=aluno['id']):
                supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                st.rerun()
else:
    # --- DASHBOARD DO ATLETA ---
    st.title("🚀 Seu Dashboard")
    
    atleta_strava = None
    res_atv_data = []

    if pago:
        res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
        if res_s.data:
            atleta_strava = res_s.data[0]
            if st.button("🔄 SINCRONIZAR TREINOS AGORA", type="primary", use_container_width=True):
                with st.spinner("Buscando Strava..."):
                    sincronizar_dados(atleta_strava['strava_id'], atleta_strava['access_token'])
                    st.rerun()
            
            res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta_strava['strava_id']).execute()
            res_atv_data = res_atv.data if res_atv else []
        else:
            st.warning("Seu Strava não está vinculado.")
            # Montagem do link limpa para evitar erro de redirect_uri
            auth_url = (
                "https://www.strava.com/oauth/authorize"
                f"?client_id={CLIENT_ID}"
                f"&redirect_uri={REDIRECT_URI}"
                f"&response_type=code"
                f"&approval_prompt=auto"
                f"&scope=read,activity:read"
                f"&state={user['email']}"
            )
            st.link_button("🔗 Vincular Strava Agora", auth_url, type="primary")
    else:
        st.error(f"Acesso expirado em {venc_date.strftime('%d/%m/%Y')}")

    # Conteúdo
    t1, t2 = st.tabs(["📊 Histórico", "📈 Carga ACWR"])
    with t1:
        if res_atv_data:
            st.dataframe(pd.DataFrame(res_atv_data).sort_values(by='data_treino', ascending=False), use_container_width=True)
    with t2:
        st.info("Gráfico de performance disponível após 28 dias de treinos.")
