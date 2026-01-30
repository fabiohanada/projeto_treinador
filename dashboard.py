import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests, base64
from supabase import create_client

# ==========================================
# VERSÃO: v6.4 (RODAPÉ BLINDADO + CSS INJETADO)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v6.4", layout="wide", page_icon="🏃‍♂️")

# --- FUNÇÃO PARA BLINDAR A IMAGEM (BASE64) ---
def get_base64_from_url(url):
    try:
        response = requests.get(url)
        return base64.b64encode(response.content).decode()
    except:
        return ""

# Logo oficial do Strava em Base64 para evitar quebras de carregamento
LOGO_STRAVA_URL = "https://strava.github.io/api/images/api_logo_pwrdBy_strava_horiz_light.png"
logo_base64 = get_base64_from_url(LOGO_STRAVA_URL)

# --- INJEÇÃO DE CSS PARA ESTABILIDADE ---
st.markdown(f"""
    <style>
    /* Fixa o rodapé e evita o balanço do layout */
    .st-emotion-cache-1y4p8pa {{ padding-bottom: 80px; }} /* Espaço para o rodapé não cobrir conteúdo */
    
    .main-footer {{
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: white;
        text-align: center;
        padding: 15px 0;
        z-index: 1000;
        border-top: 1px solid #eee;
        box-shadow: 0 -2px 5px rgba(0,0,0,0.05);
    }}
    
    /* Botão Strava na Sidebar */
    .strava-btn {{
        background-color: #FC4C02;
        color: white !important;
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        font-weight: bold;
        text-decoration: none;
        display: block;
        margin-bottom: 20px;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÕES ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
except Exception as e:
    st.error("Erro nas Secrets. Verifique as configurações do Streamlit Cloud.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

# --- SISTEMA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False

# Captura retorno do Strava via query_params
params = st.query_params
if "code" in params and "user_mail" in params:
    u = supabase.table("usuarios_app").select("*").eq("email", params["user_mail"]).execute()
    if u.data:
        st.session_state.logado = True
        st.session_state.user_info = u.data[0]

# --- TELA DE ACESSO ---
if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Aluno"])
        with tab_login:
            with st.form("login_form"):
                e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Painel", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado = True
                        st.session_state.user_info = u.data[0]
                        st.rerun()
                    else: st.error("E-mail ou senha incorretos.")
        
        with tab_cadastro:
            with st.form("cad_form"):
                n_nome = st.text_input("Nome Completo")
                n_email = st.text_input("E-mail")
                n_senha = st.text_input("Crie uma Senha", type="password")
                aceite = st.checkbox("Aceito os Termos de Uso e LGPD.")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    if not aceite: st.error("Aceite os termos para continuar.")
                    elif n_nome and n_email and n_senha:
                        try:
                            supabase.table("usuarios_app").insert({"nome": n_nome, "email": n_email, "senha": hash_senha(n_senha), "status_pagamento": False}).execute()
                            st.success("Cadastrado! Peça liberação ao Fábio.")
                        except: st.error("E-mail já cadastrado.")
    st.stop()

# --- ÁREA LOGADA ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if not eh_admin:
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={urllib.parse.quote(REDIRECT_URI + '?user_mail=' + user['email'])}&scope=activity:read_all&approval_prompt=auto"
        st.markdown(f'<a href="{link_strava}" target="_self" class="strava-btn">Connect with STRAVA</a>', unsafe_allow_html=True)
    
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# --- CONTEÚDO PRINCIPAL ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    # Lógica de Admin simplificada para o exemplo
    st.info("Gerencie seus alunos abaixo.")
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento'):
        st.error("⚠️ Acesso pendente de renovação.")
        st.code(pix_copia_e_cola, language="text")
        st.stop()

    # Exibição de Dados (Supabase)
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df, x='data', y='distancia', title="Volume (km)", color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with c2: st.plotly_chart(px.line(df, x='data', y='fc_media', title="FC Média"), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Aguardando sincronização de treinos do Strava...")

# --- RODAPÉ BLINDADO (v6.4) ---
st.markdown(f"""
    <div class="main-footer">
        <img src="data:image/png;base64,{logo_base64}" width="160">
    </div>
    """, unsafe_allow_html=True)
