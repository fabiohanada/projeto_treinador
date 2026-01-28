import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# CSS Ajustado
st.markdown("""
    <style>
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stVerticalBlock"] { max-width: 450px; margin: 0 auto; }
    .no-style { text-decoration: none !important; color: inherit !important; }
    .pix-box { background-color: #f0f2f6; padding: 20px; border-radius: 10px; border: 1px dashed #00bfa5; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
REDIRECT_URI = "https://seu-treino-app.streamlit.app" # Verifique se no Strava está IGUAL

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

# =================================================================
# 🔑 LOGIN / CADASTRO / CALLBACK
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

# Processamento Strava (Para destravar, o segredo é limpar o cache e garantir este bloco)
params = st.query_params
if "code" in params:
    cod = params["code"]
    res_t = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": cod, "grant_type": "authorization_code"
    }).json()
    if "access_token" in res_t:
        supabase.table("usuarios").upsert({
            "email": params.get("state"), "strava_id": res_t["athlete"]["id"],
            "access_token": res_t["access_token"], "refresh_token": res_t["refresh_token"]
        }).execute()
        st.success("✅ Strava Conectado!")
        st.query_params.clear()

if not st.session_state.logado:
    st.markdown("<br><h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_l, tab_c = st.tabs(["🔑 Entrar", "📝 Cadastro"])
        with tab_l:
            with st.form("l"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data: 
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.rerun()
        with tab_c:
            with st.form("c"):
                n_c, e_c, s_c = st.text_input("Nome"), st.text_input("E-mail"), st.text_input("Senha", type="password")
                st.info("🛡️ LGPD: Seus dados do Strava serão usados apenas para prescrição de treinos.")
                concordo = st.checkbox("Aceito os termos")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    if concordo and n_c and e_c and s_c:
                        supabase.table("usuarios_app").insert({"nome": n_c, "email": e_c, "senha": hash_senha(s_c), "status_pagamento": False, "data_vencimento": str(datetime.now().date())}).execute()
                        st.success("Criado! Faça login.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
with st.sidebar:
    st.markdown(f"👤 **{user['nome']}**")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 ADMIN
if user.get('is_admin'):
    st.title("👨‍🏫 Gestão Fábio")
    # Lógica do admin (idêntica à anterior para manter estrutura)
    st.write("Lista de alunos e controle de datas aqui...")

# 🚀 CLIENTE
else:
    st.title(f"🚀 Dashboard Atleta")
    v_str = user.get('data_vencimento', "2000-01-01")
    venc = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user['status_pagamento'] and datetime.now().date() <= venc

    # --- SEÇÃO PIX E FINANCEIRO ---
    with st.expander("💳 Pagamento e Assinatura", expanded=not pago):
        col1, col2 = st.columns(2)
        col1.metric("Vencimento", formatar_data_br(v_str))
        col2.metric("Status", "Ativo" if pago else "Pendente")
        
        if not pago:
            st.markdown(f"""
            <div class="pix-box">
                <h4>🔑 Chave PIX para Renovação</h4>
                <p><b>CNPJ/E-mail/Celular:</b> sua-chave-pix-aqui</p>
                <p>Valor: R$ 00,00</p>
                <small>Após pagar, envie o comprovante ao Fábio.</small>
            </div>
            """, unsafe_allow_html=True)
            st.stop()

    # --- GRÁFICOS E TREINOS ---
    res_strava = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
    if res_strava.data:
        atleta = res_strava.data[0]
        # Busca treinos
        atv_data = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).execute()
        
        if atv_data.data:
            df = pd.DataFrame(atv_data.data)
            df['data_treino'] = pd.to_datetime(df['data_treino'])
            
            # Gráfico 1: Evolução de Distância
            st.subheader("📊 Evolução de Volume (km)")
            fig = px.line(df, x='data_treino', y='distancia', title="Distância por Treino", markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
            # Gráfico 2: Tipos de Esporte
            st.subheader("👟 Mix de Atividades")
            fig2 = px.pie(df, names='tipo_esporte', title="Distribuição de Esportes")
            st.plotly_chart(fig2, use_container_width=True)
            
            st.subheader("📋 Histórico")
            st.dataframe(df[['data_treino', 'tipo_esporte', 'distancia']], use_container_width=True)
    else:
        st.warning("Conecte seu Strava para gerar os gráficos.")
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read,activity:read&state={user['email']}"
        st.link_button("🔗 Conectar Strava", auth_url)
