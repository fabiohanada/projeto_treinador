import streamlit as st
import pandas as pd
import hashlib
from supabase import create_client
from dotenv import load_dotenv

# --- CONFIGURAÇÕES INICIAIS ---
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- FUNÇÕES ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

# --- LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🏃‍♂️ Bem-vindo ao Seu Treino")
    e = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True):
        senha_h = hash_senha(s)
        u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", senha_h).execute()
        if u.data:
            st.session_state.logado = True
            st.session_state.user_info = u.data[0]
            st.rerun()
        else:
            st.error("Credenciais inválidas.")
    st.stop()

# --- LÓGICA DE DIRECIONAMENTO ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)



if eh_admin:
    # ==========================================
    # 👨‍🏫 INTERFACE DO TREINADOR (ADMIN)
    # ==========================================
    st.title("👨‍🏫 Painel do Treinador")
    st.sidebar.success(f"Logado como Treinador: {user['nome']}")
    
    # Seleção de Atletas (O Admin vê todos)
    res_atleta = supabase.table("usuarios").select("*").execute()
    if res_atleta.data:
        lista_atletas = {at['nome']: at for at in res_atleta.data}
        atleta_sel = st.sidebar.selectbox("Gerenciar Atleta", list(lista_atletas.keys()))
        dados_atleta = lista_atletas[atleta_sel]
        
        # Aqui entra sua lógica técnica de ACWR, Metas e Sincronização Strava
        st.subheader(f"Análise Técnica: {atleta_sel}")
        st.info("Aqui você visualiza as cargas agudas/crônicas e define o planejamento.")
        # ... (seu código de análise técnica aqui) ...
    else:
        st.info("Nenhum atleta cadastrado no sistema.")

else:
    # ==========================================
    # 🏃‍♂️ INTERFACE DO ATLETA (CLIENTE)
    # ==========================================
    st.title(f"🚀 Fala, {user['nome']}!")
    st.sidebar.info(f"Logado como Atleta")
    
    # O Atleta vê apenas os PRÓPRIOS dados
    # Buscamos os treinos usando o strava_id que deve estar vinculado ao e-mail dele
    strava_id_atleta = user.get('strava_id') # Supondo que você vinculou isso
    
    if strava_id_atleta:
        st.subheader("🏁 Seu Progresso")
        # Aqui entra a barra de meta semanal e gráfico de área motivacional
        # ... (seu código de visão cliente aqui) ...
    else:
        st.warning("Seu perfil ainda não está vinculado a uma conta Strava. Fale com seu treinador!")

# --- SAÍDA ---
st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
