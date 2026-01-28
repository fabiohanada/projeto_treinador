import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import hashlib, urllib.parse
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v1 (LAYOUT TRAVADO + TWILIO ATIVO)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- FUNÇÃO DE DISPARO REAL ---
def enviar_whatsapp_real(nome_aluno, telefone, treino_nome, km, tempo):
    try:
        # Usando as chaves que você forneceu
        sid = st.secrets["TWILIO_ACCOUNT_SID"]
        token = st.secrets["TWILIO_AUTH_TOKEN"]
        # Importante: para WhatsApp no Twilio, o número de origem deve ter o prefixo whatsapp:
        num_origem = f"whatsapp:{st.secrets['TWILIO_PHONE_NUMBER']}"
        
        client = Client(sid, token)
        
        msg = (
            f"🏃‍♂️ *Fábio Assessoria*\n\n"
            f"Olá *{nome_aluno}*! Seu treino foi sincronizado:\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 *{treino_nome}*\n"
            f"📏 Distância: {km} km\n"
            f"⏱️ Tempo: {tempo} min\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Bons km! 🚀"
        )
        
        # Garante que o destino tenha o prefixo correto
        num_destino = f"whatsapp:{telefone}"
        
        client.messages.create(body=msg, from_=num_origem, to=num_destino)
        return True
    except Exception as e:
        st.error(f"Erro no disparo: {e}")
        return False

# --- FUNÇÕES AUXILIARES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()
def formatar_data_br(data_str):
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

# =================================================================
# 🔑 LOGIN (v1)
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
                if st.form_submit_button("Acessar", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.rerun()
        with tab_cadastro:
            with st.form("cad"):
                n_c = st.text_input("Nome")
                e_c = st.text_input("E-mail")
                t_c = st.text_input("WhatsApp (Ex: +5511969603611)")
                s_c = st.text_input("Senha", type="password")
                if st.form_submit_button("Cadastrar"):
                    supabase.table("usuarios_app").insert({"nome": n_c, "email": e_c, "telefone": t_c, "senha": hash_senha(s_c), "status_pagamento": False, "data_vencimento": str(datetime.now().date())}).execute()
                    st.success("Sucesso!")
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA (v1)
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# Dados da Maria para o teste
df = pd.DataFrame([
    {"Data": "24/01", "Treino": "Rodagem", "Km": 10, "Tempo": 60, "FC": 145},
    {"Data": "27/01", "Treino": "Longo", "Km": 15, "Tempo": 95, "FC": 138},
])
df['FC_Final'] = df['FC'].apply(lambda x: 130 if x <= 0 else x)
df['TRIMP'] = df['Tempo'] * (df['FC_Final'] / 100)

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    st.divider()
    
    # O BOTÃO QUE VOCÊ PEDIU
    if st.button("🧪 Sincronizar e Notificar", use_container_width=True):
        ultimo = df.iloc[-1]
        # Pega o telefone direto do cadastro da Maria
        telefone_aluno = user.get('telefone', st.secrets["MY_PHONE_NUMBER"]) 
        sucesso = enviar_whatsapp_real(user['nome'], telefone_aluno, ultimo['Treino'], ultimo['Km'], ultimo['Tempo'])
        if sucesso: st.toast("✅ WhatsApp enviado para Maria!")

    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# --- LAYOUT DASHBOARD (v1 Restaurado) ---
st.title("🚀 Painel de Treino")
v_str = user.get('data_vencimento', "2000-01-01")
pago = user.get('status_pagamento', False)

c_v, c_s = st.columns(2)
c_v.info(f"📅 **Vencimento:** {formatar_data_br(v_str)}")
st_color = "green" if pago else "red"
c_s.markdown(f"**Status:** <span style='color:{st_color}; font-weight:bold;'>{'✅ ATIVO' if pago else '❌ PENDENTE'}</span>", unsafe_allow_html=True)

if not pago:
    st.warning("Aguardando Pagamento...")
    st.stop()

st.subheader("📋 Planilha de Treinos")
st.dataframe(df[['Data', 'Treino', 'Km', 'Tempo', 'FC_Final']], use_container_width=True, hide_index=True)

st.subheader("📊 Análise de Desempenho")
g1, g2 = st.columns(2)
with g1:
    st.plotly_chart(px.bar(df, x='Data', y='TRIMP', title="Carga TRIMP"), use_container_width=True)
with g2:
    fig_fc = px.line(df, x='Data', y='FC_Final', title="Frequência Cardíaca", markers=True)
    fig_fc.add_hline(y=130, line_dash="dash")
    st.plotly_chart(fig_fc, use_container_width=True)
