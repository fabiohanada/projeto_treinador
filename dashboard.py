import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v2.2 (LAYOUT COMPLETO + STRAVA REAL)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v2.2", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
STRAVA_CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
REDIRECT_URI = "https://projeto-treinador.streamlit.app/" 
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or data_str == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

def gerar_link_strava():
    url = "https://www.strava.com/oauth/authorize"
    params = {"client_id": STRAVA_CLIENT_ID, "response_type": "code", "redirect_uri": REDIRECT_URI, "scope": "activity:read_all", "approval_prompt": "force"}
    return f"{url}?{urllib.parse.urlencode(params)}"

# --- LÓGICA DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if "user_mail" in st.query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", st.query_params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]

if not st.session_state.logado:
    st.markdown("<br><h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Cadastro"])
        with tab_login:
            with st.form("login"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.query_params["user_mail"] = e
                        st.rerun()
                    else: st.error("E-mail ou senha incorretos.")
        with tab_cadastro:
            with st.form("cad"):
                n_c = st.text_input("Nome")
                e_c = st.text_input("E-mail")
                t_c = st.text_input("WhatsApp (+55...)")
                s_c = st.text_input("Senha", type="password")
                if st.form_submit_button("Cadastrar"):
                    supabase.table("usuarios_app").insert({"nome": n_c, "email": e_c, "telefone": t_c, "senha": hash_senha(s_c), "status_pagamento": False, "data_vencimento": str(date.today())}).execute()
                    st.success("Cadastrado! Faça login.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.query_params.clear()
        st.rerun()

# ==========================================
# 👨‍🏫 PAINEL ADMIN
# ==========================================
if eh_admin:
    st.title("👨‍🏫 Gestão de Alunos")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            c_info, c_btns = st.columns([3, 1])
            with c_info:
                pago_status = "✅ PAGO" if aluno['status_pagamento'] else "❌ PENDENTE"
                st.markdown(f"**{aluno['nome']}** | {pago_status} | Venc: {formatar_data_br(aluno['data_vencimento'])}")
                try: val_d = datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d').date() if aluno['data_vencimento'] else date.today()
                except: val_d = date.today()
                nova_data = st.date_input("Vencimento", value=val_d, key=f"d_{aluno['id']}")
            with c_btns:
                if st.button("💾 Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                    st.rerun()
                if st.button("🔓/🔒", key=f"a_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

# ==========================================
# 🚀 PAINEL CLIENTE (DASHBOARD RESTAURADO)
# ==========================================
else:
    st.title("🚀 Meus Treinos")
    pago = user.get('status_pagamento', False)
    st.info(f"📅 **Vencimento:** {formatar_data_br(user.get('data_vencimento'))}")

    if not pago:
        with st.expander("💳 Dados para Pagamento", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.code(chave_pix_visivel)
        st.stop()

    # --- BOTÃO STRAVA ---
    st.markdown(f'<a href="{gerar_link_strava()}" target="_self"><img src="https://branding.strava.com/buttons/connect-with-strava/btn_strava_connectwith_orange.png" width="180"></a>', unsafe_allow_html=True)
    
    if "code" in st.query_params:
        st.success("Conectado ao Strava! Processando dados...")

    # --- TABELA E GRÁFICOS ---
    # Busca treinos REAIS do banco (que você criou via SQL)
    treinos_db = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    
    if treinos_db.data:
        df = pd.DataFrame(treinos_db.data)
    else:
        # Dados de exemplo enquanto o Strava não popula a tabela
        df = pd.DataFrame([{"data": "2024-01-27", "nome_treino": "Exemplo", "distancia": 10, "tempo_min": 60, "fc_media": 145}])

    st.subheader("📋 Planilha de Treinos")
    st.dataframe(df, use_container_width=True, hide_index=True)

    g1, g2 = st.columns(2)
    with g1: 
        df['TRIMP'] = df['tempo_min'] * (df['fc_media'] / 100)
        st.plotly_chart(px.bar(df, x='data', y='TRIMP', title="Carga TRIMP"), use_container_width=True)
    with g2: 
        fig = px.line(df, x='data', y='fc_media', title="Frequência Cardíaca", markers=True)
        fig.add_hline(y=130, line_dash="dash", annotation_text="Meta 130")
        st.plotly_chart(fig, use_container_width=True)
