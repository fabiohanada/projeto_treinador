import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from datetime import datetime
from twilio.rest import Client
import hashlib

# 1. Configurações Iniciais
load_dotenv()
st.set_page_config(page_title="Elite Performance Dashboard", layout="wide")

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

# --- FUNÇÕES DE SEGURANÇA E LOGIN ---
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
        
    payload = {
        "nome": nome, 
        "email": email, 
        "senha": senha_hash, 
        "telefone": tel_limpo
    }
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
        
        if not all([sid, token, phone_from, phone_to]):
            return False

        client = Client(sid, token)
        p_from = f"whatsapp:{phone_from.replace('whatsapp:', '')}"
        p_to = f"whatsapp:{phone_to.replace('whatsapp:', '')}"
        client.messages.create(body=mensagem, from_=p_from, to=p_to)
        return True
    except:
        return False

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_info = None

# --- INTERFACE: LOGIN / CADASTRO ---
if not st.session_state.logado:
    # CSS PARA BOTÕES E TÍTULOS AZUIS
    st.markdown("""
        <style>
        div.stButton > button:first-child {
            background-color: #007bff;
            color: white;
            border: none;
            font-weight: bold;
        }
        div.stButton > button:first-child:hover {
            background-color: #0056b3;
            color: white;
        }
        h2 { color: #007bff; text-align: center; }
        .stTabs [data-baseweb="tab-list"] button [data-testid="stWidgetLabel"] { font-size: 18px; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<h2>💙 Elite Performance</h2>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        
        with tab1:
            e = st.text_input("Email", key="login_email")
            s = st.text_input("Senha", type="password", key="login_senha")
            if st.button("Acessar Painel", use_container_width=True):
                u = validar_login(e, s)
                if u:
                    st.session_state.logado = True
                    st.session_state.user_info = u
                    st.rerun()
                else:
                    st.error("E-mail ou senha incorretos.")
        
        with tab2:
            n_c = st.text_input("Nome Completo")
            e_c = st.text_input("Seu melhor E-mail")
            t_c = st.text_input("WhatsApp (ex: 5511999999999)")
            s_c = st.text_input("Crie uma Senha", type="password")
            if st.button("Cadastrar e Entrar", use_container_width=True):
                if n_c and e_c and t_c and s_c:
                    if cadastrar_usuario(n_c, e_c, s_c, t_c):
                        # LOGIN AUTOMÁTICO APÓS CADASTRO
                        novo_usuario = validar_login(e_c, s_c)
                        if novo_usuario:
                            st.session_state.logado = True
                            st.session_state.user_info = novo_usuario
                            st.rerun()
                    else:
                        st.error("Erro ao cadastrar. E-mail já existe?")
                else:
                    st.warning("Preencha todos os campos.")
    st.stop()

# --- DASHBOARD (SÓ APARECE SE LOGADO) ---
st.sidebar.markdown(f"### 👤 {st.session_state.user_info['nome']}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

# [Lógica do Strava e Gráficos abaixo...]
st.title("📊 Painel de Performance")

# Verificação de conexão Strava via URL
if "code" in st.query_params:
    code = st.query_params["code"]
    res = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": code, "grant_type": "authorization_code"
    }).json()
    if 'access_token' in res:
        u_data = {"strava_id": res['athlete']['id'], "nome": res['athlete']['firstname'], "access_token": res['access_token']}
        supabase.table("usuarios").upsert(u_data).execute()
        st.rerun()

auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.link_button("🟠 Conectar ao Strava", auth_url)

# Seleção de Atleta e Gráficos
usuarios = supabase.table("usuarios").select("*").execute()
if usuarios.data:
    opcoes = {u['nome']: u['strava_id'] for u in usuarios.data}
    nome_sel = st.sidebar.selectbox("Selecionar Atleta", list(opcoes.keys()))
    atleta_id = opcoes[nome_sel]
    
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(atleta_id)).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')

        # Gráfico Carga
        st.subheader("📈 Carga de Treino")
        df['Aguda'] = df['trimp_score'].rolling(7).mean()
        df['Cronica'] = df['trimp_score'].rolling(28).mean()
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df['data_treino'], df['Aguda'], label="Aguda", color="#007bff")
        ax.plot(df['data_treino'], df['Cronica'], label="Crônica", color="#6c757d", ls="--")
        ax.legend()
        st.pyplot(fig)

        # Gráfico Volume Semanal
        st.divider()
        st.subheader("📅 Volume Semanal (km)")
        df_sem = df.resample('W-MON', on='data_treino')['distancia'].sum().reset_index()
        fig2, ax2 = plt.subplots(figsize=(10, 3))
        ax2.bar(df_sem['data_treino'].dt.strftime('%d/%m'), df_sem['distancia'], color='#007bff')
        st.pyplot(fig2)
