import streamlit as st
import pandas as pd
import os
import requests
import hashlib
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client

# 1. CONFIGURAÇÕES
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

def sincronizar_dados(strava_id, access_token, refresh_token):
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
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
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

# --- VARIÁVEIS DE SESSÃO ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR (Sair e Ferramentas) ---
with st.sidebar:
    st.title(f"{'👨‍🏫' if eh_admin else '🏃‍♂️'} {user['nome']}")
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state.logado = False
        st.rerun()
    st.divider()
    
    if eh_admin:
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
        st.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR NOVO ATLETA</div></a>', unsafe_allow_html=True)

# =================================================================
# 👨‍🏫 VISÃO ADMINISTRADOR (TREINADOR)
# =================================================================
if eh_admin:
    res_strava = supabase.table("usuarios").select("*").execute()
    
    if res_strava.data:
        atletas = {u['nome']: u for u in res_strava.data}
        sel = st.sidebar.selectbox("Selecionar Aluno", list(atletas.keys()))
        d = atletas[sel]
        
        dias_filtro = st.sidebar.radio("Período", [7, 30, 90, "Tudo"], index=1)

        if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
            if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token')):
                st.toast(f"Dados de {sel} atualizados!")
                st.rerun()

        # Dashboard Admin
        st.title(f"📊 Análise: {sel}")
        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
        
        if res_atv.data:
            df = pd.DataFrame(res_atv.data)
            df['dt'] = pd.to_datetime(df['data_treino'], utc=True)
            df = df.sort_values('dt')
            
            # Filtro de Tempo
            if dias_filtro != "Tudo":
                cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=int(dias_filtro))
                df = df[df['dt'] >= cutoff]

            # Cálculos de Carga
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            ratio = df['Aguda'].iloc[-1] / df['Cronica'].iloc[-1] if df['Cronica'].iloc[-1] > 0 else 0

            # 1. MÉTRICAS DE TOPO
            m1, m2, m3 = st.columns(3)
            m1.metric("Carga Aguda (7d)", f"{df['Aguda'].iloc[-1]:.1f}")
            m2.metric("Carga Crônica (28d)", f"{df['Cronica'].iloc[-1]:.1f}")
            status = "PERIGO" if ratio > 1.5 else "OTIMIZADO" if 0.8 <= ratio <= 1.3 else "ALERTA"
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta=status, delta_color="normal" if status == "OTIMIZADO" else "inverse")

            # 2. META SEMANAL
            st.divider()
            meta_km = 40.0
            km_semana = df[df['dt'] >= (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7))]['distancia'].sum()
            st.subheader(f"🏁 Meta Semanal: {km_semana:.1f}km / {meta_km}km")
            st.progress(min(km_semana/meta_km, 1.0))

            # 3. GRÁFICOS
            c1, c2 = st.columns(2)
            df['data_f'] = df['dt'].dt.strftime('%d/%m')
            with c1:
                st.subheader("🗓️ Volume por Dia")
                st.bar_chart(df.groupby('data_f')['distancia'].sum())
            with c2:
                st.subheader("📈 Carga Aguda vs Crônica")
                st.line_chart(df.set_index('data_f')[['Aguda', 'Cronica']])

            # 4. TABELA DETALHADA
            st.subheader("📋 Últimos Treinos")
            df['Pace'] = df['trimp_score'] / df['distancia']
            tabela = df[['data_f', 'tipo_esporte', 'distancia', 'trimp_score', 'Pace']].tail(5).copy()
            tabela.columns = ['Data', 'Esporte', 'Km', 'Minutos', 'Pace (min/km)']
            st.dataframe(tabela, use_container_width=True)
        else:
            st.info("Sem dados para este período.")
    else:
        st.info("Conecte um atleta no botão laranja.")

# =================================================================
# 🏃‍♂️ VISÃO ATLETA (CLIENTE)
# =================================================================
else:
    st.title(f"🚀
