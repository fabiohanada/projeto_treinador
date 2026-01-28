import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import hashlib, urllib.parse
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v1 (LAYOUT INTEGRAL - NÃO MODIFICAR)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()
def formatar_data_br(data_str):
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

def enviar_whatsapp_real(nome_aluno, telefone, treino_nome, km, tempo):
    try:
        sid = st.secrets["TWILIO_ACCOUNT_SID"]
        token = st.secrets["TWILIO_AUTH_TOKEN"]
        num_origem = f"whatsapp:{st.secrets['TWILIO_PHONE_NUMBER']}"
        client = Client(sid, token)
        tel_limpo = "".join(filter(str.isdigit, str(telefone)))
        if not tel_limpo.startswith("55"): tel_limpo = "55" + tel_limpo
        num_destino = f"whatsapp:+{tel_limpo}"
        msg = f"🏃‍♂️ *Fábio Assessoria*\n\nOlá *{nome_aluno}*! Seu treino: *{treino_nome}*, {km}km em {tempo}min. 🚀"
        client.messages.create(body=msg, from_=num_origem, to=num_destino)
        return True
    except: return False

# --- LÓGICA ANTI-F5 ---
if "logado" not in st.session_state: st.session_state.logado = False

query_params = st.query_params
if "user_mail" in query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", query_params["user_mail"]).execute()
    if u.data:
        st.session_state.logado = True
        st.session_state.user_info = u.data[0]

# =================================================================
# 🔑 LOGIN E CADASTRO
# =================================================================
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
        with tab_cadastro:
            with st.form("cad"):
                n_c = st.text_input("Nome")
                e_c = st.text_input("E-mail")
                t_c = st.text_input("WhatsApp (+55...)")
                s_c = st.text_input("Senha", type="password")
                if st.form_submit_button("Cadastrar"):
                    supabase.table("usuarios_app").insert({"nome": n_c, "email": e_c, "telefone": t_c, "senha": hash_senha(s_c), "status_pagamento": False, "data_vencimento": str(datetime.now().date())}).execute()
                    st.success("Cadastrado! Use a aba Entrar.")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if st.button("🧪 Sincronizar e Notificar", use_container_width=True):
        sucesso = enviar_whatsapp_real(user['nome'], user.get('telefone',''), "Treino v1", "10", "60")
        if sucesso: st.toast("✅ WhatsApp enviado!")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.query_params.clear()
        st.rerun()

# 👨‍🏫 PAINEL ADMIN
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            c_i, c_b = st.columns([3, 1])
            c_i.markdown(f"**Aluno:** {aluno['nome']} ({'✅' if aluno['status_pagamento'] else '❌'})")
            c_i.write(f"Vencimento: {formatar_data_br(aluno['data_vencimento'])}")
            if c_b.button("Liberar/Bloquear", key=aluno['id']):
                supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                st.rerun()

# 🚀 DASHBOARD CLIENTE (v1 Original)
else:
    st.title("🚀 Painel de Treino")
    pago = user.get('status_pagamento', False)
    c1, c2 = st.columns(2)
    c1.info(f"📅 **Vencimento:** {formatar_data_br(user.get('data_vencimento'))}")
    c2.markdown(f"**Status:** {'✅ ATIVO' if pago else '❌ PENDENTE'}")

    if not pago:
        with st.expander("💳 QR Code Pagamento", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.code(chave_pix_visivel)
        st.stop()

    # DADOS E GRÁFICOS
    df = pd.DataFrame([
        {"Data": "24/01", "Treino": "Rodagem", "Km": 10, "Tempo": 60, "FC": 145},
        {"Data": "26/01", "Treino": "Trote", "Km": 5, "Tempo": 35, "FC": 0},
        {"Data": "27/01", "Treino": "Longo", "Km": 15, "Tempo": 95, "FC": 138},
    ])
    df['FC_Final'] = df['FC'].apply(lambda x: 130 if x <= 0 else x)
    df['TRIMP'] = df['Tempo'] * (df['FC_Final'] / 100)

    st.subheader("📋 Planilha")
    st.dataframe(df[['Data', 'Treino', 'Km', 'Tempo', 'FC_Final']], use_container_width=True, hide_index=True)

    g1, g2 = st.columns(2)
    with g1: st.plotly_chart(px.bar(df, x='Data', y='TRIMP', title="TRIMP"), use_container_width=True)
    with g2: 
        fig = px.line(df, x='Data', y='FC_Final', title="FC Média", markers=True)
        fig.add_hline(y=130, line_dash="dash")
        st.plotly_chart(fig, use_container_width=True)
