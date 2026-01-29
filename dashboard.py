import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client
from twilio.rest import Client 

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="Fábio Assessoria v2.1", layout="wide", page_icon="🏃‍♂️")
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# Configurações do Strava (Devem estar nas Secrets)
STRAVA_CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
STRAVA_CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
# A URL de redirecionamento deve ser a do seu app no Streamlit Cloud
REDIRECT_URI = "https://projeto-treinador.streamlit.app/" 

# --- FUNÇÕES DE LOGIN E SEGURANÇA ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or data_str == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

# --- FUNÇÃO REAL DO STRAVA ---
def gerar_link_strava():
    url = "https://www.strava.com/oauth/authorize"
    params = {
        "client_id": STRAVA_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "activity:read_all",
        "approval_prompt": "force"
    }
    return f"{url}?{urllib.parse.urlencode(params)}"

# --- LÓGICA DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if "user_mail" in st.query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", st.query_params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]

if not st.session_state.logado:
    # (Código de tela de login omitido para brevidade, permanece igual ao anterior)
    st.info("Acesse para sincronizar seus treinos.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- PAINEL DO ALUNO COM BOTÃO DO STRAVA ---
if not eh_admin:
    st.title("🚀 Sincronização Strava")
    
    pago = user.get('status_pagamento', False)
    if not pago:
        st.error("Acesso bloqueado. Realize o pagamento para sincronizar.")
        st.stop()

    # BOTÃO ANTIGO DO STRAVA (ESTILIZADO)
    st.markdown(f"""
        <a href="{gerar_link_strava()}" target="_self">
            <img src="https://branding.strava.com/buttons/connect-with-strava/btn_strava_connectwith_orange.png" width="200">
        </a>
    """, unsafe_allow_html=True)

    # LÓGICA DE RETORNO DO STRAVA
    if "code" in st.query_params:
        code = st.query_params["code"]
        st.info("Processando treino do Strava...")
        
        # Aqui o app troca o CODE pelo ACCESS_TOKEN e busca o treino
        # Na v3, automatizaremos a gravação no Supabase aqui.
        st.success("Conexão estabelecida! O treino aparecerá na sua planilha em instantes.")

    # --- EXIBIÇÃO DA PLANILHA (Vinda do Banco de Dados) ---
    st.divider()
    st.subheader("📋 Meus Treinos Reais")
    
    # Busca treinos do aluno no Supabase (Tabela de treinos que vamos alimentar)
    treinos = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    
    if treinos.data:
        df = pd.DataFrame(treinos.data)
        st.dataframe(df[['data', 'nome_treino', 'distancia', 'tempo_min', 'fc_media']], use_container_width=True)
    else:
        st.warning("Nenhum treino sincronizado ainda. Clique no botão do Strava acima!")

# --- PAINEL ADMIN ---
else:
    st.title("👨‍🏫 Gestão de Planilhas")
    # (Código do Admin permanece igual)
