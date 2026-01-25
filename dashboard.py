import streamlit as st
import pandas as pd  # CORRIGIDO: de 'import pd' para 'import pandas'
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from twilio.rest import Client
import hashlib

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

# --- FUNÇÕES DE SEGURANÇA ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def validar_login(email, senha):
    senha_hash = hash_senha(senha)
    try:
        res = supabase.table("usuarios_app").select("*").eq("email", email).eq("senha", senha_hash).execute()
        return res.data[0] if res.data else None
    except:
        return None

def cadastrar_usuario(nome, email, senha, telefone):
    senha_hash = hash_senha(senha)
    tel_limpo = ''.join(filter(str.isdigit, telefone))
    if not tel_limpo.startswith('+'):
        tel_limpo = f"+{tel_limpo}"
    payload = {"nome": nome, "email": email, "senha": senha_hash, "telefone": tel_limpo}
    try:
        supabase.table("usuarios_app").insert(payload).execute()
        return True
    except:
        return False

# --- FUNÇÃO DE WHATSAPP ---
def enviar_whatsapp_twilio(mensagem):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        phone_from = get_secret("TWILIO_PHONE_NUMBER")
        phone_to = st.session_state.user_info.get('telefone')
        if not all([sid, token, phone_from, phone_to]): return False
        client = Client(sid, token)
        p_from = f"whatsapp:{phone_from.replace('whatsapp:', '')}"
        p_to = f"whatsapp:{phone_to.replace('whatsapp:', '')}"
        client.messages.create(body=mensagem, from_=p_from, to=p_to)
        return True
    except: return False

# --- FUNÇÃO DE SINCRONIZAÇÃO SILENCIOSA (AUTOMÁTICA) ---
def sincronizar_silencioso(strava_id, access_token):
    url_atv = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        res = requests.get(url_atv, headers=headers, params={'per_page': 5})
        if res.status_code == 200:
            atividades = res.json()
            for atv in atividades:
                payload = {
                    "id_atleta": int(strava_id),
                    "data_treino": atv['start_date_local'],
                    "trimp_score": atv['moving_time'] / 60,
                    "distancia": atv['distance'] / 1000,
                    "duracao": int(atv['moving_time'] / 60),
                    "tipo_esporte": atv['type']
                }
                supabase.table("atividades_fisicas").upsert(payload, on_conflict="id_atleta, data_treino").execute()
            return True
    except: pass
    return False

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_info = None

# --- CAPTURA RETORNO DO STRAVA ---
if "code" in st.query_params:
    code = st.query_params["code"]
    res_token = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": code, "grant_type": "authorization_code"
    }).json()
    
    if 'access_token' in res_token:
        u_strava = {
            "strava_id": res_token['athlete']['id'], 
            "nome": res_token['athlete']['firstname'], 
            "access_token": res_token['access_token']
        }
        supabase.table("usuarios").upsert(u_strava).execute()
        sincronizar_silencioso(u_strava["strava_id"], u_strava["access_token"])
        st.query_params.clear()
        st.rerun()

# --- INTERFACE: LOGIN / CADASTRO ---
if not st.session_state.logado:
    st.markdown("""
        <style>
        div.stButton > button:first-child { background-color: #007bff; color: white; border: none; font-weight: bold; border-radius: 8px; height: 45px; }
        .main-header { display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 20px; }
        .runner-icon { font-size: 40px; color: #ff4b4b; }
        .title-text { font-size: 32px; font-weight: bold; color: #31333F; }
        .stTabs [data-baseweb="tab-highlight"] { background-color: #ff4b4b; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        st.markdown("""
            <div class='main-header'>
                <span class='runner-icon'>🏃‍♂️</span>
                <span class='title-text'>Seu Treino App</span>
            </div>
        """, unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        with tab1:
            e = st.text_input("Email", key="l_email")
            s = st.text_input("Senha", type="password", key="l_senha")
            if st.button("Acessar Painel", use_container_width=True):
                u = validar_login(e, s)
                if u:
                    st.session_state.logado = True
                    st.session_state.user_info = u
                    st.rerun()
                else: st.error("E-mail ou senha incorretos.")
        with tab2:
            n_c = st.text_input("Nome")
            e_c = st.text_input("E-mail")
            t_c = st.text_input("WhatsApp (Ex: 5511999999999)")
            s_c = st.text_input("Senha", type="password")
            if st.button("Cadastrar e Entrar", use_container_width=True):
                if n_c and e_c and t_c and s_c:
                    if cadastrar_usuario(n_c, e_c, s_c, t_c):
                        u_novo = validar_login(e_c, s_c)
                        if u_novo:
                            st.session_state.logado = True
                            st.session_state.user_info = u_novo
                            st.rerun()
                    else: st.error("Erro ao cadastrar.")
    st.stop()

# --- DASHBOARD LOGADO ---

# Sincronização automática ao carregar a página (roda uma vez por sessão)
usuarios = supabase.table("usuarios").select("*").execute()
if "auto_sync_done" not in st.session_state and usuarios.data:
    for u in usuarios.data:
        sincronizar_silencioso(u['strava_id'], u['access_token'])
    st.session_state.auto_sync_done = True

# Sidebar
st.sidebar.markdown(f"### 👤 {st.session_state.user_info['nome']}")

auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f"""
    <a href="{auth_url}" target="_self" style="text-decoration: none;">
        <div style="background-color: #FC4C02; color: white; text-align: center; padding: 10px; border-radius: 8px; font-weight: bold; margin-bottom: 20px;">
            🟠 Conectar ao Strava
        </div>
    </a>
""", unsafe_allow_html=True)

if usuarios.data:
    opcoes = {u['nome']: u['strava_id'] for u in usuarios.data}
    nome_sel = st.sidebar.selectbox("Selecionar Atleta", list(opcoes.keys()))
    atleta_id = opcoes[nome_sel]

st.sidebar.divider()
if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True):
    st.session_state.logado = False
    st.rerun()

# Conteúdo Principal
if usuarios.data:
    st.title(f"📊 Painel: {nome_sel}")
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(atleta_id)).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')
        
        st.subheader("📈 Carga Aguda vs Crônica")
        df['Aguda'] = df['trimp_score'].rolling(7).mean()
        df['Cronica'] = df['trimp_score'].rolling(28).mean()
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df['data_treino'], df['Aguda'], label="Aguda", color="#007bff", linewidth=2)
        ax.plot(df['data_treino'], df['Cronica'], label="Crônica", color="#6c757d", ls="--")
        ax.fill_between(df['data_treino'], df['Aguda'], alpha=0.1, color="#007bff")
        ax.legend()
        st.pyplot(fig)
else:
    st.info("Conecte ao Strava para começar.")
