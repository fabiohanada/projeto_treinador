import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from supabase import create_client
from datetime import datetime, timedelta
import math 
import threading
import time

# Importação dos módulos customizados
from modules.ui import aplicar_estilo_css, exibir_logo_rodape, estilizar_botoes
from modules.views import renderizar_tela_login, renderizar_tela_admin, renderizar_tela_bloqueio_financeiro, enviar_notificacao_treino, renderizar_edicao_perfil

# Importação da sua função de processamento de fila
try:
    from processar_fila import processar_novos_treinos as processar_fila_treinos
except ImportError:
    st.error("Arquivo processar_fila.py não encontrado ou função ausente!")

# ============================================================================
# 1. CONFIGURAÇÕES E CONEXÃO
# ============================================================================
st.set_page_config(page_title="Zaptreino - Professor Hanada", layout="wide", page_icon="🏃‍♂️")

supabase_client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

query_params = st.query_params
if "code" in query_params:
    strava_code = query_params["code"]
    with st.spinner("Finalizando conexão..."):
        try:
            res = requests.post("https://www.strava.com/oauth/token", data={
                'client_id': st.secrets["STRAVA_CLIENT_ID"],
                'client_secret': st.secrets["STRAVA_CLIENT_SECRET"],
                'code': strava_code,
                'grant_type': 'authorization_code'
            }).json()

            if 'access_token' in res:
                if "user_info" in st.session_state:
                    u_id = st.session_state.user_info['id']
                    dados_auth = {
                        "user_id": u_id,
                        "access_token": res['access_token'],
                        "refresh_token": res['refresh_token'],
                        "expires_at": res['expires_at']
                    }
                    supabase_client.table("auth_strava").upsert(dados_auth).execute()
                    
                    from processar_fila import processar_novos_treinos
                    processar_novos_treinos(u_id, origem_botao=True)
                    
                    st.success("✅ Conectado com sucesso!")
                    st.query_params.clear() 
                    time.sleep(1)
                    st.rerun()
        except Exception as e:
            st.error(f"Erro ao processar retorno do Strava: {e}")

try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

aplicar_estilo_css()
estilizar_botoes()

# ============================================================================
# 2. SERVIÇO VIGILANTE (BACKGROUND)
# ============================================================================
def servico_vigilante_5min():
    while True:
        try:
            processar_fila_treinos() 
            print(f"✅ Vigilante: Ciclo silencioso concluído {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"❌ Erro no Vigilante: {e}")
        time.sleep(300) # 5 minutos

if not hasattr(st, "vigilante_ativo"):
    t = threading.Thread(target=servico_vigilante_5min, daemon=True)
    t.start()
    st.vigilante_ativo = True

# ============================================================================
# 3. GESTÃO DE SESSÃO
# ============================================================================
if "logado" not in st.session_state:
    st.session_state.logado = False

params = st.query_params
target_id = params.get("state") or params.get("session_id")
auth_code = params.get("code") 

if not st.session_state.logado and target_id:
    res = supabase.table("usuarios_app").select("*").eq("id", target_id).execute()
    if res.data:
        st.session_state.user_info = res.data[0]
        st.session_state.logado = True
        
        if auth_code:
            try:
                response = requests.post("https://www.strava.com/api/v3/oauth/token",
                    data={
                        'client_id': st.secrets["STRAVA_CLIENT_ID"],
                        'client_secret': st.secrets["STRAVA_CLIENT_SECRET"],
                        'code': auth_code,
                        'grant_type': 'authorization_code'
                    }).json()

                if 'access_token' in response:
                    supabase.table("auth_strava").upsert({
                        "user_id": target_id,
                        "athlete_id": response.get('athlete', {}).get('id'),
                        "access_token": response['access_token'],
                        "refresh_token": response.get('refresh_token'),
                        "expires_at": response.get('expires_at')
                    }).execute()
                    processar_fila_treinos(target_id)
            except Exception as e:
                print(f"Erro no OAuth Strava: {e}")

        st.query_params.clear()
        st.query_params["session_id"] = target_id
        st.rerun()

# ============================================================================
# 4. GRÁFICOS
# ============================================================================
def gerar_grafico_analise(df, titulo, dias=7):
    df_temp = df.copy()
    df_temp['data_treino'] = pd.to_datetime(df_temp['data_treino']).dt.tz_localize(None)
    hoje = datetime.now().replace(hour=23, minute=59, second=59)
    df_filtrado = df_temp[df_temp['data_treino'] >= (hoje - timedelta(days=dias))].sort_values('data_treino')
    if df_filtrado.empty: return None
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df_filtrado['data_treino'], y=df_filtrado['distancia'], name="Km", marker_color='lightgrey', opacity=0.5), secondary_y=True)
    fig.add_trace(go.Scatter(x=df_filtrado['data_treino'], y=df_filtrado['trimp_score'], name="Carga", mode='lines+markers', line=dict(color='#FC4C02', width=3)), secondary_y=False)
    fig.update_layout(template="plotly_white", height=350, margin=dict(l=10, r=10, t=50, b=10), showlegend=False, title=titulo)
    return fig

