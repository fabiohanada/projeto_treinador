import streamlit as st

def aplicar_estilo_css():
    """Aplica o fundo cinza claro padrão da assessoria."""
    st.markdown("""<style>.main { background-color: #f5f7f9; }</style>""", unsafe_allow_html=True)

def estilizar_botao_sincronizar():
    """
    CSS Inteligente:
    1. Define TODOS os botões da sidebar como Laranja.
    2. Reseta QUALQUER botão que venha depois do primeiro para o estilo Padrão (Branco/Cinza).
    Isso garante que Strava (1º) = Laranja e Sair (2º) = Padrão.
    """
    st.markdown("""
        <style>
        /* REGRA 1: Estilo Laranja para o botão de conexão (O primeiro) */
        [data-testid="stSidebar"] .stButton button {
            background-color: #FC4C02 !important;
            color: white !important;
            border: none !important;
            padding: 12px 20px !important;
            border-radius: 4px !important;
            font-weight: bold !important;
            font-family: sans-serif !important;
            font-size: 16px !important;
            width: 100% !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
            transition: background-color 0.2s !important;
        }
        
        /* Hover do botão Laranja */
        [data-testid="stSidebar"] .stButton button:hover {
            background-color: #E34402 !important;
            color: white !important;
        }

        /* REGRA 2: RESET para o botão 'Sair' (Qualquer botão que venha depois de outro) */
        [data-testid="stSidebar"] .stButton ~ .stButton button {
            background-color: transparent !important;
            color: inherit !important; /* Usa a cor do texto padrão do tema (preto/cinza) */
            border: 1px solid rgba(49, 51, 63, 0.2) !important; /* Borda padrão do Streamlit */
            box-shadow: none !important;
        }

        /* Hover do botão 'Sair' (Efeito sutil padrão) */
        [data-testid="stSidebar"] .stButton ~ .stButton button:hover {
            background-color: rgba(49, 51, 63, 0.05) !important;
            color: #FC4C02 !important; /* Texto fica laranja no hover */
            border-color: #FC4C02 !important;
        }
        
        /* Garante que o texto dentro do botão laranja seja branco */
        [data-testid="stSidebar"] .stButton button p {
            color: white !important;
        }
        
        /* Reseta a cor do texto para o botão Sair */
        [data-testid="stSidebar"] .stButton ~ .stButton button p {
            color: inherit !important;
        }
        </style>
    """, unsafe_allow_html=True)

def exibir_botao_strava_sidebar():
    """Exibe o botão de link original com estilo laranja sólido."""
    client_id = st.secrets.get("STRAVA_CLIENT_ID", "")
    redirect_uri = "http://192.168.1.13:8501" 
    
    user_state = ""
    if "user_info" in st.session_state and st.session_state.user_info:
        user_state = st.session_state.user_info.get('email', '')

    auth_url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope=read,activity:read_all&state={user_state}"

    html_botao = f"""
    <a href="{auth_url}" target="_self" style="text-decoration:none; width:100%;">
        <div style="
            background-color: #FC4C02;
            color: white;
            padding: 12px;
            border-radius: 4px;
            text-align: center;
            font-weight: bold;
            font-family: sans-serif;
            font-size: 16px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        ">
            Connect with Strava
        </div>
    </a>
    """
    st.markdown(html_botao, unsafe_allow_html=True)

def exibir_logo_rodape():
    """Rodapé Strava."""
    css_container = "position:fixed;bottom:10px;right:15px;z-index:9999;background:rgba(255,255,255,0.95);padding:6px 12px;border-radius:8px;border:1px solid #e0e0e0;font-family:sans-serif;display:flex;align-items:center;"
    html = f"""
    <div style="{css_container}">
        <span style="color: #666; font-size: 11px; margin-right: 5px;">Powered by</span>
        <span style="color: #FC4C02; font-size: 13px; font-weight: 800;">STRAVA</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)