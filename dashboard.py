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

# --- LÓGICA DE CAPTURA DO STRAVA (CASO VOLTE PARA A TELA DE LOGIN) ---
if "code" in st.query_params:
    code = st.query_params["code"]
    res_token = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": code, "grant_type": "authorization_code"
    }).json()
    if 'access_token' in res_token:
        u_strava = {"strava_id": res_token['athlete']['id'], "nome": res_token['athlete']['firstname'], "access_token": res_token['access_token']}
        supabase.table("usuarios").upsert(u_strava).execute()
