import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client

# ==========================================
# VERSÃO: v5.6 (RODAPÉ EM SVG - NÃO QUEBRA)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v5.6", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
except Exception as e:
    st.error("Erro nas Secrets.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

# --- LOGIN / SESSÃO ---
if "logado" not in st.session_state: st.session_state.logado = False

# TELA DE ACESSO
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
                n_telefone = st.text_input("Celular / WhatsApp") # CAMPO TELEFONE
                n_senha = st.text_input("Crie uma Senha", type="password")
                aceite = st.checkbox("Li e aceito os Termos de Uso e LGPD.")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    if not aceite: st.error("Aceite os termos.")
                    elif n_nome and n_email and n_senha:
                        try:
                            payload = {"nome": n_nome, "email": n_email, "telefone": n_telefone, "senha": hash_senha(n_senha), "status_pagamento": False}
                            supabase.table("usuarios_app").insert(payload).execute()
                            st.success("Cadastrado! Peça liberação ao Fábio.")
                        except: st.error("Erro no cadastro (e-mail já existe?).")
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

# --- CONTEÚDO ADMIN / ALUNO ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1.5, 1.5])
            with c1: 
                st.write(f"**{aluno['nome']}**")
                if aluno.get('telefone'): st.caption(f"📞 {aluno['telefone']}")
            with c2: nova_dt = st.date_input("Vencimento", value=date.today(), key=f"dt_{aluno['id']}")
            with c3:
                if st.button("💾 Salvar", key=f"sv_{aluno['id']}"):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt), "status_pagamento": True}).eq("id", aluno['id']).execute()
                    st.rerun()
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento'):
        st.error("⚠️ Acesso pendente de renovação.")
        st.stop()
    
    # Gráficos de exemplo (seu layout original)
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df, x='data', y='distancia', color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with c2: st.plotly_chart(px.line(df, x='data', y='fc_media'), use_container_width=True)

