import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="Fábio Assessoria v2.6", layout="wide", page_icon="🏃‍♂️")

# Conexões Seguras
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
REDIRECT_URI = "https://seu-treino-app.streamlit.app/"

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or data_str == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

def sincronizar_strava(auth_code, aluno_id):
    token_url = "https://www.strava.com/oauth/token"
    payload = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'code': auth_code, 'grant_type': 'authorization_code'}
    try:
        r = requests.post(token_url, data=payload).json()
        if 'access_token' in r:
            token = r['access_token']
            header = {'Authorization': f"Bearer {token}"}
            atividades = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=header).json()
            for act in atividades:
                if act['type'] == 'Run':
                    dados = {
                        "aluno_id": aluno_id,
                        "data": act['start_date_local'][:10],
                        "nome_treino": act['name'],
                        "distancia": round(act['distance'] / 1000, 2),
                        "tempo_min": round(act['moving_time'] / 60, 2),
                        "fc_media": act.get('average_heartrate', 130),
                        "strava_id": str(act['id'])
                    }
                    supabase.table("treinos_alunos").upsert(dados, on_conflict="strava_id").execute()
            return True
    except: return False
    return False

# --- LOGICA DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if "code" in st.query_params: st.session_state.strava_code = st.query_params["code"]

if "user_mail" in st.query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", st.query_params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]

if not st.session_state.logado:
    st.title("🏃‍♂️ Fábio Assessoria")
    with st.form("login"):
        e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
            if u.data:
                st.session_state.logado, st.session_state.user_info = True, u.data[0]
                st.query_params["user_mail"] = e
                st.rerun()
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.write(f"Atleta: **{user['nome']}**")
    if not eh_admin:
        # CORREÇÃO DO BOTÃO: target="_blank" para abrir fora do app
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=activity:read_all&approval_prompt=force"
        st.markdown(f'<a href="{link_strava}" target="_blank"><img src="https://branding.strava.com/buttons/connect-with-strava/btn_strava_connectwith_orange.png" width="180"></a>', unsafe_allow_html=True)
        
        if "strava_code" in st.session_state:
            if sincronizar_strava(st.session_state.strava_code, user['id']):
                st.success("Sincronizado!")
                del st.session_state.strava_code
                st.rerun()

    if st.button("Sair"):
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

# --- ADMIN (CORREÇÃO DO ERRO DO PRINT) ---
if eh_admin:
    st.title("👨‍🏫 Painel Admin")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            c1, c2, c3 = st.columns([2,2,1])
            with c1:
                st.write(f"**{aluno['nome']}**")
                st.write(f"Status: {aluno['status_pagamento']}")
            with c2:
                # PROTEÇÃO CONTRA DATA 'NONE'
                data_banco = aluno.get('data_vencimento')
                try:
                    val_data = datetime.strptime(data_banco, '%Y-%m-%d').date() if data_banco and data_banco != "None" else date.today()
                except:
                    val_data = date.today()
                nova_dt = st.date_input("Vencimento", value=val_data, key=f"d_{aluno['id']}")
            with c3:
                if st.button("Salvar", key=f"b_{aluno['id']}"):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt)}).eq("id", aluno['id']).execute()
                    st.rerun()

# --- ALUNO ---
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data) if res.data else pd.DataFrame()

    if not df.empty:
        df['TRIMP'] = df['tempo_min'] * (df['fc_media'] / 100)
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df, x='data', y='TRIMP', title="Carga TRIMP"), use_container_width=True)
        with c2: 
            fig = px.line(df, x='data', y='fc_media', title="FC Média", markers=True)
            fig.add_hline(y=130, line_dash="dash", line_color="green")
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Conecte ao Strava na lateral para carregar seus dados!")