# ============================================================================
# 5. ROTEAMENTO DE TELAS
# ============================================================================
if not st.session_state.logado:
    renderizar_tela_login(supabase)
else:
    user = st.session_state.user_info
    
    with st.sidebar:
        st.markdown(f"### DataPace\n👤 **{user['nome']}**")
        if not user.get('bloqueado'):
            renderizar_edicao_perfil(supabase, user)
            st.markdown("---")
            url_strava = f"https://www.strava.com/oauth/authorize?client_id={st.secrets['STRAVA_CLIENT_ID']}&response_type=code&redirect_uri={st.secrets['STRAVA_REDIRECT_URI']}&approval_prompt=force&scope=read,activity:read_all&state={user['id']}"
            st.markdown(f'<a href="{url_strava}" target="_self"><button style="background-color:#FC4C02;color:white;border:none;padding:10px;width:100%;border-radius:4px;font-weight:bold;cursor:pointer;">Connect Strava</button></a>', unsafe_allow_html=True)
        
        st.markdown("---")
        if st.button("Sair da Conta", use_container_width=True):
            st.session_state.clear() 
            st.query_params.clear() 
            st.rerun()

    if user.get('is_admin'):
        renderizar_tela_admin(supabase)
    elif user.get('bloqueado'):
        renderizar_tela_bloqueio_financeiro()
    else:
        # TELA DO ALUNO
        if 'sync_inicial' not in st.session_state:
            with st.spinner("Sincronizando seus treinos agora..."):
                processar_fila_treinos(user['id'], origem_botao=True)
                st.session_state['sync_inicial'] = True

        st.title(f"E aí, {user['nome'].split()[0]}! ⚡")
        
        # 🚀 BUSCA ATUALIZADA: Incluindo trimp_semanal e trimp_mensal
        res_t = supabase.table("atividades_fisicas").select(
            "data_treino, name, distancia, duracao, trimp_score, trimp_semanal, trimp_mensal"
        ).eq("id_atleta", user['id']).order("data_treino", desc=True).execute()
        
        if res_t.data:
            df = pd.DataFrame(res_t.data)
            df['duracao_formatada'] = df['duracao'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}" if pd.notna(x) else "00:00")
            
            # Métricas de topo (Resumo)
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Treinos", len(df))
            m2.metric("Km Acumulados", f"{df['distancia'].sum():.1f}")
            m3.metric("Carga Média", f"{int(df['trimp_score'].mean())}")
            
            # 🚀 TABELA FINAL ATUALIZADA COM AS DUAS NOVAS COLUNAS
            st.dataframe(df.head(10), 
                         use_container_width=True, 
                         hide_index=True,
                         column_order=("data_treino", "name", "distancia", "duracao_formatada", "trimp_score", "trimp_semanal", "trimp_mensal"),
                         column_config={
                             "data_treino": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                             "name": "Atividade",
                             "distancia": st.column_config.NumberColumn("Km", format="%.2f"),
                             "duracao_formatada": "Duração",
                             "trimp_score": "Carga (TRIMP)",
                             "trimp_semanal": "Carga (7 dias)",
                             "trimp_mensal": "Carga (30 dias)"
                         })

            c1, c2 = st.columns(2)
            g1 = gerar_grafico_analise(df, "Últimos 30 dias", 30)
            g2 = gerar_grafico_analise(df, "Evolução Anual", 365)
            if g1: c1.plotly_chart(g1, use_container_width=True)
            if g2: c2.plotly_chart(g2, use_container_width=True)
        else:
            st.info("Nenhum treino encontrado. Conecte seu Strava!")

exibir_logo_rodape()