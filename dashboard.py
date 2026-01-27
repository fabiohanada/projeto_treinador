import streamlit as st
import pandas as pd
import os
import requests
import hashlib
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client

# 1. CONFIGURAÇÕES E CONEXÕES
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app"

# --- FUNÇÕES CORE ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_whatsapp(telefone):
    nums = ''.join(filter(str.isdigit, str(telefone)))
    return f"whatsapp:+{nums}"

def enviar_whatsapp(mensagem, telefone):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        client.messages.create(body=mensagem, from_=p_from, to=formatar_whatsapp(telefone))
        return True
    except: return False

# --- TELA DE LOGIN CENTRALIZADA ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🏃‍♂️ Seu Treino App")
        with st.container(border=True):
            st.subheader("Login")
            e = st.text_input("E-mail", placeholder="exemplo@email.com")
            s = st.text_input("Senha", type="password")
            if st.button("Entrar no Sistema", use_container_width=True, type="primary"):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado = True
                    st.session_state.user_info = u.data[0]
                    st.rerun()
                else:
                    st.error("E-mail ou senha incorretos.")
    st.stop()

# --- VARIÁVEIS DE SESSÃO ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR COMUM ---
st.sidebar.title(f"Olá, {user['nome']}")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

# =================================================================
# 👨‍🏫 VISÃO ADMINISTRADOR (TREINADOR - FÁBIO)
# =================================================================
if eh_admin:
    st.title("👨‍🏫 Painel de Controle do Treinador")
    
    # Botão Strava Fixo
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
    st.sidebar.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR NOVO ATLETA</div></a>', unsafe_allow_html=True)

    # Busca atletas cadastrados no Strava
    res_strava = supabase.table("usuarios").select("*").execute()
    
    if res_strava.data:
        atletas = {u['nome']: u for u in res_strava.data}
        sel = st.sidebar.selectbox("Selecionar Atleta para Análise", list(atletas.keys()))
        atleta_dados = atletas[sel]

        # Processamento de Dados (Admin vê tudo)
        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta_dados['strava_id']).execute()
        if res_atv.data:
            df = pd.DataFrame(res_atv.data)
            df['dt'] = pd.to_datetime(df['data_treino'], utc=True)
            df = df.sort_values('dt')
            
            # Cálculos ACWR
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            ratio = df['Aguda'].iloc[-1] / df['Cronica'].iloc[-1] if df['Cronica'].iloc[-1] > 0 else 0

            # Métricas
            m1, m2, m3 = st.columns(3)
            m1.metric("Carga Aguda", f"{df['Aguda'].iloc[-1]:.1f}")
            m2.metric("Carga Crônica", f"{df['Cronica'].iloc[-1]:.1f}")
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta="PERIGO" if ratio > 1.5 else "OK", delta_color="inverse" if ratio > 1.5 else "normal")

            # Gráficos Lado a Lado
            c1, c2 = st.columns(2)
            df['data_f'] = df['dt'].dt.strftime('%d/%m')
            with c1:
                st.subheader("🗓️ Volume por Dia")
                st.bar_chart(df.groupby('data_f')['distancia'].sum())
            with c2:
                st.subheader("📈 Carga Aguda vs Crônica")
                st.line_chart(df.set_index('data_f')[['Aguda', 'Cronica']])
    else:
        st.info("Nenhum atleta vinculado. Use o botão laranja para conectar o Strava de um aluno.")

# =================================================================
# 🏃‍♂️ VISÃO ATLETA (CLIENTE)
# =================================================================
else:
    st.title(f"🚀 Sua Evolução, {user['nome']}")
    
    # O Atleta só vê os dados onde o id_atleta no Supabase bate com o strava_id dele
    meu_strava_id = user.get('strava_id')
    
    if meu_strava_id:
        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", meu_strava_id).execute()
        if res_atv.data:
            df = pd.DataFrame(res_atv.data)
            df['dt'] = pd.to_datetime(df['data_treino'], utc=True)
            
            # Barra de Meta Semanal
            st.subheader("🏁 Sua Meta Semanal")
            meta = 40.0 # Exemplo
            km_semana = df[df['dt'] >= (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7))]['distancia'].sum()
            st.progress(min(km_semana/meta, 1.0))
            st.write(f"Você correu **{km_semana:.1f}km** de uma meta de **{meta}km**.")

            # Gráfico de esforço simplificado
            st.subheader("📈 Histórico de Esforço")
            st.area_chart(df.tail(15).set_index('data_treino')['trimp_score'])
        else:
            st.info("Aguardando seu treinador sincronizar seus primeiros treinos!")
    else:
        st.warning("⚠️ Conta em análise. Seu treinador precisa vincular seu Strava ID para você ver os gráficos.")
