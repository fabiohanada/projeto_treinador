import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import time
from supabase import create_client

from modules.ui import aplicar_estilo_css, exibir_botao_strava_sidebar, exibir_logo_rodape, estilizar_botao_sincronizar
from modules.views import renderizar_tela_login, renderizar_tela_admin

# --- CONFIGURAÇÕES ---
VERSAO = "v8.9.7 (Final UI Fix)"
st.set_page_config(page_title=f"Fábio Assessoria {VERSAO}", layout="wide", page_icon="🏃‍♂️")

try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.stop()

aplicar_estilo_css()

def sincronizar_dados_strava(access_token, user_id):
    headers = {'Authorization': f"Bearer {access_token}"}
    try:
        r = requests.get("https://www.strava.com/api/v3/athlete/activities?per_page=200", headers=headers)
        if r.status_code == 200:
            atividades = r.json()
            novos_treinos = []
            for act in atividades:
                if act.get('type') in ['Run', 'VirtualRun']: 
                    novos_treinos.append({
                        'id_atleta': user_id,
                        'data_treino': act['start_date'],
                        'distancia': round(act['distance'] / 1000, 2),
                        'duracao': int(act['moving_time'] / 60),
                        'trimp_score': act.get('suffer_score', 0),
                        'tipo_esporte': act.get('type')
                    })
            if novos_treinos:
                supabase.table("atividades_fisicas").upsert(novos_treinos, on_conflict="id_atleta,data_treino").execute()
                return True, len(novos_treinos)
            return True, 0
        return False, f"Erro Strava: {r.status_code}"
    except Exception as e:
        return False, str(e)

# --- MOTOR DE AUTO-LOGIN ---
if "logado" not in st.session_state:
    st.session_state.logado = False

auth_code = st.query_params.get("code")
state_raw = st.query_params.get("state")

if auth_code and state_raw:
    with st.status("Processando...", expanded=True) as status:
        try:
            state_email = state_raw if isinstance(state_raw, str) else state_raw[0]
            state_email = state_email.strip().lower()
            
            res_user = supabase.table("usuarios_app").select("*").eq("email", state_email).execute()
            
            if res_user.data:
                user_data = res_user.data[0]
                st.session_state.user_info = user_data
                st.session_state.logado = True
                
                res_token = requests.post("https://www.strava.com/oauth/token", data={
                    'client_id': st.secrets["STRAVA_CLIENT_ID"],
                    'client_secret': st.secrets["STRAVA_CLIENT_SECRET"],
                    'code': auth_code,
                    'grant_type': 'authorization_code'
                })
                
                if res_token.status_code == 200:
                    tokens = res_token.json()
                    st.session_state['strava_access_token'] = tokens['access_token']
                    uid = user_data.get('id') or user_data.get('uuid') or user_data.get('id_usuario')
                    sincronizar_dados_strava(tokens['access_token'], uid)
                    status.update(label="Concluído!", state="complete")
                    time.sleep(1)
                    st.query_params.clear()
                    st.rerun()
                else:
                    status.update(label="Erro no Strava", state="error")
                    st.error("Falha ao obter token.")
            else:
                status.update(label="Usuário não encontrado", state="error")
        except Exception as e:
            status.update(label="Erro", state="error")
            st.error(f"Erro: {e}")
            if st.button("Recarregar"):
                st.rerun()
    st.stop()

# --- INTERFACE ---
if not st.session_state.logado:
    renderizar_tela_login(supabase)
else:
    user = st.session_state.user_info
    
    with st.sidebar:
        st.markdown(f"### Fábio Assessoria `{VERSAO}`")
        st.write(f"👤 **{user['nome']}**")
        st.markdown("---")
        
        if not user.get('is_admin'):
            st.write("**Sincronização:**")
            if 'strava_access_token' in st.session_state:
                # O CSS aqui pinta o primeiro botão de laranja e o resto reseta
                estilizar_botao_sincronizar()
                
                # Este é o PRIMEIRO botão -> Fica Laranja
                if st.button("Connect with Strava", width="stretch"):
                    uid = user.get('id') or user.get('uuid') or user.get('id_usuario')
                    s, q = sincronizar_dados_strava(st.session_state['strava_access_token'], uid)
                    if s: st.toast("Atualizado!", icon="🚀")
                    st.rerun()
            else:
                exibir_botao_strava_sidebar() 
            st.markdown("---")
        
        # Este é o SEGUNDO botão -> O CSS reseta para branco
        if st.button("Sair / Logoff", key="btn_logout", width="stretch"):
            st.session_state.clear()
            st.rerun()

    # --- DASHBOARD ---
    if user.get('is_admin', False):
        renderizar_tela_admin(supabase)
    else:
        st.title(f"Olá, {user['nome']}! 🏃‍♂️")
        try:
            uid = user.get('id') or user.get('uuid') or user.get('id_usuario')
            res = supabase.table("atividades_fisicas").select("*").eq("id_atleta", uid).order("data_treino", desc=False).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df = df.rename(columns={'data_treino':'Data', 'distancia':'Distância (Km)', 'trimp_score':'TRIMP', 'duracao':'Tempo (min)'})
                df['Data_Exibicao'] = pd.to_datetime(df['Data']).dt.strftime('%d/%m')
                c1, c2 = st.columns(2)
                with c1: st.plotly_chart(px.bar(df, x='Data_Exibicao', y='Distância (Km)'), width="stretch")
                with c2: st.plotly_chart(px.area(df, x='Data_Exibicao', y='TRIMP'), width="stretch")
                st.dataframe(df[['Data', 'Distância (Km)', 'Tempo (min)', 'TRIMP']], hide_index=True, width="stretch")
            else:
                st.info("Nenhuma atividade encontrada.")
        except:
            pass

    exibir_logo_rodape()