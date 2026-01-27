import streamlit as st
import pandas as pd
import os
import requests
import hashlib
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client

# 1. CONFIGURAÇÕES INICIAIS
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

# Conexões
supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app"

# --- FUNÇÕES CORE ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone_destino):
    """Função com Logs de Diagnóstico para WhatsApp"""
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER") 
        
        if not sid or not token:
            st.error("❌ Erro: Credenciais do Twilio não configuradas.")
            return False

        client = Client(sid, token)
        
        # Limpa e formata números
        tel_limpo = ''.join(filter(str.isdigit, str(telefone_destino)))
        p_from_limpo = p_from.replace("whatsapp:", "").replace("+", "").strip()
        
        # LOG DE TENTATIVA
        st.info(f"📡 Tentando enviar para: +{tel_limpo}...")

        message = client.messages.create(
            body=mensagem,
            from_=f"whatsapp:+{p_from_limpo}",
            to=f"whatsapp:+{tel_limpo}"
        )
        
        # MOSTRA STATUS REAL DO TWILIO
        st.success(f"✅ Twilio recebeu! Status: {message.status}")
        return True
    except Exception as e:
        st.error(f"❌ Erro Crítico no Twilio: {str(e)}")
        return False

def sincronizar_dados(strava_id, access_token):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        res = requests.get(url, headers=headers, params={'per_page': 15})
        if res.status_code == 200:
            atividades = res.json()
            for atv in atividades:
                payload = {
                    "id_atleta": int(strava_id),
                    "data_treino": atv['start_date_local'],
                    "trimp_score": atv['moving_time'] / 60,
                    "distancia": atv['distance'] / 1000,
                    "tipo_esporte": atv['type']
                }
                supabase.table("atividades_fisicas").upsert(payload).execute()
            return True
        return False
    except: return False

# --- TELA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🏃‍♂️ Seu Treino App")
        with st.container(border=True):
            e = st.text_input("E-mail")
            s = st.text_input("Senha", type="password")
            if st.button("Entrar", use_container_width=True, type="primary"):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado = True
                    st.session_state.user_info = u.data[0]
                    st.rerun()
                else: st.error("E-mail ou senha incorretos.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# =================================================================
# 👨‍🏫 VISÃO ADMINISTRADOR (TREINADOR)
# =================================================================
if eh_admin:
    with st.sidebar:
        st.title(f"👨‍🏫 {user['nome']}")
        st.divider()
        
        # Link Strava
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
        st.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR NOVO ATLETA</div></a>', unsafe_allow_html=True)

        res_strava = supabase.table("usuarios").select("*").execute()
        
        if res_strava.data:
            atletas = {u['nome']: u for u in res_strava.data}
            sel = st.selectbox("Selecionar Aluno", list(atletas.keys()))
            atleta_foco = atletas[sel]
            
            st.divider()
            dias_filtro = st.radio("Período", [7, 30, 90, "Tudo"], index=1)
            
            if st.button("🔄 Sincronizar Agora", use_container_width=True, type="primary"):
                if sincronizar_dados(atleta_foco['strava_id'], atleta_foco['access_token']):
                    enviar_whatsapp(f"✅ Treinos de {sel} atualizados!", user['telefone'])
                    st.rerun()
            
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.logado = False
                st.rerun()
        else:
            if st.button("🚪 Sair", use_container_width=True):
                st.session_state.logado = False
                st.rerun()

    if res_strava.data:
        st.title(f"📊 Dashboard: {sel}")
        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta_foco['strava_id']).execute()
        
        if res_atv.data:
            df = pd.DataFrame(res_atv.data)
            df['dt'] = pd.to_datetime(df['data_treino'], utc=True)
            df = df.sort_values('dt')
            
            # Filtro
            if dias_filtro != "Tudo":
                cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=int(dias_filtro))
                df = df[df['dt'] >= cutoff]

            # ACWR
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            ratio = df['Aguda'].iloc[-1] / df['Cronica'].iloc[-1] if df['Cronica'].iloc[-1] > 0 else 0

            # Métricas
            m1, m2, m3 = st.columns(3)
            m1.metric("Carga Aguda", f"{df['Aguda'].iloc[-1]:.1f}")
            m2.metric("Carga Crônica", f"{df['Cronica'].iloc[-1]:.1f}")
            m3.metric("Rácio ACWR", f"{ratio:.2f}")

            if ratio > 1.5:
                if st.button(f"⚠️ Enviar Alerta de Risco para {sel}"):
                    enviar_whatsapp(f"🚨 {sel}, sua carga de treino está muito alta ({ratio:.2f}). Cuidado com lesões!", user['telefone'])

            st.divider()
            st.subheader("🗓️ Volume e Evolução")
            c1, c2 = st.columns(2)
            df['data_f'] = df['dt'].dt.strftime('%d/%m')
            with c1: st.bar_chart(df.groupby('data_f')['distancia'].sum())
            with c2: st.line_chart(df.set_index('data_f')[['Aguda', 'Cronica']])

# =================================================================
# 🏃‍♂️ VISÃO ATLETA (CLIENTE)
# =================================================================
else:
    with st.sidebar:
        st.title(f"🏃‍♂️ {user['nome']}")
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logado = False
            st.rerun()

    st.title(f"🚀 Fala, {user['nome']}!")
    meu_id = user.get('strava_id')
    if meu_id:
        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", meu_id).execute()
        if res_atv.data:
            df = pd.DataFrame(res_atv.data)
            st.metric("Total Percorrido", f"{df['distancia'].sum():.1f} km")
            st.area_chart(df.tail(15).set_index('data_treino')['distancia'])
