import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide", page_icon="🏃‍♂️")

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
# AJUSTE SEMPRE ESTA URL PARA O SEU LINK ATUAL:
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 30})
    if res.status_code == 200:
        atividades = res.json()
        for atv in atividades:
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), 
                "data_treino": atv['start_date_local'],
                "distancia": round(atv['distance'] / 1000, 2), 
                "tipo_esporte": atv['type'],
                "nome_treino": atv['name']
            }).execute()
        return True
    return False

# =================================================================
# 🔑 GESTÃO DE SESSÃO (LOGIN)
# =================================================================
# Inicializa as variáveis de sessão se não existirem
if "logado" not in st.session_state:
    st.session_state.logado = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

# Processamento do Callback do Strava (A "volta" do usuário)
params = st.query_params
if "code" in params and "state" in params:
    cod, email_aluno = params["code"], params["state"]
    with st.spinner("Conectando ao Strava..."):
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

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            u_email = st.text_input("E-mail")
            u_senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                # Busca usuário no banco para validar
                u = supabase.table("usuarios_app").select("*").eq("email", u_email).eq("senha", hash_senha(u_senha)).execute()
                if u.data:
                    st.session_state.logado = True
                    st.session_state.user_info = u.data[0]
                    st.rerun()
                else: st.error("E-mail ou senha inválidos.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA (SÓ CHEGA AQUI SE LOGADO)
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# Barra Lateral
with st.sidebar:
    st.title("🏃‍♂️ Fábio Assessoria")
    st.write(f"Olá, **{user['nome']}**")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.session_state.user_info = None
        st.rerun()

# 👨‍🏫 TELA DO ADMIN (FÁBIO)
if eh_admin:
    st.title("👨‍🏫 Gestão Administrativa")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    if alunos.data:
        for aluno in alunos.data:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"**{aluno['nome']}** ({aluno['email']})")
                status = "✅ Ativo" if aluno['status_pagamento'] else "❌ Bloqueado"
                c2.write(f"Status: {status} | Venc: {aluno['data_vencimento']}")
                if c3.button("Alternar Acesso", key=aluno['id']):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()
    else: st.info("Sem alunos cadastrados.")

# 🚀 TELA DO CLIENTE
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    
    # --- BLOCO FINANCEIRO ---
    v_str = user.get('data_vencimento', "2000-01-01")
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and datetime.now().date() <= venc_date

    with st.expander("💳 Minha Assinatura", expanded=not pago):
        st.write(f"**Vencimento:** {venc_date.strftime('%d/%m/%Y')}")
        st.write(f"**Status:** {'✅ Ativo' if pago else '❌ Inativo'}")
        if not pago: st.warning("Acesso suspenso. Fale com o Fábio.")

    if not pago:
        st.stop()

    # --- RESULTADOS DOS TREINOS (STRAVA) ---
    # 1. Busca os tokens do Strava no banco
    res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
    
    if res_s.data:
        atleta = res_s.data[0]
        
        # Botão de Sincronizar
        if st.button("🔄 Atualizar Treinos do Strava", type="primary"):
            with st.spinner("Buscando atividades..."):
                sincronizar_dados(atleta['strava_id'], atleta['access_token'])
                st.rerun()

        # 2. BUSCA ATIVIDADES SALVAS (Sempre busca do banco para não sumir)
        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).order("data_treino", desc=True).execute()
        
        if res_atv.data:
            st.subheader("📊 Meus Resultados")
            df = pd.DataFrame(res_atv.data)
            # Organiza as colunas para ficar bonito
            df = df[['data_treino', 'tipo_esporte', 'distancia']]
            df.columns = ['Data', 'Esporte', 'Distância (km)']
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Nenhum treino encontrado. Clique no botão acima para sincronizar pela primeira vez.")
    else:
        st.warning("⚠️ Seu Strava ainda não está vinculado.")
        auth_url = (f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
                    f"&response_type=code&approval_prompt=auto&scope=read,activity:read&state={user['email']}")
        st.link_button("🔗 Conectar meu Strava", auth_url)
