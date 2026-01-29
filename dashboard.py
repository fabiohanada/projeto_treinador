import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client

# ==========================================
# VERSÃO: v2.8 (CORREÇÃO DE SINTAXE E LAYOUT)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v2.8", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES SEGURAS ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
except Exception as e:
    st.error("Erro nas Secrets: Verifique as chaves no Streamlit Cloud.")
    st.stop()

REDIRECT_URI = "https://projeto-treinador.streamlit.app/" 
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): 
    return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

def sincronizar_strava(auth_code, aluno_id):
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'grant_type': 'authorization_code'
    }
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
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        with st.form("login_v2"):
            e = st.text_input("E-mail")
            s = st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar Painel", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.query_params["user_mail"] = e
                    st.rerun()
                else: st.error("E-mail ou senha incorretos.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### Bem-vindo, \n**{user['nome']}**")
    st.write("---")
    if not eh_admin:
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=activity:read_all&approval_prompt=force"
        st.markdown(f'''
            <a href="{link_strava}" target="_blank" style="text-decoration: none;">
                <div style="background-color: #FC4C02; color: white; padding: 12px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 20px;">
                    🟠 CONECTAR COM STRAVA
                </div>
            </a>
        ''', unsafe_allow_html=True)
        if "strava_code" in st.session_state:
            with st.spinner("Sincronizando..."):
                if sincronizar_strava(st.session_state.strava_code, user['id']):
                    st.success("Treinos atualizados!")
                    del st.session_state.strava_code
                    st.rerun()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

# --- ÁREA ADMIN ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.markdown(f"**{aluno['nome']}**")
                st.write(f"Status: {'✅ Ativo' if aluno['status_pagamento'] else '❌ Pendente'}")
            with col2:
                dt_banco = aluno.get('data_vencimento')
                try: val_data = datetime.strptime(str(dt_banco), '%Y-%m-%d').date() if dt_banco and str(dt_banco) != "None" else date.today()
                except: val_data = date.today()
                nova_dt = st.date_input("Vencimento", value=val_data, key=f"d_{aluno['id']}")
            with col3:
                if st.button("Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt)}).eq("id", aluno['id']).execute()
                    st.success("Ok!")
# --- ÁREA ALUNO ---
else:
    st.title(f"🚀 Dashboard de Performance")
    st.info(f"📅 Seu plano vence em: **{formatar_data_br(user.get('data_vencimento'))}**")
    
    # AQUI ESTAVA O ERRO DE SINTAXE - LINHA CORRIGIDA ABAIXO
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)

    if not df.empty:
        df['TRIMP'] = df['tempo_min'] * (df['fc_media'] / 100)
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df, x='data', y='TRIMP', title="Carga (TRIMP)", color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with c2:
            fig = px.line(df, x='data', y='fc_media', title="FC Média", markers=True)
            fig.add_hline(y=130, line_dash="dash", line_color="green")
            st.plotly_chart(fig, use_container_width=True)
        st.subheader("📋 Histórico")
        st.dataframe(df[['data', 'nome_treino', 'distancia', 'tempo_min', 'fc_media', 'TRIMP']], use_container_width=True, hide_index=True)
    else:
        st.warning("Conecte ao Strava na lateral para carregar seus treinos!")
