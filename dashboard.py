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

# --- FUNÇÕES DE SEGURANÇA ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def validar_login(email, senha):
    senha_hash = hash_senha(senha)
    try:
        res = supabase.table("usuarios_app").select("*").eq("email", email).eq("senha", senha_hash).execute()
        return res.data[0] if res.data else None
    except: return None

def cadastrar_usuario(nome, email, senha, telefone):
    senha_hash = hash_senha(senha)
    tel_limpo = ''.join(filter(str.isdigit, telefone))
    if not tel_limpo.startswith('+'): tel_limpo = f"+{tel_limpo}"
    
    payload = {
        "nome": nome, "email": email, "senha": senha_hash, "telefone": tel_limpo,
        "is_admin": False, "plano_ativo": True, "data_expiracao": "2026-12-31"
    }
    try:
        supabase.table("usuarios_app").insert(payload).execute()
        return True
    except: return False

# --- FUNÇÃO WHATSAPP ---
def enviar_whatsapp(mensagem, telefone_destino):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        phone_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        client.messages.create(body=mensagem, from_=phone_from, to=f"whatsapp:{telefone_destino}")
        return True
    except: return False

# --- LÓGICA DE TOKEN (RENOVAÇÃO AUTOMÁTICA) ---
def atualizar_token_strava(refresh_token, strava_id):
    url_token = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token', 'refresh_token': refresh_token
    }
    try:
        res = requests.post(url_token, data=payload)
        if res.status_code == 200:
            dados = res.json()
            novo_access = dados['access_token']
            supabase.table("usuarios").update({"access_token": novo_access}).eq("strava_id", strava_id).execute()
            return novo_access
    except: pass
    return None

def sincronizar_dados(strava_id, access_token, refresh_token, nome_atleta, telefone):
    url_atv = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get(url_atv, headers=headers, params={'per_page': 10})
    
    if res.status_code == 401:
        novo_token = atualizar_token_strava(refresh_token, strava_id)
        if novo_token:
            headers = {'Authorization': f'Bearer {novo_token}'}
            res = requests.get(url_atv, headers=headers, params={'per_page': 10})
    
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
                # O Upsert agora funciona pois adicionamos a Unique Constraint no SQL
                supabase.table("atividades_fisicas").upsert(payload).execute()
            except Exception as e:
                st.error(f"Erro ao salvar no banco: {e}")
        
        if atividades:
            ultimo = atividades[0]
            msg = f"✅ Treino Sincronizado!\nAtleta: {nome_atleta}\nDistância: {ultimo['distance']/1000:.2f}km"
            enviar_whatsapp(msg, telefone)
        return True
    return False

# --- INTERFACE DE LOGIN / CADASTRO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_info = None

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🏃‍♂️ Seu Treino App")
        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        with tab1:
            e = st.text_input("E-mail", key="l_email")
            s = st.text_input("Senha", type="password", key="l_pass")
            if st.button("Acessar", use_container_width=True):
                u = validar_login(e, s)
                if u:
                    st.session_state.logado = True
                    st.session_state.user_info = u
                    st.rerun()
                else: st.error("Login inválido.")
        with tab2:
            n_c = st.text_input("Nome Completo", key="c_nome")
            e_c = st.text_input("E-mail", key="c_email")
            t_c = st.text_input("WhatsApp (Ex: 5511999999999)", key="c_tel")
            s_c = st.text_input("Senha", type="password", key="c_pass")
            if st.button("Cadastrar", use_container_width=True):
                if cadastrar_usuario(n_c, e_c, s_c, t_c): st.success("Conta criada! Faça login.")
                else: st.error("Erro ao cadastrar.")
    st.stop()

# --- DASHBOARD ---
st.sidebar.title(f"Olá, {st.session_state.user_info['nome']}")

menu = ["Dashboard"]
if st.session_state.user_info.get('is_admin'): menu.append("👑 Admin")
escolha = st.sidebar.selectbox("Navegação", menu)

if escolha == "👑 Admin":
    st.title("👑 Painel Administrativo")
    res = supabase.table("usuarios_app").select("*").execute()
    st.table(pd.DataFrame(res.data))
    st.stop()

# Botão Strava Laranja
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR AO STRAVA</div></a>', unsafe_allow_html=True)

res_strava = supabase.table("usuarios").select("*").execute()

if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    atleta_sel = st.sidebar.selectbox("Selecionar Atleta", list(atletas.keys()))
    d = atletas[atleta_sel]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        with st.spinner("Sincronizando..."):
            if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token'), atleta_sel, st.session_state.user_info['telefone']):
                st.toast("Sucesso!")
                st.rerun()

    # --- GRÁFICOS CARGA 7/28 DIAS ---
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
    else:
        st.info("Sincronize para ver dados.")

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
