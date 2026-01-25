import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# 1. Carregar variáveis
load_dotenv()

# 2. Conectar ao Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# 3. Credenciais do Strava (PEGANDO DO SECRETS DO STREAMLIT)
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
# COLOQUE AQUI A URL EXATA DO SEU APP NO NAVEGADOR (SEM BARRA NO FINAL)
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

st.set_page_config(page_title="Elite Performance Dashboard", layout="wide")

# --- LÓGICA DE LOGIN (OAUTH2) ---
if "code" in st.query_params:
    code = st.query_params["code"]
    st.info("🔄 Autenticando com o Strava...")
    
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
        st.success(f"✅ Conectado como {response['athlete']['firstname']}!")
        st.rerun() # Limpa o código da URL e recarrega
    else:
        st.error("❌ Falha na conexão com Strava.")

# --- BARRA LATERAL ---
st.sidebar.title("Configurações")

# Botão de Login
auth_url = (
    f"https://www.strava.com/oauth/authorize?"
    f"client_id={CLIENT_ID}&"
    f"response_type=code&"
    f"redirect_uri={REDIRECT_URI}&"
    f"approval_prompt=force&"
    f"scope=read,activity:read_all"
)
st.sidebar.link_button("🟠 Conectar Novo Atleta", auth_url)

# Seleção de Atleta
atleta_id_selecionado = None
nome_selecionado = ""

try:
    usuarios_db = supabase.table("usuarios").select("nome, strava_id").execute()
    if usuarios_db.data:
        lista_nomes = {u['nome']: u['strava_id'] for u in usuarios_db.data}
        nome_selecionado = st.sidebar.selectbox("👤 Selecionar Atleta", list(lista_nomes.keys()))
        atleta_id_selecionado = lista_nomes[nome_selecionado]
except:
    st.sidebar.warning("Tabela 'usuarios' não encontrada.")

# --- CONTEÚDO PRINCIPAL ---
st.title("🚀 Painel de Performance de Elite")

def carregar_dados(atleta_id):
    if not atleta_id:
        return pd.DataFrame()
    response = supabase.table("atividades_fisicas").select("*").eq("atleta_id", atleta_id).execute()
    if not response.data:
        return pd.DataFrame()
    df = pd.DataFrame(response.data)
    df['data_treino'] = pd.to_datetime(df['data_treino'])
    return df.sort_values('data_treino')

df_treinos = carregar_dados(atleta_id_selecionado)

if not df_treinos.empty:
    # Cálculos
    df_treinos['Carga_Aguda'] = df_treinos['trimp_score'].rolling(window=7, min_periods=1).mean()
    df_treinos['Carga_Cronica'] = df_treinos['trimp_score'].rolling(window=28, min_periods=1).mean()
    df_treinos['ACWR'] = df_treinos['Carga_Aguda'] / df_treinos['Carga_Cronica']

    # Métricas
    col1, col2, col3 = st.columns(3)
    ultimo_acwr = df_treinos['ACWR'].iloc[-1]
    
    col1.metric("ACWR Atual", f"{ultimo_acwr:.2f}")
    col2.metric("Status", "✅ Seguro" if 0.8 <= ultimo_acwr <= 1.3 else "⚠️ Risco")
    col3.metric("Total de Treinos", len(df_treinos))

    # Gráfico
    st.subheader(f"Evolução: {nome_selecionado}")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df_treinos['data_treino'], df_treinos['Carga_Aguda'], label="Aguda", color="blue")
    ax.plot(df_treinos['data_treino'], df_treinos['Carga_Cronica'], label="Crônica", color="red", ls="--")
    ax.fill_between(df_treinos['data_treino'], 0.8*df_treinos['Carga_Cronica'], 1.3*df_treinos['Carga_Cronica'], color='green', alpha=0.1)
    ax.set_xlim([datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=2)])
    ax.legend()
    st.pyplot(fig)
else:
    st.warning("Selecione um atleta ou conecte uma conta para ver os dados.")
