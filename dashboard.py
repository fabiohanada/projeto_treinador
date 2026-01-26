import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib
from datetime import datetime

# 1. Configurações Iniciais
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

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

# --- FUNÇÕES DE SEGURANÇA E BANCO ---
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
    if not tel_limpo.startswith('+'): tel_limpo = f"+{tel_limpo}"
    
    payload = {
        "nome": nome, 
        "email": email, 
        "senha": senha_hash, 
        "telefone": tel_limpo,
        "is_admin": False, # Por padrão não é admin
        "plano_ativo": True, # Para teste, inicia ativo
        "data_expiracao": "2026-12-31"
    }
    try:
        supabase.table("usuarios_app").insert(payload).execute()
        return True
    except: return False

# --- FUNÇÃO WHATSAPP ---
def enviar_whatsapp(mensagem, telefone_destino):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        phone_from = get_secret("TWILIO_PHONE_NUMBER") # Ex: whatsapp:+14155238886
        
        client = Client(sid, token)
        p_to = f"whatsapp:{telefone_destino}"
        p_from = phone_from if "whatsapp:" in phone_from else f"whatsapp:{phone_from}"
        
        client.messages.create(body=mensagem, from_=p_from, to=p_to)
        return True
    except Exception as e:
        st.error(f"Erro Twilio: {e}")
        return False

# --- FUNÇÃO DE SINCRONIZAÇÃO STRAVA ---
def sincronizar_dados(strava_id, access_token, nome_atleta, telefone):
    url_atv = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        res = requests.get(url_atv, headers=headers, params={'per_page': 5})
        if res.status_code == 200:
            atividades = res.json()
            novos_treinos = 0
            for atv in atividades:
                payload = {
                    "id_atleta": int(strava_id),
                    "data_treino": atv['start_date_local'],
                    "trimp_score": atv['moving_time'] / 60,
                    "distancia": atv['distance'] / 1000,
                    "duracao": int(atv['moving_time'] / 60),
                    "tipo_esporte": atv['type']
                }
                # O Upsert evita duplicados baseados na constraint do banco
                supabase.table("atividades_fisicas").upsert(payload).execute()
                novos_treinos += 1
            
            if novos_treinos > 0:
                dist = atividades[0]['distance'] / 1000
                msg = f"✅ Treino Sincronizado!\nAtleta: {nome_atleta}\nDistância: {dist:.2f}km\nData: {atividades[0]['start_date_local'][:10]}"
                enviar_whatsapp(msg, telefone)
            return True
    except: pass
    return False

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_info = None

# --- FLUXO DE LOGIN/CADASTRO ---
if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.title("🏃‍♂️ Seu Treino App")
        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        with tab1:
            e = st.text_input("E-mail")
            s = st.text_input("Senha", type="password")
            if st.button("Acessar"):
                u = validar_login(e, s)
                if u:
                    st.session_state.logado = True
                    st.session_state.user_info = u
                    st.rerun()
                else: st.error("Falha no login.")
        with tab2:
            n_c = st.text_input("Nome Completo")
            e_c = st.text_input("E-mail de Cadastro")
            t_c = st.text_input("WhatsApp (DDI+DDD+Num)")
            s_c = st.text_input("Crie uma Senha", type="password")
            if st.button("Cadastrar"):
                if cadastrar_usuario(n_c, e_c, s_c, t_c):
                    st.success("Conta criada! Vá para a aba Entrar.")
                else: st.error("Erro ao cadastrar.")
    st.stop()

# --- DASHBOARD LOGADO ---
st.sidebar.title(f"Olá, {st.session_state.user_info['nome']}")

# Menu Administrativo (Só aparece se is_admin for True no banco)
menu = ["Dashboard"]
if st.session_state.user_info.get('is_admin'):
    menu.append("👑 Admin")

escolha = st.sidebar.selectbox("Navegação", menu)

if escolha == "👑 Admin":
    st.title("Painel Administrativo")
    res_users = supabase.table("usuarios_app").select("nome, email, telefone, plano_ativo, data_expiracao").execute()
    df_users = pd.DataFrame(res_users.data)
    st.table(df_users)
    st.stop()

# --- FLUXO DASHBOARD PRINCIPAL ---
usuarios_strava = supabase.table("usuarios").select("*").execute()

# Sidebar Strava
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&...&scope=read,activity:read_all" # simplificado
st.sidebar.markdown(f'[🟠 Conectar Strava]({auth_url})')

if usuarios_strava.data:
    lista_atletas = {u['nome']: u for u in usuarios_strava.data}
    atleta_nome = st.sidebar.selectbox("Selecionar Atleta", list(lista_atletas.keys()))
    atleta_dados = lista_atletas[atleta_nome]

    if st.sidebar.button("🔄 Sincronizar Agora"):
        with st.spinner("Sincronizando..."):
            sincronizar_dados(atleta_dados['strava_id'], atleta_dados['access_token'], atleta_nome, st.session_state.user_info['telefone'])
            st.rerun()

    # --- GRÁFICOS LADO A LADO ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta_dados['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['data_treino'] = pd.to_datetime(df['data_treino']).dt.date
        df = df.sort_values('data_treino')

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🗓️ Atividades por Dia")
            counts = df['data_treino'].value_counts().sort_index()
            st.bar_chart(counts)
        with col2:
            st.subheader("📈 Carga Aguda vs Crônica")
            df['Aguda'] = df['trimp_score'].rolling(7).mean()
            df['Cronica'] = df['trimp_score'].rolling(28).mean()
            st.line_chart(df.set_index('data_treino')[['Aguda', 'Cronica']])
    else:
        st.info("Nenhum treino encontrado para este atleta.")

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
