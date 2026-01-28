import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES INICIAIS
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# CSS para diminuir campos de login e limpar visual
st.markdown("""
    <style>
    /* Centraliza e diminui a largura do formulário de login */
    [data-testid="stForm"] {
        max-width: 450px;
        margin: 0 auto;
    }
    span.no-style { text-decoration: none !important; color: inherit !important; border-bottom: none !important; }
    .stButton>button { border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 30})
    if res.status_code == 200:
        for atv in res.json():
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), "data_treino": atv['start_date_local'],
                "distancia": round(atv['distance'] / 1000, 2), "tipo_esporte": atv['type'],
                "nome_treino": atv['name']
            }).execute()
        return True
    return False

# =================================================================
# 🔑 GESTÃO DE ACESSO
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    
    # Colunas para centralizar o bloco de abas
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
                    else: st.error("E-mail ou senha incorretos.")

        with tab_cadastro:
            with st.form("cadastro_form"):
                nome_c = st.text_input("Nome Completo")
                email_c = st.text_input("Seu E-mail")
                senha_c = st.text_input("Crie uma Senha", type="password")
                
                # --- BLOCO LGPD VISÍVEL ---
                st.markdown("---")
                st.markdown("### 🛡️ Termos e Privacidade (LGPD)")
                st.info("""
                    **Uso de Dados:** Ao se cadastrar, você autoriza o processamento dos seus dados 
                    pessoais e de treinos (via Strava) para fins exclusivos de consultoria esportiva. 
                    Seus dados não serão compartilhados com terceiros.
                """)
                concordo = st.checkbox("Aceito os termos de privacidade")
                
                if st.form_submit_button("Finalizar Cadastro", use_container_width=True):
                    if not concordo:
                        st.error("Você precisa aceitar os termos da LGPD.")
                    elif nome_c and email_c and senha_c:
                        payload = {"nome": nome_c, "email": email_c, "senha": hash_senha(senha_c), 
                                   "is_admin": False, "status_pagamento": False, "data_vencimento": str(datetime.now().date())}
                        supabase.table("usuarios_app").insert(payload).execute()
                        st.success("Conta criada! Mude para a aba 'Entrar'.")
                    else: st.warning("Preencha todos os campos.")
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
                    st.write(f"**Vencimento:** {formatar_data_br(aluno['data_vencimento'])}")
                    
                    cl1, cl2 = st.columns([1, 1])
                    cl1.markdown("**Alterar Vencimento:**")
                    nova_data = cl2.date_input("Data", value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'),
                                              key=f"d_{aluno['id']}", format="DD/MM/YYYY", label_visibility="collapsed")
                with c_btns:
                    if st.button("💾 Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                        st.rerun()
                    label = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                    if st.button(label, key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()
else:
    st.title("🚀 Meus Treinos")
    # ... Lógica do cliente mantida ...
