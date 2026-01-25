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
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- LÓGICA DE AUTENTICAÇÃO STRAVA ---
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

# Seleção de Atleta do Banco
atleta_id_selecionado = None
nome_atleta = ""

try:
    resp_users = supabase.table("usuarios").select("nome, strava_id").execute()
    if resp_users.data:
        dict_usuarios = {u['nome']: u['strava_id'] for u in resp_users.data}
        nome_atleta = st.sidebar.selectbox("👤 Selecionar Atleta", list(dict_usuarios.keys()))
        atleta_id_selecionado = dict_usuarios[nome_atleta]
except Exception as e:
    st.sidebar.error(f"Erro ao carregar lista de atletas: {e}")

# --- FUNÇÃO DE DADOS (CORREÇÃO DO TIPO BIGINT) ---
def carregar_dados(id_do_atleta):
    if not id_do_atleta:
        return pd.DataFrame()
    
    try:
        # CONVERSÃO CRUCIAL: O banco espera um BigInt (número), não texto.
        id_numerico = int(id_do_atleta)
        
        res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", id_numerico).execute()
        
        if not res.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(res.data)
        
        # Mapeando a coluna 'pontos'
        if 'pontos' in df.columns:
            df['trimp_score'] = pd.to_numeric(df['pontos'], errors='coerce')
        
        # Identificando a coluna de data
        col_data = 'dados_treino' if 'dados_treino' in df.columns else 'data_treino'
        if col_data in df.columns:
            df['data_treino_limpa'] = pd.to_datetime(df[col_data])
            return df.sort_values('data_treino_limpa')
            
        return pd.DataFrame()
    except Exception as e:
        # Se der erro aqui, saberemos se ainda é problema de tipo
        st.error(f"Erro na consulta SQL: {e}")
        return pd.DataFrame()

# --- ÁREA PRINCIPAL ---
st.title("📊 Painel de Controle de Carga")

if atleta_id_selecionado:
    df_treinos = carregar_dados(atleta_id_selecionado)

    if not df_treinos.empty and 'trimp_score' in df_treinos.columns:
        # Cálculos de Carga
        df_treinos['Carga_Aguda'] = df_treinos['trimp_score'].rolling(window=7, min_periods=1).mean()
        df_treinos['Carga_Cronica'] = df_treinos['trimp_score'].rolling(window=28, min_periods=1).mean()
        df_treinos['ACWR'] = df_treinos['Carga_Aguda'] / df_treinos['Carga_Cronica']

        # Métricas
        c1, c2, c3 = st.columns(3)
        ultimo_acwr = df_treinos['ACWR'].iloc[-1]
        
        with c1:
            st.metric("ACWR Atual", f"{ultimo_acwr:.2f}")
        with c2:
            status = "✅ Seguro" if 0.8 <= ultimo_acwr <= 1.3 else "⚠️ Risco"
            st.metric("Status", status)
        with c3:
            st.metric("Treinos Registrados", len(df_treinos))

        # Gráfico
        st.subheader(f"Evolução de Carga: {nome_atleta}")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df_treinos['data_treino_limpa'], df_treinos['Carga_Aguda'], label="Aguda (7d)", color="#1E90FF")
        ax.plot(df_treinos['data_treino_limpa'], df_treinos['Carga_Cronica'], label="Crônica (28d)", color="#FF4500", linestyle="--")
        ax.fill_between(df_treinos['data_treino_limpa'], 0.8 * df_treinos['Carga_Cronica'], 1.3 * df_treinos['Carga_Cronica'], color='green', alpha=0.1)
        ax.legend()
        st.pyplot(fig)
    else:
        st.info(f"Dados carregados, mas faltam colunas de performance para {nome_atleta}.")
else:
    st.info("Aguardando seleção de atleta...")
