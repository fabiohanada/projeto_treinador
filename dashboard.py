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
            # Usa o strava_id como chave primária para evitar duplicatas
            supabase.table("usuarios").upsert(user_data).execute()
            st.success(f"✅ Atleta {response['athlete']['firstname']} conectado!")
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

try:
    resp_users = supabase.table("usuarios").select("nome, strava_id").execute()
    if resp_users.data:
        dict_usuarios = {u['nome']: u['strava_id'] for u in resp_users.data}
        nome_atleta = st.sidebar.selectbox("👤 Selecionar Atleta", list(dict_usuarios.keys()))
        atleta_id_selecionado = dict_usuarios[nome_atleta]
except Exception as e:
    st.sidebar.error("Erro ao carregar lista de atletas.")

# --- FUNÇÃO DE CARREGAMENTO DE DADOS ---
def carregar_dados(id_do_atleta):
    if not id_do_atleta:
        return pd.DataFrame()
    
    try:
        # Buscando dados do atleta específico (BigInt no banco)
        res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(id_do_atleta)).execute()
        
        if not res.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(res.data)
        
        # Mapeamento de colunas baseado no seu print do Supabase
        # Se no banco estiver 'pontos', criamos a 'trimp_score' para o cálculo do ACWR
        if 'pontos' in df.columns:
            df['trimp_score'] = pd.to_numeric(df['pontos'], errors='coerce')
        
        # Identificar coluna de data (dados_treino ou data_inicio)
        col_data = 'dados_treino' if 'dados_treino' in df.columns else 'data_inicio'
        
        if col_data in df.columns:
            df['data_treino_limpa'] = pd.to_datetime(df[col_data])
            return df.sort_values('data_treino_limpa')
        
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao acessar banco de dados: {e}")
        return pd.DataFrame()

# --- ÁREA PRINCIPAL ---
st.title("📊 Painel de Controle de Carga")

if atleta_id_selecionado:
    df_treinos = carregar_dados(atleta_id_selecionado)

    if not df_treinos.empty and 'trimp_score' in df_treinos.columns:
        # Cálculos de Carga (ACWR
