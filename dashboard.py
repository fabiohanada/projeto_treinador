import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os, requests, hashlib
from supabase import create_client

# 1. CONFIGURAÇÕES (Mantendo o visual do dia 27/01)
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# --- CHAVES PIX (EDITE AQUI) ---
chave_pix_visivel = "seu-email@pix.com"
pix_copia_e_cola = "00020126330014BR.GOV.BCB.PIX0111suachavepix" 

# CSS para manter o layout idêntico e estilizar os alertas
st.markdown("""
    <style>
    span.no-style { text-decoration: none !important; color: inherit !important; border-bottom: none !important; }
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stVerticalBlock"] { max-width: 450px; margin: 0 auto; }
    .stButton>button { border-radius: 5px; }
    
    .pix-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 15px;
        border: 2px solid #00bfa5;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .status-pago {
        background-color: #00bfa5;
        color: white;
        padding: 2px 8px;
        border-radius: 5px;
        font-size: 0.8em;
        font-weight: bold;
        margin-left: 10px;
    }
    .pix-chave {
        background-color: #f0f2f6;
        padding: 12px;
        border-radius: 8px;
        font-family: monospace;
        font-size: 1.1em;
        color: #007bff;
        display: block;
        margin: 15px 0;
        word-break: break-all;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
REDIRECT_URI = "https://seu-treino-app.streamlit.app"

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
        with tab_cadastro:
            with st.form("cadastro_form"):
                n_c = st.text_input("Nome Completo")
                e_c = st.text_input("E-mail")
                s_c = st.text_input("Crie uma Senha", type="password")
                st.markdown("---")
                st.markdown("### 🛡️ Privacidade e LGPD")
                st.info("Seus dados de treino serão usados apenas para consultoria esportiva.")
                concordo = st.checkbox("Li e aceito os termos.")
                if st.form_submit_button("Finalizar Cadastro", use_container_width=True):
                    if concordo and n_c and e_c and s_c:
                        supabase.table("usuarios_app").insert({"nome": n_c, "email": e_c, "senha": hash_senha(s_c), "is_admin": False, "status_pagamento": False, "data_vencimento": str(datetime.now().date())}).execute()
                        st.success("Conta criada! Mude para a aba Entrar.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    st.markdown(f"📧 <span class='no-style'>{user['email']}</span>", unsafe_allow_html=True)
    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 PAINEL ADMIN (Com Alerta de Pagamento)
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    if alunos.data:
        for aluno in alunos.data:
            with st.container(border=True):
                c_info, c_btns = st.columns([3, 1])
                with c_info:
                    # ALERTA DE PAGAMENTO AQUI: Se status for true, aparece o selo PAGO
                    pago_badge = "<span class='status-pago'>PAGO</span>" if aluno['status_pagamento'] else ""
                    st.markdown(f"**Aluno:** {aluno['nome']} {pago_badge}", unsafe_allow_html=True)
                    st.markdown(f"**E-mail:** <span class='no-style'>{aluno['email']}</span>", unsafe_allow_html=True)
                    st.write(f"**Vencimento Atual:** {formatar_data_br(aluno['data_vencimento'])}")
                    
                    cl1, cl2 = st.columns([0.45, 0.55])
                    cl1.markdown("**Alterar Vencimento:**")
                    nova_data = cl2.date_input("Data", value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'),
                                              key=f"d_{aluno['id']}", format="DD/MM/YYYY", label_visibility="collapsed")
                
                with c_btns:
                    if st.button("💾 Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                        st.rerun()
                    
                    label_status = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                    if st.button(label_status, key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()

# 🚀 DASHBOARD CLIENTE (Mensagem de Comprovante Removida)
else:
    st.title("🚀 Meus Treinos")
    v_str = user.get('data_vencimento', "2000-01-01")
    venc_dt = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and datetime.now().date() <= venc_dt

    with st.expander("💳 Assinatura e Pagamento", expanded=not pago):
        c_v, c_s = st.columns(2)
        c_v.write(f"**Vencimento:** {formatar_data_br(v_str)}")
        st_color = "green" if pago else "red"
        c_s.markdown(f"**Status:** <span style='color:{st_color}; font-weight:bold;'>{'✅ ATIVO' if pago else '❌ PENDENTE'}</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={pix_copia_e_cola}"
        
        st.markdown(f"""
            <div class="pix-card">
                <h3 style="margin-top:0; color:#333;">💳 Renovação via PIX</h3>
                <p>Escaneie o QR Code abaixo para pagar:</p>
                <img src="{qr_url}" style="border: 10px solid white; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
                <p style="margin-top:15px; font-size: 0.9em;"><b>Chave PIX:</b></p>
                <span class="pix-chave">{chave_pix_visivel}</span>
                <p style="font-size: 0.9em; color: #555;"><b>Valor: R$ 00,00</b></p>
            </div>
        """, unsafe_allow_html=True)
        
        if not pago:
            st.error("⚠️ Seu acesso está suspenso. Realize o pagamento acima para liberar seus treinos.")
            st.stop()

    st.success(f"Olá {user['nome']}, seus treinos estão liberados!")
