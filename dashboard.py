import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="Fábio Assessoria v2.5", layout="wide", page_icon="🏃‍♂️")

# Conexões Seguras
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
REDIRECT_URI = "https://projeto-treinador.streamlit.app/"

# --- FUNÇÕES DE APOIO ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or data_str == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

# --- FUNÇÃO PARA PUXAR DADOS DO STRAVA ---
def sincronizar_strava(auth_code, aluno_id):
    # 1. Troca o código pelo Token
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'grant_type': 'authorization_code'
    }
    r = requests.post(token_url, data=payload).json()
    
    if 'access_token' in r:
        token = r['access_token']
        # 2. Busca as atividades (últimos 30 dias)
        header = {'Authorization': f"Bearer {token}"}
        atividades = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=header).json()
        
        for act in atividades:
            if act['type'] == 'Run': # Só treinos de corrida
                dados_treino = {
                    "aluno_id": aluno_id,
                    "data": act['start_date_local'][:10],
                    "nome_treino": act['name'],
                    "distancia": round(act['distance'] / 1000, 2),
                    "tempo_min": round(act['moving_time'] / 60, 2),
                    "fc_media": act.get('average_heartrate', 130), # Se não tiver FC, assume 130
                    "strava_id": str(act['id'])
                }
                # Salva no Supabase (ignora duplicados pelo strava_id)
                supabase.table("treinos_alunos").upsert(dados_treino, on_conflict="strava_id").execute()
        return True
    return False

# --- LÓGICA DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False

# Captura o retorno do Strava ANTES do login para não perder o código
if "code" in st.query_params:
    st.session_state.strava_code = st.query_params["code"]

if "user_mail" in st.query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", st.query_params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]

if not st.session_state.logado:
    st.title("🏃‍♂️ Fábio Assessoria - Login")
    e = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True):
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
    st.title("Painel")
    st.write(f"Atleta: **{user['nome']}**")
    
    if not eh_admin:
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=activity:read_all&approval_prompt=force"
        st.markdown(f'<a href="{link_strava}" target="_self"><img src="https://branding.strava.com/buttons/connect-with-strava/btn_strava_connectwith_orange.png" width="180"></a>', unsafe_allow_html=True)
        
        # Se voltou do Strava com código, sincroniza agora!
        if "strava_code" in st.session_state:
            if sincronizar_strava(st.session_state.strava_code, user['id']):
                st.success("Treinos sincronizados!")
                del st.session_state.strava_code # Limpa para não repetir
                st.rerun()

    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.query_params.clear()
        st.rerun()

# --- DASHBOARD ---
if eh_admin:
    st.title("👨‍🏫 Gestão Admin")
    # (Lógica do Admin com cards e bordas aqui...)
else:
    st.title(f"🚀 Treinos de {user['nome']}")
    
    # Busca treinos sincronizados
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)

    if not df.empty:
        df['TRIMP'] = df['tempo_min'] * (df['fc_media'] / 100)
        
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(df, x='data', y='TRIMP', title="Carga TRIMP", color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with col2:
            fig = px.line(df, x='data', y='fc_media', title="Frequência Média", markers=True)
            fig.add_hline(y=130, line_dash="dash", line_color="green")
            st.plotly_chart(fig, use_container_width=True)
            
        st.subheader("📋 Histórico")
        st.dataframe(df[['data', 'nome_treino', 'distancia', 'tempo_min', 'fc_media']], use_container_width=True, hide_index=True)
    else:
        st.warning("Nenhum treino encontrado. Conecte ao Strava na lateral!")
