import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from supabase import create_client
from datetime import datetime

from modules.ui import aplicar_estilo_css, exibir_logo_rodape, estilizar_botoes
from modules.views import renderizar_tela_login, renderizar_tela_admin, renderizar_tela_bloqueio_financeiro

# --- CONFIGURAÇÕES ---
VERSAO = "v9.7 (Estável)"
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
        
        if not user.get('is_admin'):
            vencimento = user.get('data_vencimento')
            if vencimento:
                try:
                    data_fmt = datetime.strptime(str(vencimento), '%Y-%m-%d').strftime('%d/%m/%Y')
                    st.info(f"📅 Vencimento: **{data_fmt}**")
                except:
                    st.write(f"📅 Vencimento: {vencimento}")
            else:
                st.write("📅 Vencimento: --/--/----")

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

    # --- ROTEAMENTO ---
    if user.get('is_admin') == True:
        renderizar_tela_admin(supabase)
        
    elif user.get('bloqueado') or not user.get('status_pagamento', True):
        renderizar_tela_bloqueio_financeiro()
        
    else:
        st.title(f"Olá, {user['nome']}! 🏃‍♂️")
        try:
            uid = user.get('id') or user.get('uuid')
            res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", uid).execute()
            
            if res.data:
                df = pd.DataFrame(res.data)
                
                # Gráficos (Histórico Completo)
                df['Data_Exibicao'] = pd.to_datetime(df['data_treino']).dt.strftime('%d/%m')
                c1, c2 = st.columns(2)
                with c1: st.plotly_chart(px.bar(df, x='Data_Exibicao', y='distancia'), width='stretch')
                with c2: st.plotly_chart(px.area(df, x='Data_Exibicao', y='trimp_score'), width='stretch')
                
                # --- TABELA DE TREINOS ---
                df_tab = df.copy()
                
                # 1. Ordenar (Recentes no topo)
                df_tab = df_tab.sort_values(by='data_treino', ascending=False)
                
                # 2. Limitar (Top 10)
                df_tab = df_tab.head(10)

                # 3. Formatar
                df_tab['Data do Treino'] = pd.to_datetime(df_tab['data_treino']).dt.strftime('%d-%m-%y')

                def fmt_dist(x): return f"{float(x):.2f}".replace('.', ',') + " km"
                df_tab['Distância'] = df_tab['distancia'].apply(fmt_dist)

                def fmt_duracao(minutos):
                    try:
                        m = int(minutos)
                        horas = m // 60
                        mins_rest = m % 60
                        return f"{horas:02d}:{mins_rest:02d}"
                    except: return minutos
                df_tab['Duração'] = df_tab['duracao'].apply(fmt_duracao)
                
                # 4. Renomear e Filtrar
                df_tab = df_tab.rename(columns={'tipo_esporte': 'Esporte', 'trimp_score': 'Trimp'})
                colunas_finais = ['Data do Treino', 'Distância', 'Duração', 'Esporte', 'Trimp']
                
                st.dataframe(df_tab[colunas_finais], hide_index=True, width='stretch')
        except: pass

    exibir_logo_rodape()