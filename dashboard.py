import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# Estilização CSS para remover sublinhado do e-mail
st.markdown("""
    <style>
    .no-underline { text-decoration: none !important; color: inherit; }
    </style>
    """, unsafe_allow_html=True)

def get_secret(key):
    try: return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
# Mantenha o link que aparece no seu navegador:
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    """Converte YYYY-MM-DD para DD/MM/YYYY"""
    try:
        return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except:
        return data_str

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 30})
    if res.status_code == 200:
        atividades = res.json()
        for atv in atividades:
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), "data_treino": atv['start_date_local'],
                "distancia": round(atv['distance'] / 1000, 2), "tipo_esporte": atv['type']
            }).execute()
        return True
    return False

# =================================================================
# 🔑 GESTÃO DE SESSÃO
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            u_email = st.text_input("E-mail")
            u_senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", u_email).eq("senha", hash_senha(u_senha)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.rerun()
                else: st.error("Login inválido.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.title("🏃‍♂️ Menu")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 TELA DO ADMIN (FÁBIO)
if eh_admin:
    st.title("👨‍🏫 Gestão de Alunos")
    res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    if res_alunos.data:
        for aluno in res_alunos.data:
            with st.container(border=True):
                col_info, col_btn = st.columns([3, 1])
                
                with col_info:
                    st.write(f"**Aluno:** {aluno['nome']}")
                    # E-mail sem sublinhado
                    st.markdown(f"📧 <span class='no-underline'>{aluno['email']}</span>", unsafe_allow_html=True)
                    
                    status = "✅ Ativo" if aluno['status_pagamento'] else "❌ Bloqueado"
                    st.write(f"**Status:** {status}")
                    st.write(f"**Vencimento Atual:** {formatar_data_br(aluno['data_vencimento'])}")
                    
                    # Linha para Alterar Vencimento (Texto e Data lado a lado)
                    c_txt, c_date = st.columns([1, 1])
                    c_txt.markdown("<br>**Alterar Vencimento:**", unsafe_allow_html=True)
                    nova_data = c_date.date_input("", 
                                                 value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'),
                                                 key=f"d_{aluno['id']}",
                                                 format="DD/MM/YYYY") # Calendário em formato brasileiro
                
                with col_btn:
                    st.write("") # Espaçador
                    if st.button("Salvar Data", key=f"s_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                        st.success("Salvo!")
                        st.rerun()
                    
                    label_acesso = "Bloquear Acesso" if aluno['status_pagamento'] else "Liberar Acesso"
                    if st.button(label_acesso, key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()
    else: st.info("Nenhum aluno cadastrado.")

# 🚀 TELA DO CLIENTE
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    v_str = user.get('data_vencimento', "2000-01-01")
    pago = user.get('status_pagamento', False) and datetime.now().date() <= datetime.strptime(v_str, '%Y-%m-%d').date()

    with st.expander("💳 Minha Assinatura", expanded=not pago):
        st.write(f"**Vencimento:** {formatar_data_br(v_str)}")
        if not pago: st.error("Acesso suspenso. Fale com o Fábio.")

    if pago:
        res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
        if res_s.data:
            if st.button("🔄 Sincronizar Strava", type="primary"):
                sincronizar_dados(res_s.data[0]['strava_id'], res_s.data[0]['access_token'])
                st.rerun()
            
            res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", res_s.data[0]['strava_id']).order("data_treino", desc=True).execute()
            if res_atv.data:
                df = pd.DataFrame(res_atv.data)
                df['data_treino'] = pd.to_datetime(df['data_treino']).dt.strftime('%d/%m/%Y')
                st.dataframe(df[['data_treino', 'tipo_esporte', 'distancia']], use_container_width=True)
