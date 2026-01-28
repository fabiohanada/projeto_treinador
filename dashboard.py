import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from twilio.rest import Client

# 1. CONFIGURAÇÕES (Estilo 27/01)
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# CSS para padronização e visual limpo
st.markdown("""
    <style>
    span.no-style { text-decoration: none !important; color: inherit !important; border-bottom: none !important; }
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stVerticalBlock"] { max-width: 450px; margin: 0 auto; }
    .strava-btn { display: block; margin-left: auto; margin-right: auto; width: 200px; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
REDIRECT_URI = "https://seu-treino-app.streamlit.app"

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

# =================================================================
# 🔑 LOGIN E CADASTRO
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("<br><h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        t1, t2 = st.tabs(["🔑 Entrar", "📝 Cadastro"])
        with t1:
            with st.form("l"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.rerun()
        with t2:
            with st.form("c"):
                n, em, se = st.text_input("Nome"), st.text_input("E-mail"), st.text_input("Senha", type="password")
                st.info("🛡️ LGPD: Seus dados são usados apenas para análise de performance.")
                concordo = st.checkbox("Aceito os termos")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    if concordo and n and em and se:
                        supabase.table("usuarios_app").insert({"nome": n, "email": em, "senha": hash_senha(se), "status_pagamento": False, "data_vencimento": str(datetime.now().date())}).execute()
                        st.success("Criado! Use a aba Entrar.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"👤 **{user['nome']}**")
    st.markdown(f"📧 <span class='no-style'>{user['email']}</span>", unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

if eh_admin:
    st.title("👨‍🏫 Gestão de Alunos")
    # Painel de gestão idêntico ao de 27/01 (com botões de salvar e liberar)
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for a in alunos.data:
        with st.container(border=True):
            ci, cb = st.columns([3, 1])
            with ci:
                st.write(f"**{a['nome']}** | {formatar_data_br(a['data_vencimento'])}")
            with cb:
                st.button("🔓 Liberar" if not a['status_pagamento'] else "🔒 Bloquear", key=f"b_{a['id']}")

else:
    st.title("🚀 Meus Treinos")
    v_str = user.get('data_vencimento', "2000-01-01")
    venc = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user['status_pagamento'] and datetime.now().date() <= venc

    if not pago:
        st.error("Assinatura Inativa. Fale com o Fábio.")
        st.stop()

    # BOTÃO OFICIAL STRAVA (Exigência para Produção)
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read,activity:read&state={user['email']}"
    
    st.markdown(f"""
        <a href="{auth_url}">
            <img src="https://strava.github.io/api/images/connect_with_strava.png" class="strava-btn">
        </a>
    """, unsafe_allow_html=True)
    
    # Gráfico Discreto
    st.subheader("📊 Desempenho Semanal")
    # Espaço para o gráfico do Plotly...
