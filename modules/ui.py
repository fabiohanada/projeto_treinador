import streamlit as st
import base64
import os

def aplicar_estilo_css():
    st.markdown("""
        <style>
        /* Espaço no final da página para o conteúdo não ficar atrás do rodapé */
        .main .block-container { 
            padding-bottom: 100px; 
        }
        
        /* CSS DO RODAPÉ (Força bruta para ficar na direita) */
        .footer-container {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: white;
            border-top: 1px solid #e0e0e0;
            padding: 10px 30px;
            z-index: 99999;
            text-align: right; /* Mágica que joga tudo para a direita */
        }
        
        /* Configura o tamanho do logo dentro do HTML */
        .footer-container img {
            height: 35px; /* Altura fixa discreta */
            width: auto;
            margin: 0;
        }

        /* Estilo dos cards do Admin */
        div[data-testid="stVerticalBlockBorderWrapper"] { 
            border: 1px solid #f0f2f6; 
            border-radius: 10px; 
            padding: 15px; 
            margin-bottom: 10px;
        }
        </style>
        """, unsafe_allow_html=True)

def get_base64_image(image_path):
    """Converte a imagem local em código texto para o HTML ler"""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

def exibir_rodape_strava():
    arquivo_local = "strava_logo.png"
    
    # URL de backup caso o arquivo local não exista
    url_online = "https://raw.githubusercontent.com/strava/api/master/docs/images/api_logo_pwrdBy_strava_horiz_light.png"

    html_content = ""

    # Lógica: Tenta ler o arquivo local e converter para Base64
    if os.path.exists(arquivo_local):
        try:
            img_b64 = get_base64_image(arquivo_local)
            # Monta o HTML com a imagem embutida
            html_content = f'<img src="data:image/png;base64,{img_b64}" alt="Powered by Strava">'
        except:
            # Se der erro na conversão, usa o link online
            html_content = f'<img src="{url_online}" alt="Powered by Strava">'
    else:
        # Se não achar o arquivo, usa o link online
        html_content = f'<img src="{url_online}" alt="Powered by Strava">'

    # Renderiza o Bloco HTML Final
    st.markdown(f"""
        <div class="footer-container">
            {html_content}
        </div>
    """, unsafe_allow_html=True)