import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# 1. Configurações Iniciais
load_dotenv()
st.set_page_config(page_title="Elite Performance Dashboard", layout="wide")

# 2. Conectar ao Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# 3. Credenciais do Strava
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
# AJUSTE: Certifique-se que esta URL está igual à cadastrada no Strava API
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÃO DE SINCRONIZAÇÃO (VERSÃO FINAL BLINDADA) ---
def sincronizar_atividades(strava_id, access_token):
    url_atividades = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'per_page': 50}
    
    try:
        atividades = requests.get(url_atividades, headers=headers, params=params).json()
        
        if isinstance(atividades, list):
            for atividade in atividades:
                # Monta o payload conforme as colunas reais do seu Supabase
                payload = {
                    "id_atleta": int(strava_id),
                    "data_treino": atividade['start_date_local'],
                    "trimp_score": atividade['moving_time'] / 60, # Cálculo base: 1 pt/min
                    "distancia": atividade['distance'] / 1000,   # Metros para Km
                    "duracao": int(atividade['moving_time'] / 60),
                    "tipo_esporte": atividade['type']
                }
                
                # UPSERT: O segredo para evitar o erro 23505 (chave duplicada)
                # Ele tenta inserir. Se já existir (id_atleta + data_treino), ele atualiza.
                supabase.table("atividades_fisicas").upsert(
                    payload, 
                    on_conflict="id_atleta, data_treino"
                ).execute()
            return True
    except Exception as e:
        st.error(f"Erro técnico na sincronização: {e}")
    return False

# --- LÓGICA DE AUTENTICAÇÃO STRAVA (OAUTH2) ---
if "code" in st.query_params:
    code = st.query_params["code"]
    try:
        response = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code"
        }).json()

        if 'access_token' in response:
            user_data = {
                "strava_id": response['athlete']['id'],
                "nome": response['athlete']['firstname'],
                "access_token": response['access_token'],
                "refresh_token": response['refresh_token'],
                "expires_at": response['expires_at']
            }
            supabase.table("usuarios").upsert(user_data).execute()
            
            # Sincroniza imediatamente após o login
            sincronizar_atividades(user_data["strava_id"], user_data["access_token"])
            
            st.success(f"✅ Atleta {user_data['nome']} conectado com sucesso!")
            st.rerun()
    except Exception as e:
        st.error(f"Erro na autenticação: {e}")

# --- BARRA LATERAL ---
st.sidebar.title("🚀 Menu de Performance")

auth_url = (
    f"https://www.strava.com/oauth/authorize?"
    f"client_id={CLIENT_ID}&"
    f"response_type=code&"
    f"redirect_uri={REDIRECT_URI}&"
    f"approval_prompt=force&"
    f"scope=read,activity:read_all"
)
st.sidebar.link_button("🟠 Conectar Novo Atleta", auth_url)
st.sidebar.divider()

# Seleção de Atleta
atleta_id_selecionado = None
nome_atleta = ""
token_atual = None

try:
    resp_users = supabase.table("usuarios").select("*").execute()
    if resp_users.data:
        dict_usuarios = {u['nome']: u['strava_id'] for u in resp_users.data}
        nome_atleta = st.sidebar.selectbox("👤 Selecionar Atleta", list(dict_usuarios.keys()))
        atleta_id_selecionado = dict_usuarios[nome_atleta]
        
        # Recupera o token para o botão de atualização manual
        for u in resp_users.data:
            if u['strava_id'] == atleta_id_selecionado:
                token_atual = u['access_token']
except Exception as e:
    st.sidebar.error("Erro ao carregar atletas.")

# Botão de Sincronização Manual
if atleta_id_selecionado and token_atual:
    if st.sidebar.button("🔄 Sincronizar Agora"):
        with st.sidebar.spinner("Buscando treinos novos..."):
            if sincronizar_atividades(atleta_id_selecionado, token_atual):
                st.sidebar.success("Sincronizado!")
                st.rerun()

# --- ÁREA PRINCIPAL ---
st.title("📊 Painel de Controle de Carga")

if atleta_id_selecionado:
    # Busca dados usando os nomes de colunas que confirmamos no Passo 2
    res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(atleta_id_selecionado)).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')

        # Cálculos de Performance (ACWR)
        df['Aguda'] = df['trimp_score'].rolling(window=7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(window=28, min_periods=1).mean()
        df['ACWR'] = df['Aguda'] / df['Cronica']

        # Cards de Métricas
        c1, c2, c3 = st.columns(3)
        ultimo_acwr = df['ACWR'].iloc[-1]
        
        with c1:
            st.metric("ACWR Atual", f"{ultimo_acwr:.2f}")
        with c2:
            status = "✅ Seguro" if 0.8 <= ultimo_acwr <= 1.3 else "⚠️ Risco"
            st
