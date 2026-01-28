import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES INICIAIS
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# CSS para dimensões e estilos (E-mail sem sublinhado)
st.markdown("""
    <style>
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stVerticalBlock"] {
        max-width: 450px;
        margin: 0 auto;
    }
    .no-style { text-decoration: none !important; color: inherit !important; border-bottom: none !important; }
    a { text-decoration: none !important; }
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
                    else: st.error("Dados incorretos.")
        with tab_cadastro:
            with st.form("cadastro_form"):
                n_c, e_c, s_c = st.text_input("Nome"), st.text_input("E-mail"), st.text_input("Senha", type="password")
                st.markdown("---")
                st.markdown("### 🛡️ Termos e Privacidade (LGPD)")
                st.info("Seus dados de treino serão usados apenas para consultoria esportiva.")
                concordo = st.checkbox("Aceito os termos de privacidade")
                if st.form_submit_button("Finalizar Cadastro", use_container_width=True):
                    if not concordo: st.error("Aceite os termos para continuar.")
                    elif n_c and e_c and s_c:
                        payload = {"nome": n_c, "email": e_c, "senha": hash_senha(s_c), "is_admin": False, "status_pagamento": False, "data_vencimento": str(datetime.now().date())}
                        supabase.table("usuarios_app").insert(payload).execute()
                        st.success("Conta criada! Use a aba Entrar.")
                    else: st.warning("Preencha todos os campos.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"👤 **{user['nome']}**")
    st.markdown(f"📧 <span class='no-style'>{user['email']}</span>", unsafe_allow_html=True)
    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 PAINEL ADMIN
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            c_info, c_btns = st.columns([3, 1])
            with c_info:
                st.markdown(f"**Aluno:** {aluno['nome']}")
                st.markdown(f"**E-mail:** <span class='no-style'>{aluno['email']}</span>", unsafe_allow_html=True)
                st.write(f"**Vencimento Atual:** {formatar_data_br(aluno['data_vencimento'])}")
                cl1, cl2 = st.columns([0.45, 0.55])
                cl1.markdown("**Alterar Vencimento:**")
                nova_d = cl2.date_input("Data", value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'), key=f"d_{aluno['id']}", format="DD/MM/YYYY", label_visibility="collapsed")
            with c_btns:
                if st.button("💾 Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_d)}).eq("id", aluno['id']).execute()
                    st.rerun()
                label = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                if st.button(label, key=f"a_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

# 🚀 DASHBOARD CLIENTE (RESTAURADO)
else:
    st.title("🚀 Meus Treinos")
    
    # --- BLOCO FINANCEIRO OBRIGATÓRIO ---
    v_str = user.get('data_vencimento', "2000-01-01")
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and datetime.now().date() <= venc_date

    with st.container(border=True):
        st.subheader("💳 Minha Assinatura")
        c1, c2 = st.columns(2)
        c1.write(f"**Vencimento:** {formatar_data_br(v_str)}")
        status_cor = "green" if pago else "red"
        status_txt = "Ativo" if pago else "Inativo/Vencido"
        c2.markdown(f"**Status:** <span style='color:{status_cor}; font-weight:bold;'>{status_txt}</span>", unsafe_allow_html=True)

    if not pago:
        st.error("⚠️ Seu acesso está suspenso. Entre em contato com o Fábio para regularizar.")
        st.stop() # Bloqueia o restante da tela
    
    # --- ÁREA DE TREINOS (SÓ APARECE SE ESTIVER PAGO) ---
    res_strava = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
    if res_strava.data:
        atleta = res_strava.data[0]
        if st.button("🔄 Sincronizar Strava", type="primary"):
            sincronizar_dados(atleta['strava_id'], atleta['access_token'])
            st.rerun()
        
        atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).order("data_treino", desc=True).execute()
        if atv.data:
            df = pd.DataFrame(atv.data)
            df['data_treino'] = pd.to_datetime(df['data_treino']).dt.strftime('%d/%m/%Y')
            st.dataframe(df[['data_treino', 'tipo_esporte', 'distancia']], use_container_width=True)
    else:
        st.warning("Vincule seu Strava abaixo.")
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read,activity:read&state={user['email']}"
        st.link_button("🔗 Conectar Strava", auth_url)
