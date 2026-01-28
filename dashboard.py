import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import hashlib, urllib.parse
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v1 (LAYOUT TRAVADO + LOGIN PERSISTENTE)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- FUNÇÃO DE LIMPEZA E DISPARO TWILIO ---
def enviar_whatsapp_real(nome_aluno, telefone, treino_nome, km, tempo):
    try:
        sid = st.secrets["TWILIO_ACCOUNT_SID"]
        token = st.secrets["TWILIO_AUTH_TOKEN"]
        num_origem = f"whatsapp:{st.secrets['TWILIO_PHONE_NUMBER']}"
        client = Client(sid, token)
        
        # Limpeza do número para o padrão internacional
        tel_limpo = "".join(filter(str.isdigit, str(telefone)))
        if not tel_limpo.startswith("55"): tel_limpo = "55" + tel_limpo
        num_destino = f"whatsapp:+{tel_limpo}"
        
        msg = f"🏃‍♂️ *Fábio Assessoria*\n\nOlá *{nome_aluno}*! Seu treino: *{treino_nome}*, {km}km em {tempo}min. 🚀"
        client.messages.create(body=msg, from_=num_origem, to=num_destino)
        return True
    except Exception as e:
        st.error(f"Erro no disparo: {e}")
        return False

# --- LÓGICA DE PERSISTÊNCIA (ANTI-F5) ---
if "logado" not in st.session_state:
    st.session_state.logado = False

# Verifica se existe um e-mail salvo na URL (query params)
query_params = st.query_params
if "user_mail" in query_params and not st.session_state.logado:
    email_salvo = query_params["user_mail"]
    u = supabase.table("usuarios_app").select("*").eq("email", email_salvo).execute()
    if u.data:
        st.session_state.logado = True
        st.session_state.user_info = u.data[0]

def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

# =================================================================
# 🔑 LOGIN E CADASTRO
# =================================================================
if not st.session_state.logado:
    st.markdown("<br><h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Cadastro"])
        with tab_login:
            with st.form("login_form"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado = True
                        st.session_state.user_info = u.data[0]
                        # SALVA NA URL PARA O F5
                        st.query_params["user_mail"] = e
                        st.rerun()
                    else:
                        st.error("Usuário ou senha inválidos")
        # [Cadastro mantido igual ao v1 anterior]
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA (v1)
# =================================================================
user = st.session_state.user_info

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    st.divider()
    
    # Botão Sincronizar (v1)
    if st.button("🧪 Sincronizar e Notificar", use_container_width=True):
        # (Lógica de dados simulados da Maria)
        sucesso = enviar_whatsapp_real(user['nome'], user.get('telefone',''), "Treino v1", "10", "60")
        if sucesso: st.toast("✅ WhatsApp enviado!")

    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.query_params.clear() # Limpa a URL ao sair
        st.rerun()

# --- RESTANTE DO LAYOUT v1 (IGUAL AO ANTERIOR) ---
st.title("🚀 Painel de Treino")
# [Planilha, TRIMP e Gráfico de FC aqui...]
