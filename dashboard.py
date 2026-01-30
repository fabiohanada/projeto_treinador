import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v5.4 (TELA CADASTRO NOVA + LGPD)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v5.4", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES SEGURAS ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
    
    # Twilio (WhatsApp) - Carrega de forma opcional para não dar erro
    TWILIO_SID = st.secrets.get("TWILIO_ACCOUNT_SID")
    TWILIO_TOKEN = st.secrets.get("TWILIO_AUTH_TOKEN")
    TWILIO_FROM = st.secrets.get("TWILIO_PHONE_NUMBER")
    TWILIO_TO = st.secrets.get("MEU_CELULAR")
    
    twilio_ativo = all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, TWILIO_TO])
except Exception as e:
    st.error("Erro crítico nas Secrets. Verifique o painel do Streamlit.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES DE NOTIFICAÇÃO ---
def enviar_whatsapp(nome):
    if not twilio_ativo: return
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(
            from_=f"whatsapp:{TWILIO_FROM}",
            to=f"whatsapp:{TWILIO_TO}",
            body=f"Fábio, novo pagamento detectado de {nome.upper()}. Confira no seu banco!"
        )
    except: pass

def notificar_admin(nome, email):
    try:
        check = supabase.table("alertas_admin").select("*").eq("email_aluno", email).eq("lida", False).execute()
        if not check.data:
            supabase.table("alertas_admin").insert({"email_aluno": email, "mensagem": f"Novo pagamento detectado {nome.upper()}, por favor conferir na sua conta bancaria.", "lida": False}).execute()
            enviar_whatsapp(nome)
    except: pass

# --- LOGIN E SESSÃO ---
if "logado" not in st.session_state: st.session_state.logado = False
params = st.query_params
if "code" in params and "user_mail" in params:
    u = supabase.table("usuarios_app").select("*").eq("email", params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]
        # (Sincronização Strava aqui...)
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
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hashlib.sha256(s.encode()).hexdigest()).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.query_params["user_mail"] = e
                        st.rerun()
                    else: st.error("Dados incorretos.")
        
        with tab_cadastro:
            # --- NOVA TELA DE CADASTRO CONFORME IMAGEM ---
            with st.form("cad_form"):
                n_nome = st.text_input("Nome Completo")
                n_email = st.text_input("E-mail")
                n_senha = st.text_input("Crie uma Senha", type="password")
                st.divider()
                aceite = st.checkbox("Li e aceito os Termos de Uso e a Política de Privacidade (LGPD). Autorizo o uso dos meus dados de treino para análise de performance.")
                
                with st.expander("Ver Termos de Uso"):
                    st.write("Seus dados de treino (distância, tempo, FC) serão usados exclusivamente para a consultoria do Fábio Hanada.")
                
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    if not aceite:
                        st.error("Você precisa aceitar os termos para continuar.")
                    elif n_nome and n_email and n_senha:
                        try:
                            supabase.table("usuarios_app").insert({
                                "nome": n_nome, "email": n_email, 
                                "senha": hashlib.sha256(n_senha.encode()).hexdigest(),
                                "status_pagamento": False
                            }).execute()
                            st.success("Cadastro realizado! Aguarde a liberação do Fábio.")
                        except: st.error("Este e-mail já está cadastrado.")
                    else: st.warning("Preencha todos os campos.")
    st.stop()

# --- CONTINUAÇÃO DO APP (ADMIN / ALUNO) ---
user = st.session_state.user_info
if user.get('is_admin'):
    st.title("👨‍🏫 Central do Treinador")
    # (Lógica do Admin v5.3...)
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento'):
        notificar_admin(user['nome'], user['email'])
        st.error("⚠️ Acesso pendente de renovação.")
        st.stop()
    # (Lógica dos Gráficos v5.3...)
