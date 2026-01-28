import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# CSS para limpeza visual e alinhamento
st.markdown("""
    <style>
    span.no-style { text-decoration: none !important; color: inherit !important; }
    .stButton>button { border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

# =================================================================
# 🔑 GESTÃO DE SESSÃO E LOGIN
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            u_email = st.text_input("E-mail")
            u_senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", u_email).eq("senha", hash_senha(u_senha)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.rerun()
                else: st.error("Login inválido.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA (Aparece para Admin e Cliente)
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- BARRA LATERAL FIXA ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    st.write(f"📧 {user['email']}")
    if eh_admin:
        st.info("Painel: Treinador")
    st.divider()
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state.logado = False
        st.session_state.user_info = None
        st.rerun()

# 👨‍🏫 TELA DO ADMIN (FÁBIO)
if eh_admin:
    st.title("👨‍🏫 Gestão de Alunos")
    res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    if res_alunos.data:
        for aluno in res_alunos.data:
            with st.container(border=True):
                col_info, col_botoes = st.columns([3, 1])
                with col_info:
                    st.markdown(f"**Aluno:** {aluno['nome']}")
                    st.markdown(f"**E-mail:** <span class='no-style'>{aluno['email']}</span>", unsafe_allow_html=True)
                    
                    status_cor = "#28a745" if aluno['status_pagamento'] else "#dc3545"
                    status_txt = "ATIVO" if aluno['status_pagamento'] else "BLOQUEADO"
                    st.markdown(f"**Status:** <span style='color:{status_cor}; font-weight:bold;'>{status_txt}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Vencimento Atual:** {formatar_data_br(aluno['data_vencimento'])}")
                    
                    # Linha de Alteração Alinhada
                    c_label, c_input = st.columns([0.8, 1])
                    c_label.markdown("<br>**Alterar Vencimento:**", unsafe_allow_html=True)
                    nova_data = c_input.date_input(
                        "Nova Data", 
                        value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'),
                        key=f"d_{aluno['id']}",
                        format="DD/MM/YYYY",
                        label_visibility="collapsed"
                    )
                
                with col_botoes:
                    st.write("") 
                    if st.button("💾 Salvar Data", key=f"s_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                        st.success("Salvo!")
                        st.rerun()
                    
                    txt_acc = "🔓 Liberar" if not aluno['status_pagamento'] else "🔒 Bloquear"
                    if st.button(txt_acc, key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()

# 🚀 TELA DO CLIENTE
else:
    st.title(f"🚀 Dashboard do Atleta")
    v_str = user.get('data_vencimento', "2000-01-01")
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and datetime.now().date() <= venc_date

    # Financeiro do Cliente
    with st.expander("💳 Minha Assinatura", expanded=not pago):
        st.write(f"**Vencimento:** {formatar_data_br(v_str)}")
        if not pago: 
            st.error("Acesso suspenso. Fale com o Fábio para renovação.")
            st.stop()

    # Se estiver pago, mostra os treinos
    res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
    if res_s.data:
        atleta = res_s.data[0]
        if st.button("🔄 Sincronizar Strava", type="primary"):
            # Função de sincronização aqui...
            st.rerun()
        
        # Tabela de resultados aqui...
        st.info("Treinos sincronizados aparecerão aqui.")
    else:
        st.warning("Vincule seu Strava.")
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read,activity:read&state={user['email']}"
        st.link_button("🔗 Conectar Strava", auth_url)
