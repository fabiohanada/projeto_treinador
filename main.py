import streamlit as st
import pandas as pd
import requests
from supabase import create_client
from datetime import datetime, timedelta

# Módulos originais
from modules.ui import aplicar_estilo_css, exibir_logo_rodape, estilizar_botoes
from modules.views import renderizar_tela_login, renderizar_tela_admin, renderizar_tela_bloqueio_financeiro

# 1. CONFIGURAÇÕES
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.stop()

aplicar_estilo_css()
estilizar_botoes()

# 2. FUNÇÃO DE SINCRONIZAÇÃO
def processar_sincronizacao(auth_code, user_id):
    try:
        response = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                'client_id': st.secrets["STRAVA_CLIENT_ID"],
                'client_secret': st.secrets["STRAVA_CLIENT_SECRET"],
                'code': auth_code,
                'grant_type': 'authorization_code'
            }
        ).json()
        
        token = response.get('access_token')
        if token:
            headers = {'Authorization': f'Bearer {token}'}
            atividades = requests.get("https://www.strava.com/api/v3/athlete/activities", 
                                      headers=headers, params={'per_page': 100}).json()
            
            if isinstance(atividades, dict) and 'message' in atividades:
                return False

            for act in atividades:
                if act['type'] in ['Run', 'VirtualRun', 'TrailRun']:
                    dist = act['distance'] / 1000
                    dur_minutos = act['moving_time'] / 60
                    
                    trimp_calc = int(dur_minutos * 1.5)
                    duracao_int = int(dur_minutos)
                    
                    dados = {
                        "id_atleta": user_id,
                        "strava_id": act['id'],
                        "tipo_esporte": act['type'],
                        "distancia": dist,
                        "duracao": duracao_int,
                        "data_treino": act['start_date_local'][:10],
                        "trimp_score": trimp_calc
                    }
                    supabase.table("atividades_fisicas").upsert(dados).execute()
            return True
        return False
    except:
        return False

# 3. GESTÃO DE SESSÃO
if "logado" not in st.session_state:
    st.session_state.logado = False

q_params = st.query_params
auth_code = q_params.get("code")
state_id = q_params.get("state")
session_id = q_params.get("session_id")

target_id = state_id or session_id

if not st.session_state.logado and target_id:
    res = supabase.table("usuarios_app").select("*").eq("id", target_id).execute()
    if res.data:
        st.session_state.user_info = res.data[0]
        st.session_state.logado = True
        
        if auth_code:
            with st.spinner("Sincronizando..."):
                processar_sincronizacao(auth_code, target_id)
            st.query_params.clear()
            st.query_params["session_id"] = target_id
            st.rerun()

# 4. ROTEAMENTO DE TELAS
if not st.session_state.logado:
    renderizar_tela_login(supabase)
else:
    user = st.session_state.user_info
    
    # ADMIN
    if user.get('is_admin'):
        with st.sidebar:
            st.markdown(f"### Fábio Assessoria")
            st.write(f"👤 **{user['nome']}**")
            st.markdown("---")
            if st.button("Sair"):
                st.session_state.clear()
                st.query_params.clear()
                st.rerun()
        renderizar_tela_admin(supabase)

    # PAGAMENTO / BLOQUEIO
    elif user.get('bloqueado') or user.get('status_pagamento') == False:
        with st.sidebar:
            st.write(f"👤 **{user['nome']}**")
            if st.button("Sair"):
                st.session_state.clear()
                st.query_params.clear()
                st.rerun()
        renderizar_tela_bloqueio_financeiro()
        
    # ALUNO ATIVO
    else:
        with st.sidebar:
            st.markdown(f"### Fábio Assessoria")
            st.write(f"👤 **{user['nome']}**")
            
            vencimento = user.get('data_vencimento')
            if vencimento:
                try:
                    data_fmt = datetime.strptime(str(vencimento), '%Y-%m-%d').strftime('%d/%m/%Y')
                    st.info(f"📅 Vencimento: **{data_fmt}**")
                except: pass

            client_id = st.secrets["STRAVA_CLIENT_ID"]
            redirect = "http://localhost:8501" 
            link = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect}&approval_prompt=force&scope=read,activity:read_all&state={user['id']}"
            
            st.markdown(f'''<a href="{link}" target="_self"><button style="background-color:#FC4C02;color:white;border:none;padding:10px;width:100%;border-radius:4px;font-weight:bold;cursor:pointer;">Conectar Strava</button></a>''', unsafe_allow_html=True)
            
            st.markdown("---")
            if st.button("Sair", type="secondary", width='stretch'):
                st.session_state.clear()
                st.query_params.clear()
                st.rerun()

        # CONTEÚDO
        st.title(f"Olá, {user['nome'].split()[0]}!")
        
        res_treinos = supabase.table("atividades_fisicas").select("*").eq("id_atleta", user['id']).order("data_treino", desc=True).execute()
        
        if res_treinos.data:
            df = pd.DataFrame(res_treinos.data)
            
            # Cards
            c1, c2 = st.columns(2)
            c1.metric("Treinos Realizados", len(df))
            km_total_fmt = f"{df['distancia'].sum():.1f}".replace('.', ',')
            c2.metric("Km Total", f"{km_total_fmt} km")
            
            # --- FORMATAÇÃO DA TABELA ---
            df_tabela = df.sort_values(by='data_treino', ascending=False).head(10).copy()
            
            # Formatação de Texto
            df_tabela['data_treino'] = pd.to_datetime(df_tabela['data_treino'])
            df_tabela['Data do Treino'] = df_tabela['data_treino'].dt.strftime('%d-%m-%y')
            
            def formatar_distancia(val):
                return f"{val:.2f}".replace('.', ',') + " km"
            df_tabela['Distância'] = df_tabela['distancia'].apply(formatar_distancia)
            
            def formatar_duracao(minutos):
                horas = int(minutos // 60)
                mins = int(minutos % 60)
                return f"{horas:02d}:{mins:02d}"
            df_tabela['Duração'] = df_tabela['duracao'].apply(formatar_duracao)
            
            df_tabela['Tipo de Esporte'] = df_tabela['tipo_esporte']
            df_tabela['Trimp'] = df_tabela['trimp_score']
            
            colunas_finais = ['Data do Treino', 'Distância', 'Duração', 'Tipo de Esporte', 'Trimp']
            
            # --- ESTILO CENTRALIZADO ---
            # Aqui aplicamos o CSS interno do Pandas para forçar o centro
            st_tabela = df_tabela[colunas_finais].style.set_properties(**{
                'text-align': 'center'
            }).set_table_styles([
                {'selector': 'th', 'props': [('text-align', 'center')]}
            ])

            st.markdown("### Últimas 10 Atividades")
            st.dataframe(
                st_tabela,
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Nenhum treino encontrado. Clique no botão lateral para conectar.")

    exibir_logo_rodape()