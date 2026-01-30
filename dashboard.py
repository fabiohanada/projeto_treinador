import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests, base64
from supabase import create_client

# ==========================================
# VERSÃO: v6.4 CORRIGIDA (ADMIN + LGPD + RODAPÉ)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v6.4", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
except Exception as e:
    st.error("Erro nas Secrets.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

# --- CSS DE ESTABILIZAÇÃO (RODAPÉ FIXO) ---
st.markdown("""
    <style>
    .footer-strava {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: white;
        text-align: center;
        padding: 10px 0;
        border-top: 1px solid #eaeaea;
        z-index: 999;
    }
    .stApp { margin-bottom: 60px; } /* Evita que o rodapé cubra o conteúdo */
    </style>
    """, unsafe_allow_html=True)

# --- SISTEMA DE LOGIN PERSISTENTE ---
if "logado" not in st.session_state:
    st.session_state.logado = False

# Captura retorno do Strava
params = st.query_params
if "code" in params and "user_mail" in params:
    u = supabase.table("usuarios_app").select("*").eq("email", params["user_mail"]).execute()
    if u.data:
        st.session_state.logado = True
        st.session_state.user_info = u.data[0]

# --- TELA DE LOGIN / CADASTRO ---
if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Aluno"])
        with tab_login:
            with st.form("login_form"):
                e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Painel", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado = True
                        st.session_state.user_info = u.data[0]
                        st.rerun()
                    else: st.error("E-mail ou senha incorretos.")
        
        with tab_cadastro:
            with st.form("cad_form"):
                n_nome = st.text_input("Nome Completo")
                n_email = st.text_input("E-mail")
                n_senha = st.text_input("Crie uma Senha", type="password")
                
                # LGPD RESTAURADO DENTRO DO FORMULÁRIO
                aceite = st.checkbox("Li e aceito os Termos de Uso e a Política de Privacidade (LGPD). Autorizo o uso dos meus dados de treino para análise de performance.")
                with st.expander("📄 Ver Termos de Uso e LGPD"):
                    st.write("Dados coletados exclusivamente para consultoria esportiva por Fábio Hanada. Seus dados do Strava serão usados apenas para métricas de performance.")
                
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    if not aceite: 
                        st.error("Você precisa aceitar os termos.")
                    elif n_nome and n_email and n_senha:
                        try:
                            supabase.table("usuarios_app").insert({"nome": n_nome, "email": n_email, "senha": hash_senha(n_senha), "status_pagamento": False}).execute()
                            st.success("Cadastrado! Peça liberação ao Fábio.")
                        except: 
                            st.error("E-mail já cadastrado.")
    st.stop()

# --- DADOS DO USUÁRIO ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if not eh_admin:
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={urllib.parse.quote(REDIRECT_URI + '?user_mail=' + user['email'])}&scope=activity:read_all&approval_prompt=auto"
        st.markdown(f'''<a href="{link_strava}" target="_self" style="text-decoration: none;"><div style="background-color: #FC4C02; color: white; padding: 12px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 20px;">Connect with STRAVA</div></a>''', unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# --- TELAS (ADMIN E ALUNO RESTAURADAS) ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1.5, 1.5])
            with c1: 
                st.write(f"**{aluno['nome']}**")
                st.write(f"Status: {'✅ Ativo' if aluno['status_pagamento'] else '❌ Bloqueado'}")
            with c2: 
                venc_atual = datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d').date() if aluno.get('data_vencimento') else date.today()
                nova_dt = st.date_input("Vencimento", value=venc_atual, key=f"d_{aluno['id']}")
            with c3:
                if st.button("💾 Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt), "status_pagamento": True}).eq("id", aluno['id']).execute()
                    st.rerun()
                if st.button("Bloquear", key=f"b_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": False}).eq("id", aluno['id']).execute()
                    st.rerun()
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento'):
        st.error("⚠️ Acesso pendente de renovação.")
        with st.expander("💳 Dados para Pagamento PIX", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.code(pix_copia_e_cola)
        st.stop()
    
    # Gráficos e Histórico
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1: st.plotly_chart(px.bar(df, x='data', y='distancia', title="Distância (km)", color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with col2: st.plotly_chart(px.line(df, x='data', y='fc_media', title="FC Média"), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- RODAPÉ STRAVA (ESTABILIZADO) ---
st.markdown(f"""
    <div class="footer-strava">
        <img src="https://strava.github.io/api/images/api_logo_pwrdBy_strava_horiz_light.png" width="160">
    </div>
    """, unsafe_allow_html=True)
