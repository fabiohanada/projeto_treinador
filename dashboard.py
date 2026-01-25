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

# --- FUNÇÃO PARA BUSCAR DADOS DO STRAVA E SALVAR NO BANCO ---
def sincronizar_atividades(strava_id, access_token):
    url_atividades = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'per_page': 50} # Puxa as últimas 50 atividades
    
    try:
        response = requests.get(url_atividades, headers=headers, params=params).json()
        
        if isinstance(response, list):
            for atividade in response:
                # Cálculo de carga simples: moving_time em minutos
                # Você pode melhorar essa fórmula depois
                pontos_estimados = atividade['moving_time'] / 60
                
                dados_treino = {
                    "id_atleta": int(strava_id),
                    "dados_treino": atividade['start_date_local'],
                    "pontos": pontos_estimados,
                    "duracao_min": atividade['moving_time'] / 60,
                    "tipo": atividade['type'],
                    "nome_atividade": atividade['name']
                }
                # Upsert usa a data/hora como chave única para não duplicar
                supabase.table("atividades_fisicas").upsert(dados_treino).execute()
            return True
    except Exception as e:
        st.error(f"Erro ao sincronizar: {e}")
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
            
            # Sincroniza logo após o primeiro login
            sincronizar_atividades(user_data["strava_id"], user_data["access_token"])
            
            st.success(f"✅ Atleta {user_data['nome']} conectado e dados sincronizados!")
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
dados_usuario = None

try:
    resp_users = supabase.table("usuarios").select("*").execute()
    if resp_users.data:
        dict_usuarios = {u['nome']: u['strava_id'] for u in resp_users.data}
        nome_atleta = st.sidebar.selectbox("👤 Selecionar Atleta", list(dict_usuarios.keys()))
        atleta_id_selecionado = dict_usuarios[nome_atleta]
        # Pega os dados do usuário selecionado para o refresh
        dados_usuario = next(u for u in resp_users.data if u['strava_id'] == atleta_id_selecionado)
except Exception as e:
    st.sidebar.error("Erro ao carregar atletas.")

# Botão de Atualização Manual
if atleta_id_selecionado and dados_usuario:
    if st.sidebar.button("🔄 Atualizar Dados do Strava"):
        with st.sidebar.spinner("Buscando atividades..."):
            sucesso = sincronizar_atividades(atleta_id_selecionado, dados_usuario['access_token'])
            if sucesso:
                st.sidebar.success("Dados atualizados!")
                st.rerun()

# --- FUNÇÃO DE CARREGAMENTO DE DADOS DO BANCO ---
def carregar_dados_banco(id_do_atleta):
    try:
        res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", int(id_do_atleta)).execute()
        if not res.data:
            return pd.DataFrame()
        
        df = pd.DataFrame(res.data)
        df['data_treino_limpa'] = pd.to_datetime(df['dados_treino'])
        df['trimp_score'] = pd.to_numeric(df['pontos'], errors='coerce')
        return df.sort_values('data_treino_limpa')
    except Exception as e:
        st.error(f"Erro ao ler banco: {e}")
        return pd.DataFrame()

# --- ÁREA PRINCIPAL ---
st.title("📊 Painel de Controle de Carga")

if atleta_id_selecionado:
    df_treinos = carregar_dados_banco(atleta_id_selecionado)

    if not df_treinos.empty:
        # Cálculos de Carga (ACWR)
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
            st.metric("Total de Treinos", len(df_treinos))

        # Gráfico
        st.subheader(f"Evolução: {nome_atleta}")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df_treinos['data_treino_limpa'], df_treinos['Carga_Aguda'], label="Aguda (Fadiga 7d)", color="#1E90FF")
        ax.plot(df_treinos['data_treino_limpa'], df_treinos['Carga_Cronica'], label="Crônica (Fitness 28d)", color="#FF4500", linestyle="--")
        ax.fill_between(df_treinos['data_treino_limpa'], 0.8 * df_treinos['Carga_Cronica'], 1.3 * df_treinos['Carga_Cronica'], color='green', alpha=0.1)
        ax.legend()
        plt.xticks(rotation=45)
        st.pyplot(fig)
        
        with st.expander("Ver atividades no banco"):
            st.write(df_treinos[['data_treino_limpa', 'tipo', 'pontos']].tail(10))
    else:
        st.info(f"O atleta {nome_atleta} está conectado, mas não há atividades no banco. Clique em 'Atualizar Dados' na barra lateral.")
else:
    st.info("Selecione um atleta para visualizar o desempenho.")
