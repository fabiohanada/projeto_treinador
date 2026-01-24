import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

load_dotenv()

# Conectar ao banco
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Configurações do App Strava (Mova estas para o Secrets do Streamlit Cloud depois)
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-app.streamlit.app" # Ajuste para sua URL final

st.set_page_config(page_title="Elite Performance Dashboard", layout="wide")

# --- LÓGICA DE LOGIN (OAUTH2) ---
query_params = st.query_params

if "code" in query_params:
    code = query_params["code"]
    st.info("🔄 Autenticando com o Strava...")
    
    # Trocar código pelo Token
    response = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    }).json()

    if 'access_token' in response:
        # Salva ou atualiza o usuário no banco
        user_data = {
            "strava_id": response['athlete']['id'],
            "nome": response['athlete']['firstname'],
            "access_token": response['access_token'],
            "refresh_token": response['refresh_token'],
            "expires_at": response['expires_at']
        }
        supabase.table("usuarios").upsert(user_data).execute()
        st.success(f"✅ Conectado como {response['athlete']['firstname']}! Seus dados aparecerão em breve.")
        # Limpa os parâmetros da URL para ficar limpo
        st.query_params.clear()
    else:
        st.error("❌ Falha na conexão com Strava.")

# --- INTERFACE PRINCIPAL ---
st.title("🚀 Painel de Performance de Elite")

# Sidebar para seleção de atleta (O diferencial para treinadores!)
try:
    usuarios_db = supabase.table("usuarios").select("nome, strava_id").execute()
    if usuarios_db.data:
        lista_nomes = {u['nome']: u['strava_id'] for u in usuarios_db.data}
        nome_selecionado = st.sidebar.selectbox("👤 Selecionar Atleta", list(lista_nomes.keys()))
        atleta_id_selecionado = lista_nomes[nome_selecionado]
    else:
        atleta_id_selecionado = None
except:
    st.sidebar.warning("Tabela 'usuarios' não encontrada no banco.")
    atleta_id_selecionado = None

# Botão para novos usuários
st.sidebar.divider()
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.link_button("➕ Conectar Novo Atleta", auth_url)

# 1. Buscar dados do Supabase filtrando pelo atleta selecionado
def carregar_dados(atleta_id):
    if not atleta_id:
        return pd.DataFrame()
    
    # Filtrando no banco pelo ID do atleta selecionado
    response = supabase.table("atividades_fisicas").select("*").eq("atleta_id", atleta_id).execute()
    
    if not response.data:
        return pd.DataFrame()
    
    df = pd.DataFrame(response.data)
    if 'data_treino' in df.columns:
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')
    return df

df_treinos = carregar_dados(atleta_id_selecionado)

if not df_treinos.empty:
    # ... (Mantenha o restante do seu código de cálculos e gráficos aqui)
    # 2. Cálculos para o Gráfico
    df_treinos['Carga_Aguda'] = df_treinos['trimp_score'].rolling(window=7, min_periods=1).mean()
    df_treinos['Carga_Cronica'] = df_treinos['trimp_score'].rolling(window=28, min_periods=1).mean()
    df_treinos['ACWR'] = df_treinos['Carga_Aguda'] / df_treinos['Carga_Cronica']

    # 3. Layout do Dashboard
    col1, col2, col3 = st.columns(3)
    ultimo_acwr = df_treinos['ACWR'].iloc[-1]
    
    with col1:
        st.metric("ACWR Atual", f"{ultimo_acwr:.2f}")
    with col2:
        status = "✅ Seguro" if 0.8 <= ultimo_acwr <= 1.3 else "⚠️ Risco"
        st.metric("Status de Lesão", status)
    with col3:
        st.metric("Total de Treinos", len(df_treinos))

    # 4. Gráfico de Evolução
    st.subheader(f"Evolução da Carga: {nome_selecionado}")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df_treinos['data_treino'], df_treinos['Carga_Aguda'], label="Aguda (7d)", color="blue")
    ax.plot(df_treinos['data_treino'], df_treinos['Carga_Cronica'], label="Crônica (28d)", color="red", linestyle="--")
    
    ax.fill_between(df_treinos['data_treino'], 
                    0.8 * df_treinos['Carga_Cronica'], 
                    1.3 * df_treinos['Carga_Cronica'], 
                    color='green', alpha=0.1, label="Zona Segura")
    
    ax.set_xlim([datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=2)])
    ax.legend()
    st.pyplot(fig)
else:
    st.warning("Nenhum treino encontrado para este atleta.")