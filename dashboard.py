import streamlit as st
import base64
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard Strava v6.4", layout="wide")

# --- 1. FUNÇÃO DE CONVERSÃO BASE64 (Blindagem de Imagem) ---
def get_base64(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        # Placeholder caso a imagem não exista para não quebrar o código
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

# Carregar logo (substitua pelo seu arquivo)
logo_base64 = get_base64("logo_strava.png")

# --- 2. TRAVA DE SESSÃO E SEGURANÇA ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

# --- 3. INJEÇÃO DE CSS (Layout Estável) ---
st.markdown(f"""
    <style>
    /* Fixar Rodapé e evitar 'balanço' */
    .footer {{
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: white;
        color: #FC4C02; /* Laranja Strava */
        text-align: center;
        padding: 10px;
        border-top: 1px solid #eee;
        z-index: 1000;
    }}
    
    /* Estilização do Container LGPD */
    .lgpd-container {{
        background-color: #f9f9f9;
        padding: 20px;
        border-left: 5px solid #FC4C02;
        border-radius: 5px;
        margin: 10px 0;
    }}

    /* Blindagem do botão Admin */
    .stButton>button {{
        border-radius: 20px;
        font-weight: bold;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 4. LÓGICA DE INTERFACE ---

# Sidebar com área de Admin
with st.sidebar:
    st.title("⚙️ Painel de Controle")
    if not st.session_state.autenticado:
        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Acessar Admin"):
            if user == "admin" and senha == "1234": # Exemplo simples
                st.session_state.autenticado = True
                st.success("Logado!")
                st.rerun()
            else:
                st.error("Credenciais inválidas")
    else:
        st.write(f"Conectado como: **Admin**")
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.rerun()

# Corpo Principal
st.header("🚀 Performance Strava - v6.4")

# Container LGPD
st.markdown('<div class="lgpd-container">', unsafe_allow_html=True)
st.subheader("Privacidade e Termos (LGPD)")
aceitou = st.checkbox("Declaro que autorizo o processamento dos meus dados de atividade física para fins de análise de performance.")
st.markdown('</div>', unsafe_allow_html=True)

if aceitou:
    st.info("✅ Termos aceitos. Carregando dados da API...")
    
    # Simulação de Dashboard
    col1, col2, col3 = st.columns(3)
    col1.metric("Distância Total", "120 km", "+5%")
    col2.metric("Elevação", "1.250 m", "10%")
    col3.metric("Tempo Ativo", "10h 15m", "-2%")
    
    # Espaço para os gráficos
    st.area_chart([10, 25, 20, 40, 35, 50])
    
else:
    st.warning("⚠️ Aguardando aceite dos termos para exibir métricas.")

# --- 5. RODAPÉ BLINDADO (HTML + Base64) ---
st.markdown(f"""
    <div class="footer">
        <img src="data:image/png;base64,{logo_base64}" width="120" style="vertical-align: middle; margin-right: 10px;">
        <span style="font-family: sans-serif; font-weight: bold;">
            Powered by Strava | Atualizado em: {datetime.now().strftime('%d/%m/%Y')}
        </span>
    </div>
    """, unsafe_allow_html=True)
