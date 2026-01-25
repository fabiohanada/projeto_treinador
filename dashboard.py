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
# IMPORTANTE: Esta URL deve ser IGUAL à do seu app no Streamlit Cloud
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

# --- FUNÇÃO DE SINCRONIZAÇÃO STRAVA ---
def sincronizar_atividades(strava_id, access_token, nome_atleta):
    url_atv = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        atividades = requests.get(url_atv, headers=headers, params={'per_page': 15}).json()
        if isinstance(atividades, list) and len(atividades) > 0:
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
            
            recente = atividades[0]
            msg = (f"🚀 *Treino Sincronizado!*\n\n"
                   f"👤 *Atleta:* {nome_atleta}\n"
                   f"📏 *Distância:* {recente.get('distance',0)/1000:.2f} km")
            enviar_whatsapp_twilio(msg)
            return True
    except: pass
    return False

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_info = None

# --- INTERFACE: LOGIN / CADASTRO ---
if not st.session_state.logado:
    st.markdown("""
        <style>
        div.stButton > button:first-child { background-color: #007bff; color: white; border: none; font-weight: bold; }
        div.stButton > button:first-child:hover { background-color: #0056b3; color: white; }
        h2 { color: #007bff; text-align: center; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<h2>💙 Elite Performance</h2>", unsafe_allow_html=True)
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
                        u = validar_login(e_c, s_c)
                        if u:
                            st.session_state.logado = True
                            st.session_state.user_info = u
                            st.rerun()
                    else: st.error("Erro ao cadastrar.")
    st.stop()

# --- LÓGICA DE CAPTURA DO STRAVA (NA MESMA TELA) ---
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
        # Sincroniza logo após autorizar
        sincronizar_atividades(u_strava["strava_id"], u_strava["access_token"], u_strava["nome"])
        # Limpa a URL e atualiza a tela
        st.query_params.clear()
        st.rerun()

# --- DASHBOARD PRINCIPAL ---
st.sidebar.markdown(f"### 👤 {st.session_state.user_info['nome']}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.link_button("🟠 Conectar ao Strava", auth_url)

usuarios = supabase.table("usuarios").select("*").execute()
if usuarios.data:
    opcoes = {u['nome']: u['strava_id'] for u in usuarios.data}
    nome_sel = st.sidebar.selectbox("Selecionar Atleta", list(opcoes.keys()))
    atleta_id = opcoes[nome_sel]
    token_atleta = next(u['access_token'] for u in usuarios.data if u['strava_id'] == atleta_id)

    if st.sidebar.button("🔄 Sincronizar Agora"):
        if sincronizar_atividades(atleta_id, token_atleta, nome_sel):
            st.sidebar.success("Dados atualizados!")
            st.rerun()

    # Exibição dos Gráficos
    st.title("📊 Painel de Performance")
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(atleta_id)).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')
        
        # Gráfico Carga
        st.subheader("📈 Carga Aguda (7d) vs Crônica (28d)")
        df['Aguda'] = df['trimp_score'].rolling(7).mean()
        df['Cronica'] = df['trimp_score'].rolling(28).mean()
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df['data_treino'], df['Aguda'], label="Aguda", color="#007bff", linewidth=2)
        ax.plot(df['data_treino'], df['Cronica'], label="Crônica", color="#6c757d", ls="--")
        ax.fill_between(df['data_treino'], df['Aguda'], alpha=0.1, color="#007bff")
        ax.legend()
        st.pyplot(fig)

        # Gráfico Volume
        st.divider()
        st.subheader("📅 Volume de Treino Semanal (km)")
        df_sem = df.resample('W-MON', on='data_treino')['distancia'].sum().reset_index()
        fig2, ax2 = plt.subplots(figsize=(10, 3))
        ax2.bar(df_sem['data_treino'].dt.strftime('%d/%m'), df_sem['distancia'], color='#007bff')
        st.pyplot(fig2)
else:
    st.info("Conecte ao Strava para começar a visualizar os dados.")
