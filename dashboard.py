import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES CORE ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 10})
    if res.status_code == 200:
        for atv in res.json():
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), "data_treino": atv['start_date_local'],
                "distancia": atv['distance'] / 1000, "tipo_esporte": atv['type']
            }).execute()
        return True
    return False

# =================================================================
# 🔑 LOGIN E CALLBACK
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

# Processamento Strava
params = st.query_params
if "code" in params and "state" in params:
    cod, email_aluno = params["code"], params["state"]
    res_t = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": cod, "grant_type": "authorization_code"
    }).json()
    if "access_token" in res_t:
        supabase.table("usuarios").upsert({
            "email": email_aluno, "strava_id": res_t["athlete"]["id"],
            "access_token": res_t["access_token"], "refresh_token": res_t["refresh_token"]
        }).execute()
        st.success("✅ Strava vinculado!")
        st.query_params.clear()
        st.rerun()

if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login"):
            u_email = st.text_input("E-mail")
            u_senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", u_email).eq("senha", hash_senha(u_senha)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.rerun()
                else: st.error("Erro de login.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.title("🏃‍♂️ Menu")
    st.write(f"Logado: **{user['nome']}**")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 TELA DO FÁBIO (ADMIN)
if eh_admin:
    st.title("👨‍🏫 Gestão de Alunos e Financeiro")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    if alunos.data:
        for aluno in alunos.data:
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([2, 1.5, 1, 1])
                col1.subheader(aluno['nome'])
                col1.write(f"📧 {aluno['email']}")
                
                status = "✅ ATIVO" if aluno['status_pagamento'] else "❌ BLOQUEADO"
                col2.write(f"**Status:** {status}")
                col2.write(f"**Vencimento:** {aluno['data_vencimento']}")
                
                label_btn = "Bloquear" if aluno['status_pagamento'] else "Ativar"
                if col3.button(label_btn, key=f"btn_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()
                
                nova_data = col4.date_input("Novo Vencimento", key=f"date_{aluno['id']}")
                if col4.button("Salvar Data", key=f"save_{aluno['id']}"):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                    st.success("Data atualizada!")
                    st.rerun()
    else:
        st.info("Nenhum aluno cadastrado.")

# 🚀 TELA DO ALUNO
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    
    # --- SEÇÃO FINANCEIRA DO CLIENTE ---
    v_str = user.get('data_vencimento', "2000-01-01")
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
    dias_restantes = (venc_date - datetime.now().date()).days
    pago = user.get('status_pagamento', False) and dias_restantes >= 0

    with st.expander("💳 Minha Assinatura / Financeiro", expanded=not pago):
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", "✅ Ativo" if pago else "❌ Inativo")
        c2.metric("Vencimento", venc_date.strftime('%d/%m/%Y'))
        c3.metric("Dias Restantes", f"{max(0, dias_restantes)} dias")
        
        if not pago:
            st.warning("⚠️ Seu acesso está suspenso. Realize o pagamento para liberar os treinos.")
            st.write("**Chave Pix para renovação:** `sua-chave-pix-aqui@pix.com`")

    # --- BLOQUEIO DE CONTEÚDO ---
    if not pago:
        st.stop()

    # --- CONTEÚDO STRAVA ---
    res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
    if res_s.data:
        atleta = res_s.data[0]
        if st.button("🔄 Atualizar Meus Treinos", type="primary"):
            sincronizar_dados(atleta['strava_id'], atleta['access_token'])
            st.rerun()
        
        atividades = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).execute()
        if atividades.data:
            st.subheader("Meus Treinos Recentes")
            st.dataframe(pd.DataFrame(atividades.data), use_container_width=True)
    else:
        st.warning("Vincule seu Strava para começar.")
        auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
                    f"&response_type=code&approval_prompt=auto&scope=read,activity:read&state={user['email']}")
        st.link_button("🔗 Conectar Strava", auth_url)
