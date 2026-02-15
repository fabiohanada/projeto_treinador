import streamlit as st

def aplicar_estilo_css():
    """Fundo cinza claro padrão."""
    st.markdown("""<style>.main { background-color: #f5f7f9; }</style>""", unsafe_allow_html=True)

def estilizar_botoes():
    """
    CSS v9.7:
    - Primary: Laranja (#FC4C02)
    - Secondary: Branco com borda
    """
    st.markdown("""
        <style>
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: #FC4C02 !important;
        }
        button[kind="primary"] {
            background-color: #FC4C02 !important;
            color: white !important;
            border: none !important;
            transition: all 0.3s !important;
        }
        button[kind="primary"]:hover {
            background-color: #d13e02 !important;
            color: white !important;
        }
        [data-testid="stSidebar"] button[kind="secondary"] {
            background-color: transparent !important;
            color: #333 !important;
            border: 1px solid #ccc !important;
        }
        [data-testid="stSidebar"] button[kind="secondary"]:hover {
            border-color: #FC4C02 !important;
            color: #FC4C02 !important;
            background-color: rgba(252, 76, 2, 0.1) !important;
        }
        </style>
    """, unsafe_allow_html=True)

def exibir_logo_rodape():
    st.markdown("""
        <div style="text-align: center;">
            <p style="color: #808495; font-size: 12px; margin-top: 10px; line-height: 1.4;">
                Este aplicativo utiliza a API do Strava, mas não é afiliado ao Strava, Inc.<br>
                © 2026 Peak Load - Desenvolvido por Fábio Assessoria | ADS Anhanguera <br>
                Termos de Uso <br>
                Política de Privacidade                
            </p>
        </div>
        <div style="position:fixed;bottom:10px;right:15px;background:white;padding:5px 10px;border-radius:5px;border:1px solid #ddd;z-index:999;">
            <span style="color:#666;font-size:10px;">Powered by</span> <span style="color:#FC4C02;font-weight:bold;">STRAVA</span>
        </div>
    """, unsafe_allow_html=True)