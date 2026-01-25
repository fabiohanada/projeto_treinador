import streamlit as st
import pd as pd
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
# O Streamlit Cloud vai ler dos "Secrets"
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# 3. Credenciais do Strava
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
# AJUSTE: Use a URL exata do seu app no Streamlit Cloud
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- LÓGICA DE CONEXÃO DE NOVO ATLETA (OAUTH2) ---
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
            st.success(f"✅ Atleta {response['athlete']['firstname']} conectado com sucesso!")
            st.rerun()
    except Exception as e:
        st.error(f"Erro na autenticação: {e}")

# --- BARRA LATERAL ---
st.sidebar.title("🚀 Menu de Performance")

# Botão de Login Strava
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
    st.sidebar.error("Erro ao carregar lista de atletas.")

# --- FUNÇÃO DE DADOS (CORRIGIDA PARA SEUS PRINTS) ---
def carregar_dados(id_do_atleta):
    if not id_do_atleta:
        return pd.DataFrame()
    
    try:
        # Usando 'id_atleta' conforme seu print do Supabase
        res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", id_do_atleta).execute()
        
        if not res.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(res.data)
        
        # Ajuste de colunas flexível (data_treino ou dados_treino)
        col_data = 'dados_treino' if 'dados_treino' in df.columns else 'data_treino'
        
        if col_data in df.columns:
            df['data_treino_limpa'] = pd.to_datetime(df[col_data])
            return df.sort_values('data_treino_limpa')
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro no banco: {e}")
        return pd.DataFrame()

# --- ÁREA PRINCIPAL ---
st.title("📊 Painel de Controle de Carga")

df_treinos = carregar_dados(atleta_id_selecionado)

if not df_treinos.empty:
    # Cálculos de Carga (ACWR)
    df_treinos['Carga_Aguda'] = df_treinos['trimp_score'].rolling(window=7, min_periods=1).mean()
    df_treinos['Carga_Cronica'] = df_treinos['trimp_score'].rolling(window=28, min_periods=1).mean()
    df_treinos['ACWR'] = df_treinos['Carga_Aguda'] / df_treinos['Carga_Cronica']

    # Métricas de Elite
    c1, c2, c3 = st.columns(3)
    ultimo_acwr = df_treinos['ACWR'].iloc[-1]
    
    with c1:
        st.metric("ACWR Atual", f"{ultimo_acwr:.2f}")
    with c2:
        status = "✅ Seguro" if 0.8 <= ultimo_acwr <= 1.3 else "⚠️ Risco de Lesão"
        st.metric("Status", status)
    with c3:
        st.metric("Treinos Registrados", len(df_treinos))

    # Gráfico de Performance
    st.subheader(f"Evolução: {nome_atleta}")
    fig, ax = plt.subplots(figsize=(10, 4))
    
    ax.plot(df_treinos['data_treino_limpa'], df_treinos['Carga_Aguda'], label="Carga Aguda (7d)", color="#1E90FF", linewidth=2)
    ax.plot(df_treinos['data_treino_limpa'], df_treinos['Carga_Cronica'], label="Carga Crônica (28d)", color="#FF4500", linestyle="--")
    
    # Zona Segura (Corredor de Performance)
    ax.fill_between(df_treinos['data_treino_limpa'], 
                    0.8 * df_treinos['Carga_Cronica'], 
                    1.3 * df_treinos['Carga_Cronica'], 
                    color='green', alpha=0.1, label="Zona Segura (0.8 - 1.3)")
    
    ax.set_ylabel("TRIMP Score")
    ax.set_xlim([datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=1)])
    ax.legend()
    st.pyplot(fig)
    
    # Tabela de Dados recentes
    with st.expander("Ver histórico de treinos"):
        st.dataframe(df_treinos[['data_treino_limpa', 'trimp_score', 'ACWR']].tail(10))
else:
    st.info("💡 Para começar, selecione um atleta na barra lateral ou conecte uma nova conta Strava.")
