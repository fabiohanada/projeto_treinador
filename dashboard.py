import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client

# 1. CONFIGURAÇÕES E CONEXÕES
load_dotenv()
st.set_page_config(page_title="Seu App Treino", layout="wide", page_icon="🏃‍♂️")

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")

# AJUSTE AQUI: Use a URL exata do seu app no Streamlit Cloud
if st.secrets.get("SUPABASE_URL"):
    REDIRECT_URI = "https://fabio-assessoria.streamlit.app" # SEM barra / no final 
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
# 🔑 LOGIN E CALLBACK DO STRAVA
# =================================================================
if "logado" not in st.session_state: 
    st.session_state.logado = False

data_hoje = datetime.now().date()

# Captura o retorno do Strava (Troca de Token)
params = st.query_params
if "code" in params and "state" in params:
    cod = params["code"]
    email_aluno = params["state"]
    with st.spinner("Finalizando conexão com o Strava..."):
        try:
            res_t = requests.post("https://www.strava.com/oauth/token", data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": cod,
                "grant_type": "authorization_code"
            })
            dados_token = res_t.json()
            if res_t.status_code == 200:
                supabase.table("usuarios").upsert({
                    "email": email_aluno, 
                    "strava_id": dados_token["athlete"]["id"],
                    "access_token": dados_token["access_token"], 
                    "refresh_token": dados_token["refresh_token"],
                    "nome": dados_token["athlete"]["firstname"]
                }).execute()
                st.success("✅ Strava vinculado com sucesso!")
                st.query_params.clear()
                st.rerun()
            else:
                st.error(f"Erro 403/401 no Strava: {dados_token.get('message')}")
                st.write("Verifique se o Client Secret nas Secrets do Streamlit está correto.")
        except Exception as e:
            st.error(f"Erro de conexão: {e}")

# Bloqueio de Login
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
            n_email = st.text_input("Seu E-mail")
            n_tel = st.text_input("WhatsApp (DDD+Número)")
            n_senha = st.text_input("Crie uma Senha", type="password")
            if st.checkbox("Aceito os termos LGPD"):
                if st.button("Criar Conta", use_container_width=True):
                    payload = {"nome": n_nome, "email": n_email, "telefone": n_tel, "senha": hash_senha(n_senha), 
                               "is_admin": False, "status_pagamento": False, "data_vencimento": str(data_hoje)}
                    supabase.table("usuarios_app").insert(payload).execute()
                    enviar_whatsapp(f"Olá {n_nome}, bem-vindo à Assessoria!", n_tel)
                    st.success("Conta criada! Faça o login.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# Barra Lateral
with st.sidebar:
    st.header(f"👋 {user['nome']}")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# --- TRATAMENTO DE DATA (ANTI-ERRO 120) ---
v_str = user.get('data_vencimento')
if not v_str or not isinstance(v_str, str): 
    v_str = "2000-01-01"
try:
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
except:
    venc_date = datetime(2000, 1, 1).date()

pago = user.get('status_pagamento', False) and data_hoje <= venc_date

# --- LÓGICA DE TELAS (ADMIN vs CLIENTE) ---
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    tab_fin, tab_perf = st.tabs(["💰 Gestão Financeira", "📊 Performance Alunos"])
    
    with tab_fin:
        res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
        if res_alunos.data:
            for aluno in res_alunos.data:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.write(f"**{aluno['nome']}** ({aluno['email']})")
                    st_atual = "✅ Ativo" if aluno['status_pagamento'] else "❌ Bloqueado"
                    c2.write(f"Status: {st_atual}")
                    if c3.button("Alterar Acesso", key=f"btn_{aluno['id']}"):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()
else:
    # VISÃO DO CLIENTE
    st.title("🚀 Seu Dashboard")
    
    # Variáveis de controle
    res_atv_data = []
    atleta_strava = None

    if pago:
        # Busca tokens do Strava
        res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
        if res_s.data:
            atleta_strava = res_s.data[0]
            # --- BOTÃO DE SINCRONIZAR NO TOPO ---
            if st.button("🔄 ATUALIZAR MEUS TREINOS (STRAVA)", type="primary", use_container_width=True):
                with st.spinner("Buscando dados..."):
                    if sincronizar_dados(atleta_strava['strava_id'], atleta_strava['access_token']):
                        st.success("Sincronizado!")
                        st.rerun()
            
            # Carrega treinos para as abas
            res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta_strava['strava_id']).execute()
            res_atv_data = res_atv.data if res_atv else []
        else:
            st.warning("⚠️ Seu Strava ainda não está vinculado.")
            auth_url = (
                f"https://www.strava.com/oauth/authorize?"
                f"client_id={CLIENT_ID}&"
                f"response_type=code&"
                f"redirect_uri={REDIRECT_URI}&"
                f"approval_prompt=auto&"
                f"scope=read,activity:read&" # Escopo simplificado para evitar 403
                f"state={user['email']}"
            )
            st.link_button("🔗 Vincular meu Strava agora", auth_url, type="primary")
    else:
        st.error(f"🚨 Acesso suspenso. Vencimento: {venc_date.strftime('%d/%m/%Y')}")

    # ABAS DO CLIENTE
    t1, t2, t3 = st.tabs(["📊 Histórico de Treinos", "📈 Índice de Carga (ACWR)", "💳 Minha Assinatura"])
    
    with t1:
        if res_atv_data:
            df = pd.DataFrame(res_atv_data)
            st.dataframe(df.sort_values(by='data_treino', ascending=False), use_container_width=True)
        else:
            st.info("Sincronize seus dados para ver o histórico.")

    with t2:
        if pago and res_atv_data:
            df_p = pd.DataFrame(res_atv_data)
            df_p['data_treino'] = pd.to_datetime(df_p['data_treino'])
            df_res = df_p.groupby(df_p['data_treino'].dt.date)['distancia'].sum().resample('D').sum().fillna(0).to_frame()
            if len(df_res) >= 28:
                df_res['acwr'] = df_res['distancia'].rolling(7).mean() / df_res['distancia'].rolling(28).mean()
                st.subheader("Risco de Lesão (Carga Aguda/Crônica)")
                st.line_chart(df_res['acwr'])
            else:
                st.info("Precisamos de pelo menos 28 dias de treinos para gerar esta análise.")
        else:
            st.info("Aba de performance disponível apenas para planos ativos com dados sincronizados.")

    with t3:
        st.subheader("Detalhes da Assinatura")
        st.write(f"Status: {'✅ Ativo' if pago else '❌ Inativo'}")
        st.write(f"Válido até: {venc_date.strftime('%d/%m/%Y')}")
        st.divider()
        st.markdown("**Pagamento via Pix:** `sua-chave-pix-aqui@pix.com`")
        if st.button("✅ Já realizei o pagamento"):
            enviar_whatsapp(f"O aluno {user['nome']} informou que já pagou.", "5511999999999")
            st.toast("Fábio foi notificado!")
