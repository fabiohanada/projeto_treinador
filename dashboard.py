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
REDIRECT_URI = "https://seu-treino-app.streamlit.app" # Ajuste para sua URL real

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
    # Limpa o telefone: deixa apenas números
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
    except Exception as e:
        st.error(f"Erro no cadastro: {e}")
        return False

# --- FUNÇÃO DE WHATSAPP DINÂMICA ---
def enviar_whatsapp_twilio(mensagem):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        phone_from = get_secret("TWILIO_PHONE_NUMBER")
        
        # Pega o telefone do usuário logado na sessão
        phone_to = st.session_state.user_info.get('telefone')
        
        if not all([sid, token, phone_from, phone_to]):
            return False

        client = Client(sid, token)
        # Garante o prefixo whatsapp: exigido pelo Twilio
        p_from = f"whatsapp:{phone_from.replace('whatsapp:', '')}"
        p_to = f"whatsapp:{phone_to.replace('whatsapp:', '')}"

        client.messages.create(body=mensagem, from_=p_from, to=p_to)
        return True
    except:
        return False

# --- FUNÇÃO DE SINCRONIZAÇÃO STRAVA ---
def sincronizar_atividades(strava_id, access_token, nome_atleta):
    url_atv = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        atividades = requests.get(url_atv, headers=headers, params={'per_page': 10}).json()
        if isinstance(atividades, list) and len(atividades) > 0:
            recente = atividades[0]
            dist = recente.get('distance', 0) / 1000
            dur = recente.get('moving_time', 0) / 60
            
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
            
            msg = (f"🚀 *Treino Sincronizado!*\n\n"
                   f"👤 *Atleta:* {nome_atleta}\n"
                   f"📏 *Distância:* {dist:.2f} km\n"
                   f"⏱️ *Duração:* {dur:.1f} min")
            enviar_whatsapp_twilio(msg)
            return True
    except:
        pass
    return False

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_info = None

# --- INTERFACE: LOGIN / CADASTRO ---
if not st.session_state.logado:
    st.markdown("""
        <style>
        div.stButton > button:first-child {
            background-color: #28a745;
            color: white;
            border: none;
        }
        div.stButton > button:first-child:hover {
            background-color: #218838;
            color: white;
        }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔐 Elite Login</h2>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Login", "Cadastro"])
        
        with tab1:
            e = st.text_input("Email")
            s = st.text_input("Senha", type="password")
            if st.button("Entrar", use_container_width=True):
                u = validar_login(e, s)
                if u:
                    st.session_state.logado = True
                    st.session_state.user_info = u
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
        
        with tab2:
            n_c = st.text_input("Nome Completo")
            e_c = st.text_input("Email de Acesso")
            t_c = st.text_input("WhatsApp (ex: 5511999999999)")
            s_c = st.text_input("Sua Senha", type="password")
            if st.button("Criar Conta", use_container_width=True):
                if n_c and e_c and t_c and s_c:
                    # ESTAS LINHAS ABAIXO DEVEM TER UM "TAB" A MAIS
                    if cadastrar_usuario(n_c, e_c, s_c, t_c):
                        st.success("Conta criada! Faça login.")
                    else:
                        st.error("Erro ao criar conta.")
