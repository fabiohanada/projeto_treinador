import streamlit as st
import pandas as pd
from datetime import datetime
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

# Detecta URL para o Strava
if st.secrets.get("SUPABASE_URL"):
    REDIRECT_URI = "https://seu-projeto.streamlit.app" # <--- AJUSTE PARA SUA URL REAL
else:
    REDIRECT_URI = "http://localhost:8501"

# --- FUNÇÕES CORE ---
def hash_senha(senha): 
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    try:
        sid, token = get_secret("TWILIO_ACCOUNT_SID"), get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
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

# =================================================================
# 🔑 LOGIN E CALLBACK
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False
data_hoje = datetime.now().date()

# Callback Strava
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
            if st.checkbox("Li e aceito os termos de uso (LGPD)"):
                if st.button("Finalizar Cadastro", use_container_width=True):
                    payload = {"nome": n_nome, "email": n_email, "telefone": n_tel, "senha": hash_senha(n_senha), 
                               "is_admin": False, "status_pagamento": False, "data_vencimento": str(data_hoje)}
                    supabase.table("usuarios_app").insert(payload).execute()
                    enviar_whatsapp(f"Bem-vindo {n_nome}!", n_tel)
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

# Tratamento de Data Blindado
v_str = user.get('data_vencimento')
if not v_str or not isinstance(v_str, str): v_str = "2000-01-01"
try:
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
except:
    venc_date = datetime(2000, 1, 1).date()

pago = user.get('status_pagamento', False) and data_hoje <= venc_date

# --- LÓGICA DE TELAS ---
if eh_admin:
    st.title("👨‍🏫 Painel Admin")
    tab_f, tab_p = st.tabs(["💰 Financeiro", "📊 Performance"])
    with tab_f:
        res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
        if res_alunos.data:
            for aluno in res_alunos.data:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.write(f"**{aluno['nome']}**")
                    status_txt = "Ativo" if aluno['status_pagamento'] else "Bloqueado"
                    c2.write(f"Status: {status_txt}")
                    if c3.button("Inverter Status", key=f"inv_{aluno['id']}"):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()

else:
    # --- VISÃO DO ATLETA (O QUE TINHA DESAPARECIDO) ---
    st.title("🚀 Dashboard do Atleta")
    
    res_atv_data = []
    atleta_strava = None

    if pago:
        # Busca tokens do Strava
        res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
        if res_s.data:
            atleta_strava = res_s.data[0]
            # Botão de Sincronizar no TOPO
            if st.button("🔄 ATUALIZAR TREINOS (STRAVA)", type="primary", use_container_width=True):
                with st.spinner("Sincronizando..."):
                    if sincronizar_dados(atleta_strava['strava_id'], atleta_strava['access_token']):
                        st.success("Dados atualizados!")
                        st.rerun()
            
            res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta_strava['strava_id']).execute()
            res_atv_data = res_atv.data if res_atv else []
        else:
            st.warning("⚠️ Seu Strava ainda não está vinculado.")
            auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=activity:read_all&state={user['email']}"
            st.link_button("🔗 Vincular Strava Agora", auth_url)
    else:
        st.error(f"🚨 Acesso expirado em {venc_date.strftime('%d/%m/%Y')}. Regularize seu pagamento.")

    # Tabs do Atleta
    t1, t2, t3 = st.tabs(["📊 Histórico", "📈 Análise ACWR", "💳 Pagamento"])
    
    with t1:
        if res_atv_data:
            df = pd.DataFrame(res_atv_data)
            st.dataframe(df.sort_values(by='data_treino', ascending=False), use_container_width=True)
        else:
            st.info("Sincronize seus dados para ver o histórico de treinos.")

    with t2:
        if pago and res_atv_data:
            df_p = pd.DataFrame(res_atv_data)
            df_p['data_treino'] = pd.to_datetime(df_p['data_treino'])
            df_res = df_p.groupby(df_p['data_treino'].dt.date)['distancia'].sum().resample('D').sum().fillna(0).to_frame()
            if len(df_res) >= 28:
                df_res['acwr'] = df_res['distancia'].rolling(7).mean() / df_res['distancia'].rolling(28).mean()
                st.subheader("Risco de Lesão (ACWR)")
                st.line_chart(df_res['acwr'])
            else:
                st.info("Aguardando 28 dias de dados para gerar análise.")

    with t3:
        st.subheader("Assinatura Pix")
        st.write(f"Vencimento: {venc_date.strftime('%d/%m/%Y')}")
        st.code("sua-chave-pix-aqui@exemplo.com", language="text")
        if st.button("✅ Já paguei"):
            enviar_whatsapp(f"O aluno {user['nome']} informou pagamento.", "5511999999999")
            st.toast("Fábio notificado!")
