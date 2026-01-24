import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# 1. Tenta carregar o .env (apenas para teste local)
load_dotenv()

# 2. Conectar ao banco usando os Secrets do Streamlit
# O Streamlit vai ler direto daqui no servidor
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Credenciais do Strava para o Login
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
# IMPORTANTE: Coloque aqui a URL que aparece no seu navegador do Streamlit Cloud
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

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
# --- LÓGICA DE CONEXÃO (NOVO USUÁRIO) ---
# O Strava manda um 'code' na URL após o login
if "code" in st.query_params:
    code = st.query_params["code"]
    st.info("🔄 Finalizando conexão com o Strava...")
    
    # Troca o código pelo Token Real
    response = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code"
    }).json()

    if 'access_token' in response:
        # Salva ou atualiza o usuário no banco
        # Salva o novo usuário na tabela 'usuarios' do Supabase
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
        st.success(f"✅ Conta de {response['athlete']['firstname']} conectada!")
        st.query_params.clear() # Limpa a URL

# --- BARRA LATERAL (SIDEBAR) ---
st.sidebar.title("Configurações")

# Botão Laranja de Conexão
auth_url = (
    f"https://www.strava.com/oauth/authorize?"
    f"client_id={CLIENT_ID}&"
    f"response_type=code&"
    f"redirect_uri={REDIRECT_URI}&"
    f"approval_prompt=force&"
    f"scope=read,activity:read_all"
)
st.sidebar.link_button("🟠 Conectar Novo Atleta", auth_url)

# Menu para escolher o atleta (busca na tabela 'usuarios')
try:
    resp_users = supabase.table("usuarios").select("nome, strava_id").execute()
    if resp_users.data:
        opcoes = {u['nome']: u['strava_id'] for u in resp_users.data}
        selecionado = st.sidebar.selectbox("👤 Selecione o Atleta", list(opcoes.keys()))
        atleta_id = opcoes[selecionado]
    else:
        atleta_id = None
except:
    st.sidebar.error("Crie a tabela 'usuarios' no Supabase!")
    atleta_id = None

# --- CONTEÚDO PRINCIPAL ---
st.title("🚀 Painel de Performance de Elite")

def carregar_dados(id_do_atleta):
    if not id_do_atleta: return pd.DataFrame()
    # Filtra os treinos apenas do atleta selecionado
    response = supabase.table("atividades_fisicas").select("*").eq("atleta_id", id_do_atleta).execute()
    if not response.data: return pd.DataFrame()
    
    df = pd.DataFrame(response.data)
    df['data_treino'] = pd.to_datetime(df['data_treino'])
    return df.sort_values('data_treino')

df_treinos = carregar_dados(atleta_id)

if not df_treinos.empty:
    # Cálculos
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
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    ultimo = df_treinos['ACWR'].iloc[-1]
    c1.metric("ACWR Atual", f"{ultimo:.2f}")
    c2.metric("Status", "✅ Seguro" if 0.8 <= ultimo <= 1.3 else "⚠️ Risco")
    c3.metric("Total Treinos", len(df_treinos))

    # Gráfico
    st.subheader(f"Evolução: {selecionado}")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df_treinos['data_treino'], df_treinos['Carga_Aguda'], label="Aguda", color="blue")
    ax.plot(df_treinos['data_treino'], df_treinos['Carga_Cronica'], label="Crônica", color="red", ls="--")
    ax.fill_between(df_treinos['data_treino'], 0.8*df_treinos['Carga_Cronica'], 1.3*df_treinos['Carga_Cronica'], color='green', alpha=0.1)
    ax.set_xlim([datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=2)])
    ax.legend()
    st.pyplot(fig)
else:
    st.warning("Nenhum treino encontrado para este atleta.")
    st.warning("Selecione um atleta ou conecte uma nova conta para ver os dados.")
