import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse
from supabase import create_client
from twilio.rest import Client 

# --- CONFIGURAÇÕES E CONEXÕES ---
st.set_page_config(page_title="Fábio Assessoria v2", layout="wide", page_icon="🏃‍♂️")
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str: return "Não definida"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

# --- LÓGICA DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False

if "user_mail" in st.query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", st.query_params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]

if not st.session_state.logado:
    st.info("Por favor, faça login para continuar.")
    st.stop()

# --- INTERFACE ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.query_params.clear()
        st.rerun()

# 👨‍🏫 PAINEL ADMINISTRATIVO (Correção do Erro no Print)
if eh_admin:
    st.title("👨‍🏫 Gestão de Alunos")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    for aluno in alunos.data:
        with st.container(border=True):
            c_info, c_btns = st.columns([3, 1])
            with c_info:
                pago_status = "✅ PAGO" if aluno['status_pagamento'] else "❌ PENDENTE"
                st.markdown(f"**Aluno:** {aluno['nome']} | **Status:** {pago_status}")
                st.write(f"Vencimento: {formatar_data_br(aluno['data_vencimento'])}")
                
                # --- TRAVA DE SEGURANÇA PARA DATA VAZIA ---
                data_padrao = date.today()
                if aluno['data_vencimento']:
                    try: data_padrao = datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d').date()
                    except: pass
                
                nova_data = st.date_input("Alterar Vencimento", value=data_padrao, key=f"d_{aluno['id']}")
            
            with c_btns:
                if st.button("💾 Salvar Data", key=f"s_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                    st.rerun()
                label = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                if st.button(label, key=f"a_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

# 🚀 PAINEL DO ALUNO
else:
    st.title("🚀 Meus Treinos")
    pago = user.get('status_pagamento', False)
    # Lógica de exibição de treinos (Dashboard Cliente) segue aqui conforme a v2...
    st.info(f"📅 **Vencimento:** {formatar_data_br(user.get('data_vencimento'))}")
    if not pago:
        st.warning("Seu acesso está pendente de pagamento.")
        with st.expander("💳 Dados para Pagamento"):
            st.code(chave_pix_visivel)
