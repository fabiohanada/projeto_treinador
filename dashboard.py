import streamlit as st
import pandas as pd
from datetime import datetime
import os, requests, hashlib
from supabase import create_client
from dotenv import load_dotenv

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

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
    """Converte YYYY-MM-DD para DD/MM/YYYY"""
    try:
        return datetime.strptime(data_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    except:
        return data_str

def sincronizar_dados(strava_id, access_token):
    headers = {'Authorization': f'Bearer {access_token}'}
    res = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=headers, params={'per_page': 30})
    if res.status_code == 200:
        atividades = res.json()
        for atv in atividades:
            supabase.table("atividades_fisicas").upsert({
                "id_atleta": int(strava_id), 
                "data_treino": atv['start_date_local'],
                "distancia": round(atv['distance'] / 1000, 2), 
                "tipo_esporte": atv['type'],
                "nome_treino": atv['name']
            }).execute()
        return True
    return False

# =================================================================
# 🔑 GESTÃO DE SESSÃO
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

# Callback Strava
params = st.query_params
if "code" in params and "state" in params:
    cod, email_aluno = params["code"], params["state"]
    res_t = requests.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "code": cod, "grant_type": "authorization_code"
    }).json()
    if "access_token" in res_t:
        supabase.table("usuarios").upsert({
            "email": email_aluno, "strava_id": res_t["athlete"]["id"],
            "access_token": res_t["access_token"], "refresh_token": res_t["refresh_token"]
        }).execute()
        st.success("✅ Strava vinculado!")
        st.query_params.clear()
        st.rerun()

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
                else: st.error("Erro de login.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.title("🏃‍♂️ Menu")
    st.write(f"Olá, **{user['nome']}**")
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
                col1, col2, col3 = st.columns([2, 2, 1])
                
                col1.write(f"**Aluno:** {aluno['nome']}")
                col1.write(f"📧 {aluno['email']}")
                
                # Exibição da Data em Formato BR
                data_br = formatar_data_br(aluno['data_vencimento'])
                status = "✅ Ativo" if aluno['status_pagamento'] else "❌ Bloqueado"
                col2.write(f"**Status:** {status}")
                col2.write(f"**Vencimento Atual:** {data_br}")
                
                # Modificação de Data e Acesso
                nova_data = col2.date_input("Alterar Vencimento", 
                                          value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'),
                                          key=f"date_{aluno['id']}")
                
                if col3.button("Salvar Data", key=f"btn_date_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                    st.success("Data atualizada!")
                    st.rerun()
                
                label_acesso = "Bloquear Acesso" if aluno['status_pagamento'] else "Liberar Acesso"
                if col3.button(label_acesso, key=f"btn_acc_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()
    else: st.info("Nenhum aluno cadastrado.")

# 🚀 TELA DO CLIENTE
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    
    # Validação Financeira
    v_str = user.get('data_vencimento', "2000-01-01")
    venc_date = datetime.strptime(v_str, '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and datetime.now().date() <= venc_date

    with st.expander("💳 Minha Assinatura", expanded=not pago):
        st.write(f"**Vencimento:** {formatar_data_br(v_str)}")
        st.write(f"**Status:** {'✅ Ativo' if pago else '❌ Suspenso'}")
        if not pago: st.error("Acesso suspenso. Realize o pagamento para visualizar seus treinos.")

    if not pago: st.stop()

    # Treinos
    res_s = supabase.table("usuarios").select("*").eq("email", user['email']).execute()
    if res_s.data:
        atleta = res_s.data[0]
        if st.button("🔄 Sincronizar Strava", type="primary"):
            sincronizar_dados(atleta['strava_id'], atleta['access_token'])
            st.rerun()

        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta['strava_id']).order("data_treino", desc=True).execute()
        if res_atv.data:
            df = pd.DataFrame(res_atv.data)
            # Formata a coluna de data do DataFrame para BR
            df['data_treino'] = pd.to_datetime(df['data_treino']).dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(df[['data_treino', 'tipo_esporte', 'distancia']], use_container_width=True)
