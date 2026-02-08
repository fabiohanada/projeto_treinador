import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from supabase import create_client

from modules.ui import aplicar_estilo_css, exibir_logo_rodape, estilizar_botoes
from modules.views import renderizar_tela_login, renderizar_tela_admin, renderizar_tela_bloqueio_financeiro

# --- CONFIGURAÇÕES ---
VERSAO = "v9.5 (Admin Restaurado)"
st.set_page_config(page_title=f"Fábio Assessoria {VERSAO}", layout="wide", page_icon="🏃‍♂️")

try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.stop()

aplicar_estilo_css()
estilizar_botoes()

# --- LÓGICA F5 ---
if "logado" not in st.session_state:
    st.session_state.logado = False

url_id = st.query_params.get("session_id")
if not st.session_state.logado and url_id:
    try:
        res = supabase.table("usuarios_app").select("*").eq("id", url_id).execute()
        if not res.data:
            res = supabase.table("usuarios_app").select("*").eq("uuid", url_id).execute()
        if res.data:
            st.session_state.user_info = res.data[0]
            st.session_state.logado = True
    except: pass

# --- INTERFACE ---
if not st.session_state.logado:
    renderizar_tela_login(supabase)
else:
    user = st.session_state.user_info
    
    with st.sidebar:
        st.markdown(f"### Fábio Assessoria")
        st.write(f"👤 **{user['nome']}**")
        
        # Menu apenas para Alunos (não Admin)
        if not user.get('is_admin'):
            if 'strava_access_token' in st.session_state:
                if st.button("Sincronizar Agora", type="primary", width='stretch'):
                    pass 
            else:
                client_id = st.secrets["STRAVA_CLIENT_ID"]
                redirect = "http://192.168.1.13:8501"
                link = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect}&approval_prompt=force&scope=read,activity:read_all&state={user['email']}"
                st.markdown(f'''<a href="{link}" target="_self"><button style="background-color:#FC4C02;color:white;border:none;padding:10px;width:100%;border-radius:4px;font-weight:bold;cursor:pointer;">Connect with Strava</button></a>''', unsafe_allow_html=True)
        
        st.markdown("---")
        if st.button("Sair / Logoff", type="secondary", width='stretch'):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    # --- ROTEAMENTO DE TELAS (CORRIGIDO) ---
    # 1. Se for Admin, MOSTRA O PAINEL ADMIN e para por aqui.
    if user.get('is_admin') == True:
        renderizar_tela_admin(supabase)
        
    # 2. Se for Aluno bloqueado, mostra bloqueio.
    elif user.get('bloqueado') or not user.get('pago', True):
        renderizar_tela_bloqueio_financeiro()
        
    # 3. Se for Aluno normal, mostra Dashboard.
    else:
        st.title(f"Olá, {user['nome']}! 🏃‍♂️")
        try:
            uid = user.get('id') or user.get('uuid')
            res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", uid).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df['Data_Exibicao'] = pd.to_datetime(df['data_treino']).dt.strftime('%d/%m')
                c1, c2 = st.columns(2)
                with c1: st.plotly_chart(px.bar(df, x='Data_Exibicao', y='distancia'), width='stretch')
                with c2: st.plotly_chart(px.area(df, x='Data_Exibicao', y='trimp_score'), width='stretch')
                st.dataframe(df, hide_index=True, width='stretch')
        except: pass

    exibir_logo_rodape()