# --- RODAPÉ OFICIAL (DESENHADO EM SVG - NÃO QUEBRA NUNCA) ---
st.markdown("---")
# O código abaixo é o desenho oficial da logo 'Powered by Strava'
strava_logo_svg = """
<div style="display: flex; justify-content: flex-end; padding: 20px;">
    <svg width="160" height="30" viewBox="0 0 162 25" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M14.017 6.094l-4.47 8.923h8.941l-4.471-8.923z" fill="#FC4C02"/>
        <path d="M5.337 13.14l-2.618 5.228h5.236l-2.618-5.228z" fill="#FC4C02"/>
        <path d="M32.85 10.38c0 1.25-.33 2.27-1 3.06-.66.79-1.58 1.18-2.76 1.18h-2.1v4.44h-1.85V6.74h3.95c1.18 0 2.1.39 2.76 1.18.67.79 1 1.81 1 3.06zm-1.85 0c0-.85-.18-1.5-.54-1.95-.36-.45-.89-.68-1.58-.68h-1.9v5.26h1.9c.69 0 1.22-.23 1.58-.68.36-.45.54-1.1.54-1.95zM40.92 13.91c0 1.58-.45 2.82-1.35 3.73-.9.91-2.12 1.36-3.66 1.36-1.54 0-2.76-.45-3.66-1.36-.9-.91-1.35-2.15-1.35-3.73 0-1.59.45-2.83 1.35-3.73.9-.9 2.12-1.35 3.66-1.35 1.54 0 2.76.45 3.66 1.35.9.9 1.35 2.14 1.35 3.73zm-1.91 0c0-1.12-.26-1.99-.78-2.62-.52-.63-1.29-.94-2.32-.94-1.03 0-1.8.31-2.32.94-.52.63-.78 1.5-.78 2.62 0 1.11.26 1.98.78 2.62.52.63 1.29.95 2.32.95 1.03 0 1.8-.32 2.32-.95.52-.64.78-1.51.78-2.62zM52.01 6.74l-2.15 8.32-2.35-8.32h-1.87l-2.34 8.32-2.16-8.32h-1.93l3.07 11.8h2l2.36-8.08 2.37 8.08h2l3.07-11.8h-2.07zM60.1 11.66c-.16-.27-.4-.48-.7-.64-.3-.16-.65-.24-1.04-.24-.59 0-1.04.18-1.34.54-.31.36-.46.85-.46 1.48v5.74h-1.85V9.4h1.74l.08 1.48c.24-.52.58-.93 1.01-1.22.43-.29.91-.44 1.44-.44.42 0 .8.06 1.12.18l-.5 1.76l.5-.1zM67.57 16.5c-.38.54-.88.97-1.49 1.28-.61.31-1.29.47-2.03.47-1.13 0-2.03-.35-2.71-1.06-.68-.7-1.02-1.63-1.02-2.78 0-1.16.33-2.1.98-2.8.65-.7 1.47-1.05 2.45-1.05.74 0 1.38.15 1.93.45.55.3 1.01.76 1.37 1.36l.1-1.3h1.74v11.8h-1.85v-6.37l.53-1.48zm-1.81-2.34c0-.64-.17-1.15-.5-1.51-.33-.36-.78-.54-1.34-.54-.57 0-1.03.2-1.36.6-.33.4-.5 1-.5 1.78 0 .76.16 1.35.49 1.74.33.39.78.59 1.37.59.54 0 .98-.18 1.33-.55.35-.37.51-.91.51-1.61v-.5zM76.53 14.65h-5.46c.07.72.3 1.28.69 1.68.39.4 1 .6 1.83.6.59 0 1.07-.11 1.44-.33.37-.22.68-.53.94-.92l1.45.82c-.44.7-.99 1.22-1.65 1.57-.66.35-1.46.52-2.4.52-1.51 0-2.69-.45-3.53-1.35-.84-.9-1.26-2.15-1.26-3.74 0-1.58.42-2.82 1.25-3.73.83-.91 1.96-1.36 3.39-1.36 1.36 0 2.43.43 3.2 1.29.77.86 1.15 2.05 1.15 3.57v.98l-1.04-.53zm-5.43-1.45h3.61c-.06-.63-.26-1.12-.59-1.46-.33-.34-.78-.51-1.35-.51-.57 0-1 .17-1.29.51-.29.34-.38.82-.38 1.46zM84.44 6.13v3.27l.08 1.48c.24-.52.58-.93 1.01-1.22.43-.29.91-.44 1.44-.44.97 0 1.71.32 2.22.95.51.63.77 1.55.77 2.76v5.61h-1.85v-5.43c0-.75-.16-1.31-.48-1.68-.32-.37-.78-.56-1.38-.56-.59 0-1.06.19-1.42.56-.36.37-.54.94-.54 1.71v5.4h-1.85V6.13h1.91zM97.31 18.54h-1.85v-1.16c-.34.45-.77.8-1.29 1.05-.52.25-1.11.37-1.77.37-1.13 0-2.02-.38-2.66-1.13-.64-.75-.96-1.78-.96-3.08 0-1.34.33-2.4 1-3.18.67-.78 1.58-1.17 2.72-1.17.65 0 1.21.13 1.68.39.47.26.89.62 1.26 1.09l.02-1.32h1.85v8.14zm-1.85-4.04c0-.85-.18-1.51-.54-1.98-.36-.47-.86-.71-1.5-.71-.62 0-1.11.23-1.46.68-.35.45-.52 1.13-.52 2.03 0 .86.17 1.52.51 1.99.34.47.84.71 1.51.71.65 0 1.16-.24 1.53-.72.37-.48.56-.1.56-1.01l-.09-1.01-.01.01z" fill="#000"/>
    </svg>
</div>
"""
st.markdown(strava_logo_svg, unsafe_allow_html=True)
