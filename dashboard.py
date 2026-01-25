import streamlit as st
import pandas as pd
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

# --- FUNÇÃO DE SINCRONIZAÇÃO (PODE SER CHAMADA MANUAL OU AUTOMÁTICA) ---
def sincronizar_dados(strava_id, access_token):
    url_atv = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        res = requests.get(url_atv, headers=headers, params={'per_page': 10})
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
        sincronizar_dados(u_strava["strava_id"], u_strava["access_token"])
        st.query_params.clear()
        st.rerun()

# --- INTERFACE: LOGIN ---
if not st.session_state.logado:
    st.markdown("""
        <style>
        div.stButton > button:first-child { background-color: #007bff; color: white; font-weight: bold; border-radius: 8px; height: 45px; }
        .main-header { display: flex; align-items: center; justify-content: center; gap: 10px; margin-bottom: 20px; }
        .runner-icon { font-size: 40px; color: #ff4b4b; }
        .title-text { font-size: 32px; font-weight: bold; color: #31333F; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        st.markdown("<div class='main-header'><span class='runner-icon'>🏃‍♂️</span><span class='title-text'>Seu Treino App</span></div>", unsafe_allow_html=True)
        e = st.text_input("Email")
        s = st.text_input("Senha", type="password")
        if st.button("Acessar Painel", use_container_width=True):
            u = validar_login(e, s)
            if u:
                st.session_state.logado = True
                st.session_state.user_info = u
                st.rerun()
            else: st.error("Dados incorretos.")
    st.stop()

# --- DASHBOARD LOGADO ---
usuarios = supabase.table("usuarios").select("*").execute()

# Sincronização Automática ao Carregar
if "auto_sync_done" not in st.session_state and usuarios.data:
    for u in usuarios.data:
        sincronizar_dados(u['strava_id'], u['access_token'])
    st.session_state.auto_sync_done = True

# --- SIDEBAR ---
st.sidebar.markdown(f"### 👤 {st.session_state.user_info['nome']}")

# Botão Strava Laranja (Normal)
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
    
    # Busca o token do atleta selecionado para o botão manual
    token_atleta = next(u['access_token'] for u in usuarios.data if u['strava_id'] == atleta_id)
    
    # REINSERÇÃO DO BOTÃO SINCRONIZAR
    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        with st.spinner("Atualizando dados..."):
            if sincronizar_dados(atleta_id, token_atleta):
                st.sidebar.success("Sincronizado!")
                st.rerun()

st.sidebar.divider()
if st.sidebar.button("🚪 Sair do Sistema", use_container_width=True):
    st.session_state.logado = False
    st.rerun()

# --- CONTEÚDO PRINCIPAL ---
if usuarios.data:
    st.title(f"📊 Painel: {nome_sel}")
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(atleta_id)).execute()
    
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['data_treino'] = pd.to_datetime(df['data_treino']).dt.date
        df = df.sort_values('data_treino')
        
        # 1. Gráfico de Carga Aguda vs Crônica
        st.subheader("📈 Carga Aguda vs Crônica")
        df_plot = df.copy()
        df_plot['Aguda'] = df_plot['trimp_score'].rolling(7).mean()
        df_plot['Cronica'] = df_plot['trimp_score'].rolling(28).mean()
        st.line_chart(df_plot.set_index('data_treino')[['Aguda', 'Cronica']])

        # 2. Gráfico de Atividades Diárias
        st.divider()
        st.subheader("🗓️ Quantidade de Atividades por Dia")
        contagem_diaria = df['data_treino'].value_counts().sort_index()
        df_barras = pd.DataFrame({'Data': contagem_diaria.index, 'Quantidade': contagem_diaria.values}).set_index('Data')
        st.bar_chart(df_barras, color="#ff4b4b")
    else:
        st.info("Conecte ao Strava para carregar os treinos.")
