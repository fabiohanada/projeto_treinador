import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib

# 1. CONFIGURAÇÕES E CONSTANTES
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

# --- FUNÇÕES DE COMUNICAÇÃO ---

def formatar_whatsapp_destino(telefone):
    apenas_numeros = ''.join(filter(str.isdigit, str(telefone)))
    return f"whatsapp:+{apenas_numeros}"

def enviar_whatsapp(mensagem, telefone_cru):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        phone_from = get_secret("TWILIO_PHONE_NUMBER")
        if not str(phone_from).startswith("whatsapp:"):
            phone_from = f"whatsapp:{phone_from}"
            
        client = Client(sid, token)
        client.messages.create(body=mensagem, from_=phone_from, to=formatar_whatsapp_destino(telefone_cru))
        return True
    except: return False

# --- SINCRONIZAÇÃO E CÁLCULOS ---

def sincronizar_dados(strava_id, access_token, refresh_token, nome_atleta, tel_usuario):
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
            
            # Notificação padrão de sucesso
            if atividades:
                enviar_whatsapp(f"✅ Treinos de {nome_atleta} atualizados com sucesso!", tel_usuario)
            return True
        return False
    except: return False

# --- INTERFACE DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    st.title("🏃‍♂️ Portal do Treinador")
    e = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        senha_h = hashlib.sha256(str.encode(s)).hexdigest()
        u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", senha_h).execute()
        if u.data:
            st.session_state.logado, st.session_state.user_info = True, u.data[0]
            st.rerun()
    st.stop()

# --- DASHBOARD ---
st.sidebar.title(f"Treinador: {st.session_state.user_info['nome']}")

# Atletas
res_atleta = supabase.table("usuarios").select("*").execute()
if res_atleta.data:
    lista_atletas = {at['nome']: at for at in res_atleta.data}
    atleta_nome = st.sidebar.selectbox("Escolha o Atleta", list(lista_atletas.keys()))
    d_atleta = lista_atletas[atleta_nome]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        if sincronizar_dados(d_atleta['strava_id'], d_atleta['access_token'], d_atleta.get('refresh_token'), atleta_nome, st.session_state.user_info['telefone']):
            st.rerun()

    # --- PROCESSAMENTO DE DADOS ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d_atleta['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['dt'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('dt')
        df['data_f'] = df['dt'].dt.strftime('%d/%m/%Y')

        # CÁLCULO DE CARGAS
        df['Aguda'] = df['trimp_score'].rolling(window=7, min_periods=1).mean()
        df['Cronica'] = df['trimp_score'].rolling(window=28, min_periods=1).mean()
        
        # Últimos valores para o alerta
        ultima_aguda = df['Aguda'].iloc[-1]
        ultima_cronica = df['Cronica'].iloc[-1]
        ratio = ultima_aguda / ultima_cronica if ultima_cronica > 0 else 0

        # --- EXIBIÇÃO DE ALERTAS ---
        st.markdown(f"### Análise de Performance: {atleta_nome}")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Carga Aguda (7d)", f"{ultima_aguda:.1f}")
        m2.metric("Carga Crónica (28d)", f"{ultima_cronica:.1f}")
        
        # Alerta visual de Risco
        if ratio > 1.5:
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta="ALTO RISCO", delta_color="inverse")
            st.error(f"⚠️ **PERIGO:** O atleta {atleta_nome} está com um rácio de {ratio:.2f}. Risco elevado de lesão por aumento súbito de carga!")
            if st.button("⚠️ Enviar Alerta de Risco via WhatsApp"):
                msg_alerta = f"🚨 *ALERTA DE SEGURANÇA*\n\nAtleta: {atleta_nome}\nO rácio de carga atingiu {ratio:.2f}.\n\nRecomendação: Reduzir a intensidade nos próximos 3 dias para evitar lesões."
                enviar_whatsapp(msg_alerta, st.session_state.user_info['telefone'])
        elif ratio < 0.8:
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta="SUB-TREINO")
            st.warning("ℹ️ O atleta está em fase de destreino ou recuperação excessiva.")
        else:
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta="ZONA SEGURA")
            st.success("✅ Carga de treino equilibrada (Sweet Spot).")

        # --- GRÁFICOS LADO A LADO ---
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🗓️ Atividades por Dia")
            st.bar_chart(df.groupby('data_f').size())
        with c2:
            st.subheader("📈 Progressão de Cargas")
            st.line_chart(df.set_index('data_f')[['Aguda', 'Cronica']])

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
