import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        if key in st.secrets: return st.secrets[key]
    except: pass
    return os.getenv(key)

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        tel_limpo = ''.join(filter(str.isdigit, str(telefone)))
        client.messages.create(body=mensagem, from_=p_from, to=f"whatsapp:+{tel_limpo}")
        return True
    except: return False

def sincronizar_dados(strava_id, access_token, refresh_token, nome, telefone):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        res = requests.get(url, headers=headers, params={'per_page': 10})
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
                try: supabase.table("atividades_fisicas").upsert(payload).execute()
                except: continue
            return True
        return False
    except: return False

# --- LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    st.title("🏃‍♂️ Acesso ao Sistema")
    e = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True):
        u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
        if u.data:
            st.session_state.logado, st.session_state.user_info = True, u.data[0]
            st.rerun()
    st.stop()

# --- SIDEBAR (Botão Strava FIXO) ---
st.sidebar.title(f"Treinador: {st.session_state.user_info['nome']}")
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'''
    <a href="{auth_url}" target="_self" style="text-decoration:none;">
        <div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-top:10px;margin-bottom:20px;">
            🟠 CONECTAR NOVO ATLETA
        </div>
    </a>
''', unsafe_allow_html=True)

# --- DASHBOARD ---
res_strava = supabase.table("usuarios").select("*").execute()

if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    sel = st.sidebar.selectbox("Selecionar Atleta", list(atletas.keys()))
    d = atletas[sel]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token'), sel, st.session_state.user_info['telefone']):
            st.toast("Dados atualizados!")
            st.rerun()

    # --- PROCESSAMENTO E MÉTRICAS ACWR ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['dt'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('dt')
        df['data_f'] = df['dt'].dt.strftime('%d/%m/%Y')
        
        # Cálculos de Carga
        df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
        
        ultima_aguda = df['Aguda'].iloc[-1]
        ultima_cronica = df['Cronica'].iloc[-1]
        ratio = ultima_aguda / ultima_cronica if ultima_cronica > 0 else 0

        st.markdown(f"## 📊 Análise de Performance: {sel}")

        # 1. MÉTRICAS DE TOPO
        m1, m2, m3 = st.columns(3)
        m1.metric("Carga Aguda (7d)", f"{ultima_aguda:.1f}")
        m2.metric("Carga Crônica (28d)", f"{ultima_cronica:.1f}")
        
        # 2. LÓGICA ACWR COM ALERTAS
        if ratio > 1.5:
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta="PERIGO", delta_color="inverse")
            st.error(f"🚨 **ALERTA CRÍTICO:** O rácio de {sel} está em {ratio:.2f}. Risco altíssimo de lesão!")
            if st.button("📩 Enviar Alerta Urgente via WhatsApp"):
                enviar_whatsapp(f"🚨 ALERTA: Atleta {sel} com rácio de carga em {ratio:.2f}. Sugerido repouso ou redução de volume.", st.session_state.user_info['telefone'])
        elif 0.8 <= ratio <= 1.3:
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta="EXCELENTE")
            st.success(f"✅ **SWEET SPOT:** {sel} está na zona ideal de evolução (Rácio: {ratio:.2f}).")
        else:
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta="Atenção")
            st.warning(f"ℹ️ O rácio de {sel} está em {ratio:.2f} (Fora da zona ideal).")

        # 3. GRÁFICOS LADO A LADO
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🗓️ Atividades por Dia")
            st.bar_chart(df.groupby('data_f').size())
        with c2:
            st.subheader("📈 Carga Aguda vs Crônica")
            st.line_chart(df.set_index('data_f')[['Aguda', 'Cronica']])
    else:
        st.info("Sincronize os dados para gerar as análises de carga.")

else:
    st.info("Conecte um atleta no botão laranja da lateral para começar.")

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
