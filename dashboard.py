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
REDIRECT_URI = "https://seu-treino-app.streamlit.app" # Verifique se este é o link atual

# --- FUNÇÕES ---
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
# 🔑 SISTEMA DE LOGIN (SÓ APARECE SE NÃO ESTIVER LOGADO)
# =================================================================
if "logado" not in st.session_state:
    st.session_state.logado = False

# Processamento do Strava (Callback)
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
            "access_token": res_t["access_token"], "refresh_token": res_t["refresh_token"],
            "nome": res_t["athlete"]["firstname"]
        }).execute()
        st.success("✅ Strava vinculado!")
        st.query_params.clear()
        st.rerun()

if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    tab_l, tab_c = st.tabs(["Entrar", "Novo Cadastro"])
    
    with tab_l:
        with st.form("login_form"):
            u_email = st.text_input("E-mail")
            u_senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", u_email).eq("senha", hash_senha(u_senha)).execute()
                if u.data:
                    st.session_state.logado = True
                    st.session_state.user_info = u.data[0]
                    st.rerun()
                else: st.error("Dados incorretos.")
    with tab_c:
        st.info("Cadastre-se para começar seus treinos.")
        # ... (seu código de cadastro aqui)
    st.stop() # Interrompe aqui para quem não está logado

# =================================================================
# 🏠 ÁREA LOGADA (DASHBOARD) - SÓ CHEGA AQUI SE LOGAR
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# Barra Lateral (Comum a todos)
with st.sidebar:
    st.title("🏃‍♂️ Menu")
    st.write(f"Usuário: **{user['nome']}**")
    if eh_admin: st.subheader("⭐ Perfil Treinador")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# -----------------------------------------------------------------
# 👨‍🏫 VISÃO DO ADMIN (FÁBIO)
# -----------------------------------------------------------------
if eh_admin:
    st.title("👨‍🏫 Painel de Controle - Treinador")
    
    tabs = st.tabs(["👥 Alunos", "💰 Financeiro", "📊 Performance Geral"])
    
    with tabs[0]:
        st.subheader("Lista de Alunos Cadastrados")
        alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
        if alunos.data:
            df_alunos = pd.DataFrame(alunos.data)
            st.dataframe(df_alunos[['nome', 'email', 'telefone', 'data_vencimento']], use_container_width=True)
        else:
            st.write("Nenhum aluno cadastrado.")

    with tabs[1]:
        st.subheader("Controle de Pagamentos")
        # Aqui você pode listar quem está com 'status_pagamento' = False
        st.info("Funcionalidade em desenvolvimento: Em breve você poderá ativar/desativar alunos aqui.")

# -----------------------------------------------------------------
# 🚀 VISÃO DO ALUNO
# -----------------------------------------------------------------
else:
    st.title(f"🚀 Dashboard do Atleta: {user['nome']}")
    
    # Verifica se o aluno pagou
    v_str = user.get('data_vencimento', "2000-01-01")
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and datetime.now().date() <= venc_date

    if not pago:
        st.error(f"🚨 Sua assinatura expirou em {venc_date.strftime('%d/%m/%Y')}. Entre em contato com o Fábio.")
        st.stop()

    # Se estiver pago, mostra o Strava
    res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
    
    if res_s.data:
        atleta = res_s.data[0]
        if st.button("🔄 Sincronizar Meus Treinos", type="primary"):
            sincronizar_dados(atleta['strava_id'], atleta['access_token'])
            st.rerun()
        
        # Histórico
        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).execute()
        if res_atv.data:
            st.subheader("Meu Histórico")
            st.dataframe(pd.DataFrame(res_atv.data), use_container_width=True)
    else:
        st.warning("Vincule seu Strava para ver seus treinos.")
        auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
                    f"&response_type=code&approval_prompt=auto&scope=read,activity:read&state={user['email']}")
        st.link_button("🔗 Conectar Strava", auth_url)
