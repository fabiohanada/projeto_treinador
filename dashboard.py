import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client

# ==========================================
# VERSÃO: v6.3 (LGPD FIXA + FINANCEIRO + ADMIN)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v6.3", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
except Exception as e:
    st.error("Erro nas Secrets. Verifique as configurações.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

# --- CSS (RODAPÉ E ESPAÇAMENTO) ---
st.markdown("""
    <style>
    .main .block-container { padding-bottom: 120px; }
    .footer-strava {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: white;
        text-align: right;
        padding: 10px 30px;
        border-top: 1px solid #eee;
        z-index: 999;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN / SESSÃO ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Aluno"])
        
        with tab_login:
            with st.form("login_form"):
                e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Painel", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.rerun()
                    else: st.error("E-mail ou senha incorretos.")
        
        with tab_cadastro:
            with st.form("cad_form"):
                n_nome = st.text_input("Nome Completo")
                n_email = st.text_input("E-mail")
                n_telefone = st.text_input("Telefone/WhatsApp")
                n_senha = st.text_input("Crie uma Senha", type="password")
                
                st.markdown("---")
                # --- BLOCO LGPD (GARANTIDO) ---
                aceite = st.checkbox("Li e aceito os Termos de Uso e a Política de Privacidade (LGPD) 🔒")
                with st.expander("📄 Ler Termos Detalhados"):
                    st.write("Ao se cadastrar, você autoriza Fábio Hanada a processar seus dados de saúde e treinos para fins de consultoria esportiva. Seus dados do Strava serão usados apenas para métricas de performance.")
                
                if st.form_submit_button("Finalizar Cadastro", use_container_width=True):
                    if not aceite:
                        st.error("⚠️ Você precisa marcar o campo da LGPD para continuar.")
                    elif n_nome and n_email and n_senha:
                        try:
                            supabase.table("usuarios_app").insert({
                                "nome": n_nome, "email": n_email, "telefone": n_telefone, 
                                "senha": hash_senha(n_senha), "status_pagamento": False
                            }).execute()
                            st.success("✅ Cadastro enviado! Fale com o Fábio para liberar seu acesso.")
                        except: st.error("Este e-mail já está em uso.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if not eh_admin:
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={urllib.parse.quote(REDIRECT_URI + '?user_mail=' + user['email'])}&scope=activity:read_all&approval_prompt=auto"
        st.markdown(f'''<a href="{link_strava}" target="_self" style="text-decoration: none;"><div style="background-color: #FC4C02; color: white; padding: 12px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 20px;">Connect with STRAVA</div></a>''', unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.clear(); st.rerun()

# --- TELAS ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            col_info, col_venc, col_btns = st.columns([2, 2, 1.5])
            with col_info:
                st.subheader(aluno['nome'])
                st.caption(f"📧 {aluno['email']}")
                st.write(f"Status: {'✅ ATIVO' if aluno['status_pagamento'] else '❌ BLOQUEADO'}")
            with col_venc:
                v_data = date.fromisoformat(aluno['data_vencimento']) if aluno.get('data_vencimento') else date.today()
                nova_dt = st.date_input("Vencimento", value=v_data, key=f"d_{aluno['id']}")
            with col_btns:
                if st.button("💾 Salvar Data", key=f"s_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt), "status_pagamento": True}).eq("id", aluno['id']).execute()
                    st.rerun()
                if aluno['status_pagamento']:
                    if st.button("🚫 Bloquear", key=f"b_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": False}).eq("id", aluno['id']).execute()
                        st.rerun()
                else:
                    if st.button("✅ Ativar", key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": True}).eq("id", aluno['id']).execute()
                        st.rerun()

else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento'):
        st.error("⚠️ Seu acesso está pendente de renovação.")
        # FINANCEIRO (PIX) VISÍVEL PARA BLOQUEADOS
        with st.expander("💳 Dados para Pagamento PIX", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.code(pix_copia_e_cola)
        st.stop()
    
    # Dash do Aluno Ativo
    st.info(f"📅 Plano ativo até: **{formatar_data_br(user.get('data_vencimento'))}**")
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df, x='data', y='distancia', color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with c2: st.plotly_chart(px.line(df, x='data', y='fc_media'), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

# --- RODAPÉ STRAVA ---
st.markdown(f"""
    <div class="footer-strava">
        <img src="https://strava.github.io/api/images/api_logo_pwrdBy_strava_horiz_light.png" width="160">
    </div>
    """, unsafe_allow_html=True)
