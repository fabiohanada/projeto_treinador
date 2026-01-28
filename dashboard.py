import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import hashlib, urllib.parse
from supabase import create_client
from twilio.rest import Client # Importante: adicione no requirements.txt

# ==========================================
# VERSÃO: v1 (ESTÁVEL + LÓGICA WHATSAPP TWILIO)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- FUNÇÃO DE ENVIO WHATSAPP ---
def enviar_whatsapp_twilio(nome_aluno, telefone, treino_nome, km, tempo):
    try:
        # Pega as chaves dos secrets
        sid = st.secrets["TWILIO_ACCOUNT_SID"]
        token = st.secrets["TWILIO_AUTH_TOKEN"]
        num_origem = st.secrets["TWILIO_NUMBER"] # Formato 'whatsapp:+14155238886'
        
        client = Client(sid, token)
        
        msg = f"Olá {nome_aluno}! 🏃‍♂️\n\nSeu último treino foi sincronizado:\n" \
              f"📌 *{treino_nome}*\n" \
              f"📏 Distância: {km}\n" \
              f"⏱️ Tempo: {tempo}\n\n" \
              f"Bons treinos! Fábio Assessoria."

        message = client.messages.create(
            from_=num_origem,
            body=msg,
            to=f'whatsapp:{telefone}' # O telefone deve estar no formato +5511999999999
        )
        return True
    except Exception as e:
        st.error(f"Erro no Twilio: {e}")
        return False

# --- FUNÇÕES AUXILIARES ---
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
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Cadastro"])
        with tab_login:
            with st.form("login_form"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.rerun()
        with tab_cadastro:
            with st.form("cadastro_form"):
                n_c = st.text_input("Nome")
                e_c = st.text_input("E-mail")
                tel_c = st.text_input("WhatsApp (Ex: +5511999999999)") # Novo campo
                s_c = st.text_input("Senha", type="password")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    supabase.table("usuarios_app").insert({"nome": n_c, "email": e_c, "telefone": tel_c, "senha": hash_senha(s_c), "status_pagamento": False, "data_vencimento": str(datetime.now().date())}).execute()
                    st.success("Cadastrado!")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info

# Dados simulados para o exemplo (vão vir do Strava/DB no futuro)
df = pd.DataFrame([
    {"Data": "24/01", "Treino": "Rodagem", "Km": "10 km", "Tempo": "60 min", "FC": 145},
    {"Data": "25/01", "Treino": "Intervalado", "Km": "8 km", "Tempo": "45 min", "FC": 160},
    {"Data": "27/01", "Treino": "Longo", "Km": "15 km", "Tempo": "95 min", "FC": 138},
])

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    st.divider()
    
    # --- BOTÃO COM A LÓGICA TWILIO ---
    if st.button("🧪 Sincronizar e Notificar", use_container_width=True):
        ultimo_treino = df.iloc[-1] # Pega o último treino da lista
        sucesso = enviar_whatsapp_twilio(
            user['nome'], 
            user.get('telefone', ''), # Pega o telefone do banco
            ultimo_treino['Treino'], 
            ultimo_treino['Km'], 
            ultimo_treino['Tempo']
        )
        if sucesso:
            st.toast("✅ WhatsApp enviado com sucesso!")
        else:
            st.error("Falha ao enviar. Verifique as chaves e o número.")

    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 🚀 RESTANTE DO LAYOUT (Dashboard Cliente v1...)
st.title(f"🚀 Painel de Treino")
# [Mantém o restante do código da planilha e gráficos aqui igual ao v1]
