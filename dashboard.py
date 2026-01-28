import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# CSS para remover sublinhado, ajustar cores e espaçamentos
st.markdown("""
    <style>
    /* Remove sublinhado de links e e-mails */
    span.no-style { text-decoration: none !important; color: inherit !important; }
    a { text-decoration: none !important; }
    
    /* Ajuste de espaçamento das linhas no card */
    .aluno-row { margin-bottom: 8px; line-height: 1.6; }
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
# 🔑 LOGIN
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
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 TELA DO ADMIN (FÁBIO)
if eh_admin:
    st.title("👨‍🏫 Gestão de Alunos")
    res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    if res_alunos.data:
        for aluno in res_alunos.data:
            with st.container(border=True):
                # Dividimos o card em Informações (esquerda) e Botões (direita)
                col_info, col_botoes = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"**Aluno:** {aluno['nome']}")
                    
                    # E-mail usando span para forçar a remoção do sublinhado
                    st.markdown(f"**E-mail:** <span class='no-style'>{aluno['email']}</span>", unsafe_allow_html=True)
                    
                    status_cor = "green" if aluno['status_pagamento'] else "red"
                    status_texto = "Ativo" if aluno['status_pagamento'] else "Bloqueado"
                    st.markdown(f"**Status:** <span style='color:{status_cor}; font-weight:bold;'>{status_texto}</span>", unsafe_allow_html=True)
                    
                    st.write(f"**Vencimento Atual:** {formatar_data_br(aluno['data_vencimento'])}")
                    
                    # Linha: Alterar Vencimento + Seletor de Data
                    c_label, c_input = st.columns([0.8, 1])
                    c_label.markdown("**Alterar Vencimento:**")
                    nova_data = c_input.date_input(
                        "Selecione a data", 
                        value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'),
                        key=f"date_{aluno['id']}",
                        format="DD/MM/YYYY",
                        label_visibility="collapsed" # Esconde o rótulo do seletor para alinhar
                    )
                
                with col_botoes:
                    st.write("") # Espaçador para alinhar botões
                    if st.button("💾 Salvar Data", key=f"save_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                        st.success("Atualizado!")
                        st.rerun()
                    
                    tipo_btn = "primary" if not aluno['status_pagamento'] else "secondary"
                    txt_btn = "🔓 Liberar Acesso" if not aluno['status_pagamento'] else "🔒 Bloquear Acesso"
                    if st.button(txt_btn, key=f"acc_{aluno['id']}", use_container_width=True, type=tipo_btn):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()
    else:
        st.info("Nenhum aluno encontrado.")

# 🚀 TELA DO CLIENTE (Simplificada)
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    # ... (Restante do código do cliente mantido conforme anterior)
