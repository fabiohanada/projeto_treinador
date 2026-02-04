import streamlit as st

def aplicar_estilo_css():
    """
    Aplica o CSS global mantendo o layout v8.1.
    """
    st.markdown("""
        <style>
        .main { 
            background-color: #f5f7f9; 
        }
        </style>
    """, unsafe_allow_html=True)

def exibir_botao_strava_sidebar():
    """
    Exibe o botão 'Connect with Strava' (Versão Texto Robusta).
    """
    client_id = st.secrets.get("STRAVA_CLIENT_ID", "")
    redirect_uri = "http://localhost:8501" 
    
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&approval_prompt=auto&scope=read,activity:read_all"

    botao_html = f"""
    <a href="{auth_url}" target="_self" style="text-decoration: none; width: 100%; display: block;">
        <div style="
            background-color: #FC4C02; 
            color: white;
            font-weight: bold;
            font-family: sans-serif;
            font-size: 15px;
            padding: 12px 15px; 
            border-radius: 4px; 
            text-align: center;
            box-shadow: 0px 2px 5px rgba(0,0,0,0.2); 
            transition: all 0.2s ease;
        "
        onmouseover="this.style.backgroundColor='#E34402'; this.style.transform='translateY(-1px)';"
        onmouseout="this.style.backgroundColor='#FC4C02'; this.style.transform='translateY(0)';"
        >
            Connect with Strava
        </div>
    </a>
    """
    st.markdown(botao_html, unsafe_allow_html=True)

def exibir_logo_rodape():
    """
    Exibe o rodapé 'Powered by STRAVA' (Apenas Texto).
    Removido o ícone SVG conforme solicitado.
    """
    
    # CSS do container (Mantém o posicionamento v8.1)
    estilo_container = "position: fixed; bottom: 10px; right: 15px; z-index: 9999; background-color: rgba(255, 255, 255, 0.95); padding: 6px 12px; border-radius: 8px; border: 1px solid #e0e0e0; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 6px rgba(0,0,0,0.08); font-family: sans-serif;"

    # HTML Final (Sem o ícone SVG)
    html_rodape = f"""
    <div style="{estilo_container}">
        <span style="color: #666; font-size: 11px; margin-right: 4px;">Powered by</span>
        <span style="color: #FC4C02; font-size: 13px; font-weight: 800;">STRAVA</span>
    </div>
    """
    
    st.markdown(html_rodape, unsafe_allow_html=True)