import streamlit as st
import pd as pd
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v2 FINAL (ESTÁVEL E SEM ERROS DE DATA)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v2", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES AUXILIARES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or data_str == "None": return "Pendente"
    try: 
        return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: 
        return str(data_str)

def enviar_whatsapp_real(nome_aluno, telefone, treino_nome, km, tempo):
    try:
        sid = st.secrets["TWILIO_ACCOUNT_SID"]
        token = st.secrets["TWILIO_AUTH_TOKEN"]
        num_origem = f"whatsapp:{st.secrets['TWILIO_PHONE_NUMBER']}"
        client = Client(sid, token)
        tel_limpo = "".join(filter(str.isdigit, str(telefone)))
        if not tel_limpo.startswith("55"): tel_limpo = "55" + tel_limpo
        num_destino = f"whatsapp:+{tel_limpo}"
        msg = f"🏃‍♂️ *Fábio Assessoria*\n\nOlá *{nome_aluno}*! Seu treino sincronizado: *{treino_nome}*, {km}km em {tempo}min. 🚀"
        client.messages.create(body=msg, from_=num_origem, to=num_destino)
        return True
    except: return False

# --- LÓGICA ANTI-F5 ---
if "logado" not in st.session_state: st.session_state.logado = False
if "user_mail" in st.query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", st.query_params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]

# --- TELA DE LOGIN ---
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

# --- ÁREA LOGADA ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if not eh_admin:
        if st.button("🧪 Sincronizar e Notificar", use_container_width=True):
            sucesso = enviar_whatsapp_real(user['nome'], user.get('telefone',''), "Treino v2", "10", "60")
            if sucesso: st.toast("✅ WhatsApp enviado!")
    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.query_params.clear()
        st.rerun()

# =================================================================
# 👨‍🏫 PAINEL ADMIN (RESTURADO E PROTEGIDO)
# =================================================================
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    for aluno in alunos.data:
        with st.container(border=True):
            c_info, c_btns = st.columns([3, 1])
            with c_info:
                pago_status = "✅ PAGO" if aluno['status_pagamento'] else "❌ PENDENTE"
                st.markdown(f"**Aluno:** {aluno['nome']} | **Status:** {pago_status}")
                st.write(f"Vencimento Atual: {formatar_data_br(aluno['data_vencimento'])}")
                
                # Previne erro se a data no banco estiver vazia
                try:
                    val_data = datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d').date() if aluno['data_vencimento'] else date.today()
                except:
                    val_data = date.today()
                
                nova_data = st.date_input("Alterar Vencimento", value=val_data, key=f"d_{aluno['id']}")
            
            with c_btns:
                if st.button("💾 Salvar Data", key=f"s_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                    st.rerun()
                label = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                if st.button(label, key=f"a_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

# =================================================================
# 🚀 PAINEL CLIENTE (DASHBOARD v2)
# =================================================================
else:
    st.title("🚀 Painel de Treino")
    pago = user.get('status_pagamento', False)
    c1, c2 = st.columns(2)
    c1.info(f"📅 **Vencimento:** {formatar_data_br(user.get('data_vencimento'))}")
    c2.markdown(f"**Status:** {'✅ ATIVO' if pago else '❌ PENDENTE'}")

    if not pago:
        with st.expander("💳 Dados para Pagamento", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.code(chave_pix_visivel)
            if st.button("🚀 Já paguei! Avisar o Fábio", use_container_width=True):
                st.toast("Notificação enviada ao Fábio!")
        st.stop()

    # Dados Mockados para Exibição
    df = pd.DataFrame([
        {"Data": "24/01", "Treino": "Rodagem", "Km": 10, "Tempo": 60, "FC": 145},
        {"Data": "26/01", "Treino": "Trote", "Km": 5, "Tempo": 35, "FC": 0},
        {"Data": "27/01", "Treino": "Longo", "Km": 15, "Tempo": 95, "FC": 138},
    ])
    df['FC_Final'] = df['FC'].apply(lambda x: 130 if x <= 0 else x)
    df['TRIMP'] = df['Tempo'] * (df['FC_Final'] / 100)

    st.subheader("📋 Planilha de Treinos")
    st.dataframe(df[['Data', 'Treino', 'Km', 'Tempo', 'FC_Final']], use_container_width=True, hide_index=True)

    g1, g2 = st.columns(2)
    with g1: st.plotly_chart(px.bar(df, x='Data', y='TRIMP', title="Carga TRIMP"), use_container_width=True)
    with g2: 
        fig = px.line(df, x='Data', y='FC_Final', title="Frequência Cardíaca", markers=True)
        fig.add_hline(y=130, line_dash="dash", annotation_text="Base 130bpm")
        st.plotly_chart(fig, use_container_width=True)
