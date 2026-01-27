import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client

# 1. CONFIGURAÇÕES INICIAIS
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

# Conexões
supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-app.streamlit.app" # Substitua pela sua URL real

# --- FUNÇÕES CORE ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    try:
        sid, token = get_secret("TWILIO_ACCOUNT_SID"), get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        client.messages.create(body=mensagem, from_=p_from, to=f"whatsapp:+{telefone}")
        return True
    except: return False

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 30})
    if res.status_code == 200:
        for atv in res.json():
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), "data_treino": atv['start_date_local'],
                "distancia": atv['distance'] / 1000, "tipo_esporte": atv['type'],
                "trimp_score": atv['moving_time'] / 60
            }).execute()
        return True
    return False

# =================================================================
# 🔑 SISTEMA DE LOGIN E CADASTRO (SÓ APARECE SE NÃO LOGADO)
# =================================================================
if "logado" not in st.session_state:
    st.session_state.logado = False

data_hoje = datetime.now().date()

if not st.session_state.logado:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🏃‍♂️ Fábio Assessoria")
        tab_login, tab_cad = st.tabs(["Entrar", "Novo Cadastro"])
        
        with tab_login:
            e = st.text_input("E-mail", key="l_email")
            s = st.text_input("Senha", type="password", key="l_senha")
            if st.button("Entrar", use_container_width=True, type="primary"):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado = True
                    st.session_state.user_info = u.data[0]
                    st.rerun()
                else: st.error("E-mail ou senha incorretos.")
        
        with tab_cad:
            n_nome = st.text_input("Nome Completo")
            n_email = st.text_input("E-mail")
            n_tel = st.text_input("WhatsApp (DDD+Número)")
            n_senha = st.text_input("Senha", type="password")
            with st.expander("Termos de Uso e LGPD"):
                st.write("Seus dados serão usados apenas para análise de performance.")
            aceite = st.checkbox("Aceito os termos")
            if st.button("Criar Conta", use_container_width=True):
                if aceite and n_nome and n_email and n_senha:
                    payload = {"nome": n_nome, "email": n_email, "telefone": n_tel, "senha": hash_senha(n_senha), "is_admin": False, "status_pagamento": False, "data_vencimento": str(data_hoje)}
                    supabase.table("usuarios_app").insert(payload).execute()
                    enviar_whatsapp(f"Olá {n_nome}, bem-vindo!", n_tel)
                    st.success("Conta criada! Faça login.")
    st.stop() # Interrompe o script aqui se não estiver logado

# =================================================================
# 🏠 ÁREA LOGADA (APÓS LOGIN)
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.header(f"👋 {user['nome']}")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# --- VISÃO DO TREINADOR ---
if eh_admin:
    st.title("👨‍🏫 Painel Admin")
    # (Código de gestão financeira que já fizemos...)

# --- VISÃO DO ATLETA ---
else:
    st.title("🚀 Seu Dashboard")
    v_str = user.get('data_vencimento', '2000-01-01')
    v_date = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and data_hoje <= v_date

    tab_resumo, tab_perf, tab_pag = st.tabs(["📊 Resumo", "📈 Performance ACWR", "💰 Pagamento"])

    with tab_resumo:
        if pago:
            # Busca dados do Strava
            res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
            if res_s.data:
                atleta = res_s.data[0]
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔄 Sincronizar Strava", use_container_width=True):
                        sincronizar_dados(atleta['strava_id'], atleta['access_token'])
                        st.rerun()
                
                # Histórico Antigo (O que você gostava)
                res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).execute()
                if res_atv.data:
                    df = pd.DataFrame(res_atv.data)
                    st.subheader("Últimos Treinos")
                    st.dataframe(df[['data_treino', 'distancia', 'tipo_esporte']].tail(5), use_container_width=True)
            else:
                st.warning("Vincule seu Strava abaixo:")
                url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=activity:read_all&state={user['email']}"
                st.link_button("🔗 Conectar Strava", url)
        else:
            st.error("Acesso bloqueado. Verifique a aba Pagamento.")

    with tab_perf:
        if pago and res_atv.data:
            # Gráfico de ACWR aqui (conforme código anterior)
            st.info("Aqui entra o gráfico de Risco de Lesão.")

    with tab_pag:
        st.subheader("Sua Assinatura")
        # Pix e Botão de aviso aqui
