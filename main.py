import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
            
            for act in atividades:
                if act['type'] in ['Run', 'VirtualRun', 'TrailRun']:
                    dist = act['distance'] / 1000
                    dur_minutos = act['moving_time'] / 60
                    trimp_calc = int(dur_minutos * 1.5)
                    
                    dados = {
                        "id_atleta": user_id,
                        "strava_id": act['id'],
                        "tipo_esporte": act['type'],
                        "distancia": dist,
                        "duracao": int(dur_minutos),
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
target_id = q_params.get("state") or q_params.get("session_id")

if not st.session_state.logado and target_id:
    res = supabase.table("usuarios_app").select("*").eq("id", target_id).execute()
    if res.data:
        st.session_state.user_info = res.data[0]
        st.session_state.logado = True
        auth_code = q_params.get("code")
        if auth_code:
            processar_sincronizacao(auth_code, target_id)
            st.query_params.clear()
            st.query_params["session_id"] = target_id
            st.rerun()

# 4. FUNÇÃO GRÁFICOS
def gerar_grafico_analise(df, titulo, dias=7):
    hoje = datetime.now().date()
    data_inicio = hoje - timedelta(days=dias)
    df_filtrado = df[df['data_treino'].dt.date > data_inicio].copy()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df_filtrado['data_treino'], y=df_filtrado['distancia'], name="Km", marker_color='lightgrey', opacity=0.5), secondary_y=True)
    fig.add_trace(go.Scatter(x=df_filtrado['data_treino'], y=df_filtrado['trimp_score'], name="TRIMP", mode='lines+markers', line=dict(color='#FC4C02', width=3)), secondary_y=False)
    fig.add_hrect(y0=70, y1=140, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Ideal")
    fig.add_hrect(y0=180, y1=250, fillcolor="red", opacity=0.1, line_width=0, annotation_text="Sobrecarga")
    fig.update_layout(title_text=titulo, template="plotly_white", hovermode="x unified", showlegend=False, height=400)
    fig.update_yaxes(title_text="TRIMP", secondary_y=False, range=[0, 250])
    fig.update_yaxes(title_text="Km", secondary_y=True, showgrid=False)
    return fig

# 5. ROTEAMENTO E INTERFACE
if not st.session_state.logado:
    renderizar_tela_login(supabase)
else:
    user = st.session_state.user_info
    
    with st.sidebar:
        st.markdown(f"### Fábio Assessoria")
        st.write(f"👤 **{user['nome']}**")
        
        is_aluno_ativo = not user.get('is_admin') and not user.get('bloqueado') and user.get('status_pagamento') != False
        
        if is_aluno_ativo:
            vencimento = user.get('data_vencimento')
            if vencimento:
                try:
                    data_fmt = datetime.strptime(str(vencimento), '%Y-%m-%d').strftime('%d/%m/%Y')
                    st.info(f"📅 Vencimento: **{data_fmt}**")
                except: pass

            client_id = st.secrets['STRAVA_CLIENT_ID']
            redirect_uri = "http://localhost:8501" 
            link = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope=read,activity:read_all&state={user['id']}"
            
            st.markdown(f'''<a href="{link}" target="_self"><button style="background-color:#FC4C02;color:white;border:none;padding:10px;width:100%;border-radius:4px;font-weight:bold;cursor:pointer;">Conectar Strava</button></a>''', unsafe_allow_html=True)

        st.markdown("---")
        if st.button("Sair", type="secondary", width='stretch'):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    if user.get('is_admin'):
        renderizar_tela_admin(supabase)
        
    elif user.get('bloqueado') or user.get('status_pagamento') == False:
        renderizar_tela_bloqueio_financeiro()
        
    else:
        st.title(f"Olá, {user['nome'].split()[0]}! 🏃‍♂️")
        
        res_treinos = supabase.table("atividades_fisicas").select("*").eq("id_atleta", user['id']).order("data_treino", desc=True).execute()
        
        if res_treinos.data:
            df = pd.DataFrame(res_treinos.data)
            df['data_treino'] = pd.to_datetime(df['data_treino'])

            c1, c2 = st.columns(2)
            c1.metric("Treinos Realizados", len(df))
            c2.metric("Km Total", f"{df['distancia'].sum():.1f}".replace('.', ',') + " km")
            
            st.markdown("### Últimas 10 Atividades")
            df_tabela = df.head(10).copy()
            df_tabela['Data do Treino'] = df_tabela['data_treino'].dt.strftime('%d-%m-%y')
            df_tabela['Distância'] = df_tabela['distancia'].apply(lambda x: f"{x:.2f}".replace('.', ',') + " km")
            df_tabela['Duração'] = df_tabela['duracao'].apply(lambda x: f"{int(x//60):02d}:{int(x%60):02d}")
            
            st_tabela = df_tabela[['Data do Treino', 'Distância', 'Duração', 'tipo_esporte', 'trimp_score']].style.set_properties(**{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
            
            # CORRIGIDO AQUI: width='stretch' na Tabela
            st.dataframe(st_tabela, hide_index=True, width='stretch')

            st.markdown("---")
            col_graf1, col_graf2 = st.columns(2)
            with col_graf1:
                # CORRIGIDO AQUI: width='stretch' no Gráfico 1
                st.plotly_chart(gerar_grafico_analise(df, "Análise Semanal", dias=7), width='stretch')
            with col_graf2:
                # CORRIGIDO AQUI: width='stretch' no Gráfico 2
                st.plotly_chart(gerar_grafico_analise(df, "Análise Mensal", dias=30), width='stretch')
        else:
            st.info("Sincronize seus treinos para começar!")

    exibir_logo_rodape()