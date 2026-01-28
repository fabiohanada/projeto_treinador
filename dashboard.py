import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES INICIAIS
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# CSS para formatação fina (E-mail sem sublinhado e alinhamentos)
st.markdown("""
    <style>
    span.no-style { text-decoration: none !important; color: inherit !important; border-bottom: none !important; }
    .stButton>button { border-radius: 5px; }
    .stExpander { border: 1px solid #f0f2f6; }
    </style>
    """, unsafe_allow_html=True)

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
# Mantenha a URL correta do seu app aqui
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES DE APOIO ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 30})
    if res.status_code == 200:
        for atv in res.json():
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), "data_treino": atv['start_date_local'],
                "distancia": round(atv['distance'] / 1000, 2), "tipo_esporte": atv['type'],
                "nome_treino": atv['name']
            }).execute()
        return True
    return False

# =================================================================
# 🔑 GESTÃO DE ACESSO (LOGIN E CADASTRO)
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

# Processamento do Callback do Strava
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
    tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Cadastro"])
    
    with tab_login:
        with st.form("login_form"):
            e = st.text_input("E-mail")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar Sistema", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.rerun()
                else: st.error("E-mail ou senha incorretos.")

    with tab_cadastro:
        with st.form("cadastro_form"):
            nome_c = st.text_input("Nome Completo")
            email_c = st.text_input("Seu E-mail")
            senha_c = st.text_input("Crie uma Senha", type="password")
            st.markdown("---")
            st.caption("🛡️ **LGPD e Privacidade**")
            st.caption("Ao se cadastrar, você aceita que seus dados de treino do Strava sejam coletados para fins de consultoria esportiva.")
            concordo = st.checkbox("Li e concordo com os termos.")
            if st.form_submit_button("Criar minha conta", use_container_width=True):
                if concordo and nome_c and email_c and senha_c:
                    payload = {"nome": nome_c, "email": email_c, "senha": hash_senha(senha_c), 
                               "is_admin": False, "status_pagamento": False, "data_vencimento": str(datetime.now().date())}
                    supabase.table("usuarios_app").insert(payload).execute()
                    st.success("Conta criada! Vá para a aba 'Entrar'.")
                else: st.warning("Preencha tudo e aceite a LGPD.")
    st.stop()

# =================================================================
# 🏠 DASHBOARD LOGADO
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- BARRA LATERAL FIXA ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    st.markdown(f"📧 <span class='no-style'>{user['email']}</span>", unsafe_allow_html=True)
    st.divider()
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 TELA DO ADMIN
if eh_admin:
    st.title("👨‍🏫 Painel do Treinador")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    if alunos.data:
        for aluno in alunos.data:
            with st.container(border=True):
                c_info, c_btns = st.columns([3, 1])
                with c_info:
                    st.markdown(f"**Aluno:** {aluno['nome']}")
                    st.markdown(f"**E-mail:** <span class='no-style'>{aluno['email']}</span>", unsafe_allow_html=True)
                    st.write(f"**Status:** {'✅ Ativo' if aluno['status_pagamento'] else '❌ Bloqueado'}")
                    st.write(f"**Vencimento Atual:** {formatar_data_br(aluno['data_vencimento'])}")
                    
                    # Alinhamento da Alteração de Vencimento
                    cl1, cl2 = st.columns([0.8, 1])
                    cl1.markdown("<br>**Alterar Vencimento:**", unsafe_allow_html=True)
                    nova_data = cl2.date_input("Data", value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'),
                                              key=f"d_{aluno['id']}", format="DD/MM/YYYY", label_visibility="collapsed")
                
                with c_btns:
                    st.write("")
                    if st.button("💾 Salvar Data", key=f"s_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                        st.rerun()
                    
                    txt_btn = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                    if st.button(txt_btn, key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()

# 🚀 TELA DO CLIENTE
else:
    st.title(f"🚀 Dashboard do Atleta")
    venc = datetime.strptime(user['data_vencimento'], '%Y-%m-%d').date()
    pago = user['status_pagamento'] and datetime.now().date() <= venc

    with st.expander("💳 Minha Assinatura", expanded=not pago):
        st.write(f"**Vencimento:** {formatar_data_br(user['data_vencimento'])}")
        if not pago: 
            st.error("Acesso suspenso. Fale com o Fábio.")
            st.stop()

    # Treinos
    res_strava = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
    if res_strava.data:
        atleta = res_strava.data[0]
        if st.button("🔄 Sincronizar Strava", type="primary"):
            sincronizar_dados(atleta['strava_id'], atleta['access_token'])
            st.rerun()
        
        atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).order("data_treino", desc=True).execute()
        if atv.data:
            df = pd.DataFrame(atv.data)
            df['data_treino'] = pd.to_datetime(df['data_treino']).dt.strftime('%d/%m/%Y')
            st.dataframe(df[['data_treino', 'tipo_esporte', 'distancia']], use_container_width=True)
    else:
        st.warning("Vincule seu Strava.")
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read,activity:read&state={user['email']}"
        st.link_button("🔗 Conectar Strava", auth_url)
