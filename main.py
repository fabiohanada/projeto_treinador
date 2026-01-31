import streamlit as st
import urllib.parse
from supabase import create_client
from modules.ui import aplicar_estilo_css, exibir_rodape_strava
from modules.views import renderizar_tela_login, renderizar_tela_admin, renderizar_tela_aluno
from modules.utils import REDIRECT_URI

# Configuração da página
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# Conexão
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
except:
    st.error("Erro crítico nas configurações (Secrets).")
    st.stop()

aplicar_estilo_css()

if "logado" not in st.session_state:
    st.session_state.logado = False

# LÓGICA DE NAVEGAÇÃO
if not st.session_state.logado:
    renderizar_tela_login(supabase)
else:
    user = st.session_state.user_info
    
    # Barra Lateral (Sidebar)
    with st.sidebar:
        st.write(f"👤 {user['nome']}")
        
        # Botão Conectar Strava (Somente se NÃO for admin)
        if not user.get('is_admin', False):
            link = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={urllib.parse.quote(REDIRECT_URI + '?user_mail=' + user['email'])}&scope=activity:read_all&approval_prompt=auto"
            st.markdown(f'''<a href="{link}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;padding:10px;border-radius:5px;text-align:center;font-weight:bold;">Conectar Strava</div></a>''', unsafe_allow_html=True)
        
        if st.button("Sair", width="stretch"):
            st.session_state.clear()
            st.rerun()

    # Conteúdo Principal
    if user.get('is_admin', False):
        # TELA ADMIN (Sem Rodapé)
        renderizar_tela_admin(supabase)
    else:
        # TELA ALUNO (Com Rodapé)
        renderizar_tela_aluno(supabase, user, CLIENT_ID)
        exibir_rodape_strava() # <--- AGORA SÓ É CHAMADO AQUI