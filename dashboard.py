import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        if key in st.secrets: return st.secrets[key]
    except: pass
    return os.getenv(key)

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÃO WHATSAPP CORRIGIDA PARA EVITAR ERRO 400 ---
def enviar_whatsapp(mensagem, telefone):
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        
        # Validação de segurança das chaves
        if not all([sid, token, p_from]):
            st.error("Erro: Chaves do Twilio não configuradas corretamente.")
            return False

        client = Client(sid, token)
        
        # LIMPEZA TOTAL DO NÚMERO (Remove tudo que não é número)
        tel_so_numeros = ''.join(filter(str.isdigit, str(telefone)))
        
        # Formata exatamente como o Twilio exige: whatsapp:+[numeros]
        p_to = f"whatsapp:+{tel_so_numeros}"
        
        # Garante que o From tenha o prefixo correto
        if not p_from.startswith("whatsapp:"):
            p_from = f"whatsapp:{p_from}"

        client.messages.create(body=mensagem, from_=p_from, to=p_to)
        return True
    except Exception as e:
        # Se der 400, o erro aparecerá aqui detalhado
        st.sidebar.error(f"Erro 400/Twilio: {e}")
        return False

# --- SINCRONIZAÇÃO ---
def sincronizar_dados(strava_id, access_token, refresh_token, nome, telefone):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        res = requests.get(url, headers=headers, params={'per_page': 5})
        
        # Se token expirou
        if res.status_code == 401:
            r = requests.post("https://www.strava.com/oauth/token", data={
                'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
                'grant_type': 'refresh_token', 'refresh_token': refresh_token
            })
            if r.status_code == 200:
                access_token = r.json()['access_token']
                supabase.table("usuarios").update({"access_token": access_token}).eq("strava_id", strava_id).execute()
                headers = {'Authorization': f'Bearer {access_token}'}
                res = requests.get(url, headers=headers, params={'per_page': 5})

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
                try: supabase.table("atividades_fisicas").upsert(payload).execute()
                except: continue
            
            if atividades:
                dist = atividades[0]['distance']/1000
                enviar_whatsapp(f"✅ Treino Sincronizado!\nAtleta: {nome}\nDistância: {dist:.2f}km", telefone)
            return True
        return False
    except Exception as e:
        st.error(f"Falha: {e}")
        return False

# --- LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("🏃‍♂️ Dashboard Treinador")
    e = st.text_input("E-mail", key="l_e")
    s = st.text_input("Senha", type="password", key="l_s")
    if st.button("Entrar", use_container_width=True):
        u = supabase.table("usuarios_app").select("*").eq("email", e).execute()
        if u.data and u.data[0]['senha'] == hashlib.sha256(str.encode(s)).hexdigest():
            st.session_state.logado, st.session_state.user_info = True, u.data[0]
            st.rerun()
    st.stop()

# --- DASHBOARD ---
st.sidebar.title(f"Bem-vindo, {st.session_state.user_info['nome']}")

# Botão Strava
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR AO STRAVA</div></a>', unsafe_allow_html=True)

res_strava = supabase.table("usuarios").select("*").execute()
if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    sel = st.sidebar.selectbox("Selecionar Atleta", list(atletas.keys()))
    d = atletas[sel]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token'), sel, st.session_state.user_info['telefone']):
            st.toast("Dados atualizados!")
            st.rerun()

    # --- GRÁFICOS LADO A LADO ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['dt'] = pd.to_datetime(df['data_treino'])
        df['data_f'] = df['dt'].dt.strftime('%d/%m/%Y')
        df = df.sort_values('dt')
        
        col_esq, col_dir = st.columns(2)
        with col_esq:
            st.subheader("🗓️ Atividades por Dia")
            st.bar_chart(df.groupby('data_f').size())
        with col_dir:
            st.subheader("📈 Carga Aguda vs Crônica")
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            st.line_chart(df.set_index('data_f')[['Aguda', 'Cronica']])

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
