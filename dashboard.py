import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib

# 1. Configurações Iniciais
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        if key in st.secrets: return st.secrets[key]
    except: pass
    return os.getenv(key)

# Conexões
supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES DE APOIO ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        client = Client(sid, token)
        
        tel_limpo = ''.join(filter(str.isdigit, telefone))
        client.messages.create(
            body=mensagem,
            from_=p_from,
            to=f"whatsapp:+{tel_limpo}"
        )
        return True
    except Exception as e:
        st.error(f"Erro WhatsApp: {e}")
        return False

def atualizar_token_strava(refresh_token, strava_id):
    url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token', 'refresh_token': refresh_token
    }
    res = requests.post(url, data=payload)
    if res.status_code == 200:
        novo_access = res.json()['access_token']
        supabase.table("usuarios").update({"access_token": novo_access}).eq("strava_id", strava_id).execute()
        return novo_access
    return None

def sincronizar_dados(strava_id, access_token, refresh_token, nome, telefone):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get(url, headers=headers, params={'per_page': 10})
    
    if res.status_code == 401:
        access_token = atualizar_token_strava(refresh_token, strava_id)
        if access_token:
            headers = {'Authorization': f'Bearer {access_token}'}
            res = requests.get(url, headers=headers, params={'per_page': 10})

    if res.status_code == 200:
        atividades = res.json()
        for atv in atividades:
            payload = {
                "id_atleta": int(strava_id),
                "data_treino": atv['start_date_local'],
                "trimp_score": atv['moving_time'] / 60,
                "distancia": atv['distance'] / 1000,
                "tipo_esporte": atv['type']
            }
            try:
                supabase.table("atividades_fisicas").upsert(payload).execute()
            except: continue
        
        if atividades:
            dist = atividades[0]['distance']/1000
            enviar_whatsapp(f"✅ Treino Sincronizado!\nAtleta: {nome}\nDistância: {dist:.2f}km", telefone)
        return True
    return False

# --- SISTEMA DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.title("🏃‍♂️ Seu Treino App")
        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            e = st.text_input("E-mail", key="login_e")
            s = st.text_input("Senha", type="password", key="login_s")
            if st.button("Acessar", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado = True
                    st.session_state.user_info = u.data[0]
                    st.rerun()
                else: st.error("Credenciais inválidas.")
        with t2:
            n_c = st.text_input("Nome", key="cad_n")
            e_c = st.text_input("E-mail", key="cad_e")
            t_c = st.text_input("WhatsApp (Ex: 5511999999999)", key="cad_t")
            s_c = st.text_input("Senha", type="password", key="cad_s")
            if st.button("Cadastrar", use_container_width=True):
                payload = {"nome": n_c, "email": e_c, "senha": hash_senha(s_c), "telefone": t_c, "is_admin": False}
                supabase.table("usuarios_app").insert(payload).execute()
                st.success("Conta criada! Faça login.")
    st.stop()

# --- DASHBOARD PRINCIPAL ---
st.sidebar.title(f"Olá, {st.session_state.user_info['nome']}")

# Menu Admin
menu = ["Dashboard"]
if st.session_state.user_info.get('is_admin'): menu.append("👑 Admin")
escolha = st.sidebar.selectbox("Navegação", menu)

if escolha == "👑 Admin":
    st.title("👑 Painel Administrativo")
    res = supabase.table("usuarios_app").select("nome, email, telefone").execute()
    st.table(pd.DataFrame(res.data))
    st.stop()

# Botão Strava Laranja
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR AO STRAVA</div></a>', unsafe_allow_html=True)

# Lógica de Atletas
res_strava = supabase.table("usuarios").select("*").execute()
if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    sel = st.sidebar.selectbox("Atleta", list(atletas.keys()))
    d = atletas[sel]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token'), sel, st.session_state.user_info['telefone']):
            st.toast("Treinos Atualizados!")
            st.rerun()

    # --- GRÁFICOS (LIMPOS) ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['dt_objetivo'] = pd.to_datetime(df['data_treino'])
        df['data_formatada'] = df['dt_objetivo'].dt.strftime('%d/%m/%Y')
        df = df.sort_values('dt_objetivo')

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🗓️ Atividades por Dia")
            # Agrupa para garantir que dias sem treino não inventem horas no gráfico
            vendas_dia = df.groupby('data_formatada').size()
            st.bar_chart(vendas_dia)
        
        with c2:
            st.subheader("📈 Carga Aguda (7d) vs Crônica (28d)")
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            st.line_chart(df.set_index('data_formatada')[['Aguda', 'Cronica']])
    else:
        st.info("Aguardando primeira sincronização.")

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
