import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os, requests, hashlib
from supabase import create_client

# 1. CONFIGURAÇÕES (Estilo Estável 27/01)
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# CSS para restaurar o visual exato (E-mail sem sublinhado e formulário centralizado)
st.markdown("""
    <style>
    span.no-style { text-decoration: none !important; color: inherit !important; border-bottom: none !important; }
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stVerticalBlock"] { max-width: 450px; margin: 0 auto; }
    .stButton>button { border-radius: 5px; }
    /* Estilo para a caixa de PIX */
    .pix-container {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        text-align: center;
        margin-top: 10px;
    }
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
# 🔑 LOGIN E CADASTRO (Visual 27/01)
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("<br><h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        t1, t2 = st.tabs(["🔑 Entrar", "📝 Novo Cadastro"])
        with t1:
            with st.form("login_form"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Sistema", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.rerun()
        with t2:
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
                    else: st.warning("Preencha tudo e aceite a LGPD.")
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

# 👨‍🏫 PAINEL ADMIN (Layout 27/01)
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    if alunos.data:
        for aluno in alunos.data:
            with st.container(border=True):
                c_info, c_btns = st.columns([3, 1])
                with c_info:
                    st.markdown(f"**Aluno:** {aluno['nome']}")
                    st.markdown(f"**E-mail:** <span class='no-style'>{aluno['email']}</span>", unsafe_allow_html=True)
                    st.write(f"**Vencimento Atual:** {formatar_data_br(aluno['data_vencimento'])}")
                    cl1, cl2 = st.columns([0.45, 0.55])
                    cl1.markdown("**Alterar Vencimento:**")
                    nova_data = cl2.date_input("Data", value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'), key=f"d_{aluno['id']}", format="DD/MM/YYYY", label_visibility="collapsed")
                with c_btns:
                    if st.button("💾 Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                        st.rerun()
                    label_status = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                    if st.button(label_status, key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()

# 🚀 DASHBOARD CLIENTE (Com Pagamento embutido no Expander)
else:
    st.title("🚀 Meus Treinos")
    v_str = user.get('data_vencimento', "2000-01-01")
    venc_dt = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user['status_pagamento'] and datetime.now().date() <= venc_dt

    # MANTIDO O EXPANDER DE ONTEM, APENAS COM O CONTEÚDO DE PAGAMENTO DENTRO
    with st.expander("💳 Assinatura", expanded=not pago):
        st.write(f"**Vencimento:** {formatar_data_br(v_str)}")
        
        if not pago:
            st.warning("Seu acesso está pendente de renovação.")
            # Interface de Pagamento Discreta
            st.markdown(f"""
                <div class="pix-container">
                    <p style="margin-bottom:5px;"><b>Pagamento via PIX</b></p>
                    <code style="font-size: 1.2em;">sua-chave-pix@aqui.com</code>
                    <p style="font-size: 0.8em; color: gray; margin-top:10px;">
                    Após o pagamento, envie o comprovante para o Fábio.<br>
                    Seu acesso será liberado em instantes.
                    </p>
                </div>
            """, unsafe_allow_html=True)
            st.stop() # Bloqueia os treinos se não estiver pago

    st.write("Aqui aparecerão seus gráficos e treinos sincronizados.")
