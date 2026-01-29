import streamlit as st
import pandas as pd
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client

# ==========================================
# VERSÃO: v4.8 (FIX ERRO DE CARREGAMENTO)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v4.8", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
except Exception as e:
    st.error("Erro nas Secrets.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

# FUNÇÃO DE NOTIFICAÇÃO SIMPLIFICADA PARA EVITAR ERROS
def notificar_pagamento_admin(aluno_nome_completo, aluno_email):
    try:
        # Verifica se já existe um alerta não lido para este aluno hoje
        check = supabase.table("alertas_admin").select("*").eq("email_aluno", aluno_email).eq("lida", False).execute()
        
        if not check.data:
            msg = f"Novo pagamento detectado {aluno_nome_completo.upper()}, por favor conferir na sua conta bancaria."
            supabase.table("alertas_admin").insert({
                "email_aluno": aluno_email,
                "mensagem": msg,
                "lida": False
            }).execute()
    except:
        pass

# --- LOGICA DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if "user_mail" in st.query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", st.query_params["user_mail"]).execute()
    if u.data: st.session_state.logado, st.session_state.user_info = True, u.data[0]

if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        with st.form("login_form"):
            e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar Painel", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.query_params["user_mail"] = e
                    st.rerun()
                else: st.error("Dados incorretos.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.clear(); st.query_params.clear(); st.rerun()

# --- PAINEL ADMIN ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    
    st.subheader("🔔 Notificações de Pagamento")
    
    # Tentativa de carregar alertas com tratamento de erro
    try:
        res_alertas = supabase.table("alertas_admin").select("*").eq("lida", False).order("created_at", desc=True).execute()
        
        if res_alertas.data:
            for a in res_alertas.data:
                # MENSAGEM EM VERMELHO VIVO
                st.error(f"🚨 {a['mensagem']}")
            
            if st.button("Marcar todos como lidos", type="primary"):
                supabase.table("alertas_admin").update({"lida": True}).eq("lida", False).execute()
                st.rerun()
        else:
            st.info("Nenhum pagamento novo pendente de conferência.")
            
        if st.button("🔄 Atualizar Lista"):
            st.rerun()
            
    except Exception as e:
        st.warning("Aguardando inicialização da tabela de alertas...")
        if st.button("🔄 Tentar Novamente"):
            st.rerun()

    st.divider()

    # Gestão de Alunos
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1.5])
            with col1:
                st.markdown(f"#### {aluno['nome']}")
                st.markdown(f"**Status:** {'✅ Ativo' if aluno['status_pagamento'] else '❌ Bloqueado'}")
            with col2:
                dt_banco = aluno.get('data_vencimento')
                try: val_data = datetime.strptime(str(dt_banco), '%Y-%m-%d').date() if dt_banco and str(dt_banco) != "None" else date.today()
                except: val_data = date.today()
                nova_dt = st.date_input("Vencimento", value=val_data, key=f"dt_{aluno['id']}")
            with col3:
                if st.button("💾 Salvar Data", key=f"sv_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt)}).eq("id", aluno['id']).execute()
                    st.success("Salvo!")
                label_btn = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                if st.button(label_btn, key=f"ac_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

# --- PAINEL ALUNO ---
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento', False):
        # DISPARA O ALERTA
        notificar_pagamento_admin(user['nome'], user['email'])
        
        st.error("⚠️ Acesso pendente de renovação ou pagamento.")
        with st.expander("💳 Dados para Pagamento PIX", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.info(f"**Chave PIX (E-mail):** {chave_pix_visivel}")
            st.code(pix_copia_e_cola)
        st.stop()
    
    st.success(f"📅 Plano ativo até: **{formatar_data_br(user.get('data_vencimento'))}**")
