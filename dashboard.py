import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from twilio.rest import Client

# 1. CONFIGURAÇÕES
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# CSS Estável (Versão 27/01)
st.markdown("""
    <style>
    span.no-style { text-decoration: none !important; color: inherit !important; border-bottom: none !important; }
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stVerticalBlock"] { max-width: 450px; margin: 0 auto; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
TWILIO_SID = st.secrets.get("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = st.secrets.get("TWILIO_AUTH_TOKEN")

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_aviso_whatsapp(nome, telefone):
    if not TWILIO_SID or not TWILIO_TOKEN:
        st.error("Credenciais Twilio não configuradas.")
        return
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        msg = f"Olá {nome}! Seu acesso à Fábio Assessoria foi liberado. Bons treinos! 🏃‍♂️"
        client.messages.create(from_='whatsapp:+14155238886', body=msg, to=f'whatsapp:{telefone}')
        st.success(f"WhatsApp enviado para {nome}!")
    except Exception as e:
        st.error(f"Erro ao enviar: {e}")

# =================================================================
# 🔑 LOGIN E CADASTRO (Layout 27/01)
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
                # LGPD Obrigatória como solicitado
                st.info("🛡️ LGPD: Seus dados de treino são usados apenas para sua assessoria.")
                concordo = st.checkbox("Aceito os termos")
                if st.form_submit_button("Finalizar Cadastro", use_container_width=True):
                    if concordo and n and em and se:
                        supabase.table("usuarios_app").insert({"nome": n, "email": em, "senha": hash_senha(se), "status_pagamento": False, "data_vencimento": str(datetime.now().date())}).execute()
                        st.success("Cadastrado! Mude para a aba 'Entrar'.")
                    else: st.warning("Aceite os termos e preencha tudo.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    st.markdown(f"📧 <span class='no-style'>{user['email']}</span>", unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

if user.get('is_admin'):
    st.title("👨‍🏫 Gestão de Alunos")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for a in alunos.data:
        with st.container(border=True):
            col_inf, col_btn = st.columns([3, 1])
            with col_inf:
                st.markdown(f"**Aluno:** {a['nome']} | **E-mail:** <span class='no-style'>{a['email']}</span>", unsafe_allow_html=True)
                st.write(f"Vencimento: {datetime.strptime(a['data_vencimento'], '%Y-%m-%d').strftime('%d/%m/%Y')}")
            with col_btn:
                # Botão Twilio integrado
                if st.button(f"📲 Avisar via Whats", key=f"w_{a['id']}"):
                    # Aqui você precisaria ter o campo 'telefone' na tabela. 
                    # Se não tiver, podemos adicionar amanhã.
                    enviar_aviso_whatsapp(a['nome'], "5511999999999") # Exemplo
                
                label = "🔒 Bloquear" if a['status_pagamento'] else "🔓 Liberar"
                if st.button(label, key=f"b_{a['id']}"):
                    supabase.table("usuarios_app").update({"status_pagamento": not a['status_pagamento']}).eq("id", a['id']).execute()
                    st.rerun()
else:
    # Dashboard Cliente com Gráficos
    st.title("🚀 Meus Treinos")
    venc = datetime.strptime(user['data_vencimento'], '%Y-%m-%d').date()
    if not (user['status_pagamento'] and datetime.now().date() <= venc):
        st.error("Assinatura inativa. Chave PIX: seu-email@pix.com")
        st.stop()
    
    st.info("Gráficos de desempenho e integração Strava (Aguardando liberação de cota)")
    # Espaço para os gráficos do Plotly que configuramos ontem
