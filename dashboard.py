import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib, urllib.parse
from supabase import create_client

# 1. CONFIGURAÇÕES (Estilo Estável 27/01)
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# --- CONFIGURAÇÃO PIX ---
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# CSS para restaurar o visual e criar os cards do Strava
st.markdown("""
    <style>
    span.no-style { text-decoration: none !important; color: inherit !important; border-bottom: none !important; }
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stVerticalBlock"] { max-width: 450px; margin: 0 auto; }
    .stButton>button { border-radius: 5px; }
    
    /* Estilo Card Strava */
    .strava-card {
        background-color: #ffffff;
        border-left: 5px solid #FC4C02; /* Laranja Strava */
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 15px;
    }
    .strava-title { color: #FC4C02; font-weight: bold; font-size: 1.1em; margin-bottom: 5px; }
    .strava-metrics { display: flex; gap: 20px; font-size: 0.9em; color: #555; }
    .metric-item b { color: #000; font-size: 1.1em; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()
def formatar_data_br(data_str):
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

# =================================================================
# 🔑 LOGIN E CADASTRO
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("<br><h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Cadastro"])
        with tab_login:
            with st.form("login_form"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Sistema", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.rerun()
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 PAINEL ADMIN (Layout 27/01)
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    if alunos.data:
        for aluno in alunos.data:
            with st.container(border=True):
                c_info, c_btns = st.columns([3, 1])
                with c_info:
                    pago_badge = "<span style='background:#00bfa5;color:white;padding:2px 8px;border-radius:5px;font-size:0.8em;'>PAGO</span>" if aluno['status_pagamento'] else ""
                    st.markdown(f"**Aluno:** {aluno['nome']} {pago_badge}", unsafe_allow_html=True)
                    st.write(f"**Vencimento:** {formatar_data_br(aluno['data_vencimento'])}")
                    nova_data = st.date_input("Novo Vencimento", value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'), key=f"d_{aluno['id']}")
                with c_btns:
                    if st.button("💾 Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                        st.rerun()
                    if st.button("🔓 Liberar/Bloquear", key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()

# 🚀 DASHBOARD CLIENTE (Estilo Strava)
else:
    st.title("🚀 Meus Treinos")
    pago = user.get('status_pagamento', False)
    
    with st.expander("💳 Assinatura e Pagamento", expanded=not pago):
        if not pago:
            payload_encoded = urllib.parse.quote(pix_copia_e_cola)
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={payload_encoded}"
            st.markdown(f"""
                <div class="pix-card">
                    <h3>💳 Renovação via PIX (R$ 9,99)</h3>
                    <img src="{qr_url}" width="200">
                    <p class="pix-chave">{chave_pix_visivel}</p>
                </div>
            """, unsafe_allow_html=True)
            st.stop()

    st.success(f"Olá {user['nome']}, veja seus últimos treinos:")

    # --- LISTA DE TREINOS TESTE (ESTILO STRAVA) ---
    treinos = [
        {"nome": "Adaptação e Mobilidade", "dist": "5.0 km", "tempo": "32:10", "pace": "6:26 /km"},
        {"nome": "Fortalecimento Core e Estabilidade", "dist": "---", "tempo": "45:00", "pace": "N/A"},
        {"nome": "Resistência Aeróbica (Trote)", "dist": "8.2 km", "tempo": "54:30", "pace": "6:38 /km"},
        {"nome": "Técnica de Corrida e Educativos", "dist": "3.0 km", "tempo": "25:00", "pace": "8:20 /km"},
    ]

    for t in treinos:
        st.markdown(f"""
            <div class="strava-card">
                <div class="strava-title">🏃‍♂️ {t['nome']}</div>
                <div class="strava-metrics">
                    <div class="metric-item">Distância<br><b>{t['dist']}</b></div>
                    <div class="metric-item">Tempo<br><b>{t['tempo']}</b></div>
                    <div class="metric-item">Ritmo Médio<br><b>{t['pace']}</b></div>
                </div>
            </div>
        """, unsafe_allow_html=True)
