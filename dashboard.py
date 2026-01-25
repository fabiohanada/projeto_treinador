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

# --- FUNÇÃO DE SINCRONIZAÇÃO (AJUSTADA PARA SUAS COLUNAS REAIS) ---
def sincronizar_atividades(strava_id, access_token):
    url_atividades = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'per_page': 50}
    
    try:
        response = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": access_token, # Idealmente usar o refresh_token aqui
            "grant_type": "refresh_token"
        }).json() if "expires_at" in st.session_state and st.session_state.expires_at < datetime.now().timestamp() else {"access_token": access_token}

        token = response.get("access_token", access_token)
        headers = {'Authorization': f'Bearer {token}'}
        
        atividades = requests.get(url_atividades, headers=headers, params=params).json()
        
        if isinstance(atividades, list):
            for atividade in atividades:
                # Payload ajustado para os nomes do seu print do Supabase
                payload = {
                    "id_atleta": int(strava_id),
                    "data_treino": atividade['start_date_local'],
                    "trimp_score": atividade['moving_time'] / 60, # Cálculo simples
                    "distancia": atividade['distance'] / 1000,   # Converte para km
                    "duracao": int(atividade['moving_time'] / 60),
                    "tipo_esporte": atividade['type']
                }
                # Agora o banco sabe que deve comparar id_atleta + data_treino
                supabase.table("atividades_fisicas").upsert(payload).execute()
            return True
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")
    return False

# --- LÓGICA DE AUTENTICAÇÃO ---
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
            sincronizar_atividades(user_data["strava_id"], user_data["access_token"])
            st.success(f"✅ Atleta {user_data['nome']} pronto!")
            st.rerun()
    except Exception as e:
        st.error(f"Erro no login: {e}")

# --- BARRA LATERAL ---
st.sidebar.title("🚀 Menu")
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.link_button("🟠 Conectar Strava", auth_url)

atleta_id = None
nome_atleta = ""
dados_full = None

try:
    usuarios = supabase.table("usuarios").select("*").execute()
    if usuarios.data:
        opcoes = {u['nome']: u['strava_id'] for u in usuarios.data}
        nome_atleta = st.sidebar.selectbox("👤 Atleta", list(opcoes.keys()))
        atleta_id = opcoes[nome_atleta]
        dados_full = next(u for u in usuarios.data if u['strava_id'] == atleta_id)
except:
    st.sidebar.error("Erro ao listar usuários.")

if atleta_id and st.sidebar.button("🔄 Sincronizar Agora"):
    if sincronizar_atividades(atleta_id, dados_full['access_token']):
        st.sidebar.success("Sincronizado!")
        st.rerun()

# --- ÁREA PRINCIPAL ---
st.title("📊 Controle de Carga")

if atleta_id:
    # Busca usando as colunas corretas do seu banco
    res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(atleta_id)).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')

        # Cálculos de Carga
        df['Aguda'] = df['trimp_score'].rolling(window=7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(window=28, min_periods=1).mean()
        df['ACWR'] = df['Aguda'] / df['Cronica']

        # Cards
        c1, c2, c3 = st.columns(3)
        c1.metric("ACWR", f"{df['ACWR'].iloc[-1]:.2f}")
        c2.metric("Última Distância", f"{df['distancia'].iloc[-1]:.1f} km")
        c3.metric("Total Treinos", len(df))

        # Gráfico
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df['data_treino'], df['Aguda'], label="Aguda (7d)", color="#1E90FF")
        ax.plot(df['data_treino'], df['Cronica'], label="Crônica (28d)", color="#FF4500", ls="--")
        ax.fill_between(df['data_treino'], 0.8*df['Cronica'], 1.3*df['Cronica'], color='green', alpha=0.1)
        ax.legend()
        st.pyplot(fig)
    else:
        st.warning("Sem atividades. Clique em 'Sincronizar Agora' na lateral.")
