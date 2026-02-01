import streamlit as st
import base64
import os

def aplicar_estilo_css():
    st.markdown("""
        <style>
        /* Garante espaço no final da página para o conteúdo não ficar atrás do rodapé */
        .main .block-container { 
            padding-bottom: 120px; 
        }
        
        /* Rodapé Fixo na Direita */
        .footer-container {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: white;
            border-top: 1px solid #e0e0e0;
            padding: 10px 30px;
            z-index: 99999;
            text-align: right; /* Alinha conteúdo à direita */
        }
        
        .footer-container img {
            height: 32px;
            width: auto;
        }

        /* Aumenta o espaço entre os botões da Sidebar */
        div[data-testid="stSidebarNav"] {
            margin-bottom: 20px;
        }
        
        /* Classe utilitária para margens */
        .spacer {
            margin-top: 20px;
        }
        </style>
        """, unsafe_allow_html=True)

def exibir_rodape_strava():
    """Exibe o logo Powered by Strava fixo no canto inferior direito."""
    arquivo_local = "strava_logo.png"
    url_oficial = "https://raw.githubusercontent.com/strava/api/master/docs/images/api_logo_pwrdBy_strava_horiz_light.png"
    
    # Tenta carregar local via Base64 para garantir posicionamento
    img_html = f'<img src="{url_oficial}" alt="Powered by Strava">'
    
    if os.path.exists(arquivo_local):
        try:
            with open(arquivo_local, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
                img_html = f'<img src="data:image/png;base64,{img_b64}" alt="Powered by Strava">'
        except:
            pass            

    st.markdown(f'<div class="footer-container">{img_html}</div>', unsafe_allow_html=True)