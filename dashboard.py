import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v5.7 (RODAPÉ BLINDADO COM HTML)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v5.7", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES SEGURAS ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
    
    TW_SID = st.secrets.get("TWILIO_ACCOUNT_SID")
    TW_TOKEN = st.secrets.get("TWILIO_AUTH_TOKEN")
    TW_FROM = st.secrets.get("TWILIO_PHONE_NUMBER")
    TW_TO = st.secrets.get("MEU_CELULAR")
    twilio_pronto = all([TW_SID, TW_TOKEN, TW_FROM, TW_TO])
except Exception as e:
    st.error("Erro crítico nas Secrets. Verifique o painel do Streamlit.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

def sincronizar_strava(auth_code, aluno_id):
    token_url = "https://www.strava.com/oauth/token"
    payload = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'code': auth_code, 'grant_type': 'authorization_code'}
    try:
        r = requests.post(token_url, data=payload).json()
        if 'access_token' in r:
            token = r['access_token']
            header = {'Authorization': f"Bearer {token}"}
            atividades = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=header).json()
            for act in atividades:
                if act['type'] == 'Run':
                    dados = {"aluno_id": aluno_id, "data": act['start_date_local'][:10], "nome_treino": act['name'], "distancia": round(act['distance'] / 1000, 2), "tempo_min": round(act['moving_time'] / 60, 2), "fc_media": act.get('average_heartrate', 130), "strava_id": str(act['id'])}
                    supabase.table("treinos_alunos").upsert(dados, on_conflict="strava_id").execute()
            return True
    except: return False
    return False

# --- SESSÃO E LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
params = st.query_params
if "code" in params and "user_mail" in params:
    u = supabase.table("usuarios_app").select("*").eq("email", params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]
        sincronizar_strava(params["code"], u.data[0]['id'])
        st.query_params.clear()
        st.query_params["user_mail"] = u.data[0]['email']

if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Aluno"])
        with tab_login:
            with st.form("login_form"):
                e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Painel", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.query_params["user_mail"] = e
                        st.rerun()
                    else: st.error("E-mail ou senha incorretos.")
        with tab_cadastro:
            with st.form("cad_form"):
                n_nome = st.text_input("Nome Completo")
                n_email = st.text_input("E-mail")
                n_senha = st.text_input("Crie uma Senha", type="password")
                aceite = st.checkbox("Li e aceito os Termos de Uso e a Política de Privacidade (LGPD).")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    if not aceite: st.error("Você precisa aceitar os termos.")
                    elif n_nome and n_email and n_senha:
                        try:
                            supabase.table("usuarios_app").insert({"nome": n_nome, "email": n_email, "senha": hash_senha(n_senha), "status_pagamento": False}).execute()
                            st.success("Cadastro realizado!")
                        except: st.error("E-mail já cadastrado.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if not eh_admin:
        redirect_com_email = f"{REDIRECT_URI}?user_mail={user['email']}"
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={urllib.parse.quote(redirect_com_email)}&scope=activity:read_all&approval_prompt=auto"
        st.markdown(f'''<a href="{link_strava}" target="_self" style="text-decoration: none;"><div style="background-color: #FC4C02; color: white; padding: 12px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 20px;">Connect with STRAVA</div></a>''', unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.clear(); st.query_params.clear(); st.rerun()

# --- CONTEÚDO ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    # Lógica de gestão de alunos...
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento'):
        st.error("⚠️ Acesso pendente de renovação.")
        st.stop()
    
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df, x='data', y='distancia', title="Distância por Treino", color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with c2: st.plotly_chart(px.line(df, x='data', y='fc_media', title="FC Média"), use_container_width=True)
    else: st.warning("Conecte ao Strava para ver seus dados.")

# --- RODAPÉ DEFINITIVO (HTML INJETADO) ---
st.write("") # Espaçador
st.markdown("""
    <hr>
    <div style="display: flex; justify-content: flex-end; align-items: center; padding: 10px;">
        <img src="https://strava.github.io/api/images/api_logo_pwrdBy_strava_horiz_light.png" width="160">
    </div>
    """, unsafe_allow_html=True)
