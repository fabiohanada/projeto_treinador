import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client

# 1. CONFIGURAÇÕES E CONEXÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-app.streamlit.app" # Ajuste para sua URL real

# --- FUNÇÕES CORE ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    try:
        sid, token = get_secret("TWILIO_ACCOUNT_SID"), get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        # Garante que o número está no formato correto para o Twilio
        tel_destino = ''.join(filter(str.isdigit, str(telefone)))
        client.messages.create(body=mensagem, from_=p_from, to=f"whatsapp:+{tel_destino}")
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

# --- LÓGICA DE CALLBACK DO STRAVA ---
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

# =================================================================
# 🔑 TELA DE LOGIN E CADASTRO
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False
data_hoje = datetime.now().date()

if not st.session_state.logado:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🏃‍♂️ Fábio Assessoria")
        t_log, t_cad = st.tabs(["Entrar", "Novo Cadastro"])
        with t_log:
            e = st.text_input("E-mail", key="l_email")
            s = st.text_input("Senha", type="password", key="l_senha")
            if st.button("Entrar", use_container_width=True, type="primary"):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.rerun()
                else: st.error("E-mail ou senha inválidos.")
        with t_cad:
            n_nome = st.text_input("Nome Completo")
            n_email = st.text_input("E-mail", key="reg_email")
            n_tel = st.text_input("WhatsApp (DDD+Número)")
            n_senha = st.text_input("Crie uma Senha", type="password")
            with st.expander("Ver Termos de Uso e LGPD"):
                st.write("Seus dados de treino serão analisados apenas para fins esportivos.")
            if st.checkbox("Aceito os termos", key="check_lgpd"):
                if st.button("Finalizar Cadastro", use_container_width=True):
                    payload = {"nome": n_nome, "email": n_email, "telefone": n_tel, "senha": hash_senha(n_senha), 
                               "is_admin": False, "status_pagamento": False, "data_vencimento": str(data_hoje)}
                    supabase.table("usuarios_app").insert(payload).execute()
                    enviar_whatsapp(f"Bem-vindo {n_nome}! Cadastro realizado.", n_tel)
                    st.success("Conta criada! Vá para a aba Entrar.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.header(f"👋 {user['nome']}")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

if eh_admin:
    st.title("👨‍🏫 Painel do Treinador")
    # ... (Seu código de admin aqui)
else:
    # --- VISÃO ATLETA ---
    v_str = user.get('data_vencimento', '2000-01-01')
    v_date = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and data_hoje <= v_date

    # Inicializa variáveis para evitar NameError
    res_atv = None
    atleta_strava = None

    if pago:
        res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
        if res_s.data:
            atleta_strava = res_s.data[0]
            res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta_strava['strava_id']).execute()

    t1, t2, t3 = st.tabs(["📊 Resumo", "📈 Performance ACWR", "💰 Assinatura"])

    with t1:
        st.title("🚀 Meus Treinos")
        if pago:
            if atleta_strava:
                if st.button("🔄 Sincronizar Strava", type="primary"):
                    sincronizar_dados(atleta_strava['strava_id'], atleta_strava['access_token'])
                    st.rerun()
                if res_atv and res_atv.data:
                    df = pd.DataFrame(res_atv.data)
                    st.dataframe(df.tail(10), use_container_width=True)
            else:
                st.warning("Vincule seu Strava abaixo")
                link = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=activity:read_all&state={user['email']}"
                st.link_button("🔗 Conectar Strava", link)
        else:
            st.error("Acesso bloqueado por pendência financeira.")

    with t2:
        if pago and res_atv and res_atv.data:
            st.subheader("Análise de Carga (Risco de Lesão)")
            df_p = pd.DataFrame(res_atv.data)
            df_p['data_treino'] = pd.to_datetime(df_p['data_treino'])
            df_res = df_p.groupby(df_p['data_treino'].dt.date)['distancia'].sum().resample('D').sum().fillna(0).to_frame()
            if len(df_res) >= 28:
                df_res['acwr'] = df_res['distancia'].rolling(7).mean() / df_res['distancia'].rolling(28).mean()
                st.line_chart(df_res['acwr'])
            else: st.info("Histórico insuficiente para cálculo (mínimo 28 dias).")

    with t3:
        st.header("💳 Pagamento")
        if pago: st.success(f"Assinatura ativa até {venc_date.strftime('%d/%m/%Y')}")
        else:
            st.markdown("**Chave Pix:** `seu-email@pix.com`")
            if st.button("✅ Já paguei"):
                enviar_whatsapp(f"Pagamento informado por {user['nome']}", "5511999999999")
                st.toast("Fábio notificado!")
