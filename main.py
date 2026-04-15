import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from supabase import create_client
from datetime import datetime, timedelta
import math 

# Importação dos módulos customizados
from modules.ui import aplicar_estilo_css, exibir_logo_rodape, estilizar_botoes
from modules.views import renderizar_tela_login, renderizar_tela_admin, renderizar_tela_bloqueio_financeiro, enviar_notificacao_treino, renderizar_edicao_perfil

# ============================================================================
# 1. CONFIGURAÇÕES DE PÁGINA E CONEXÃO
# ============================================================================
st.set_page_config(page_title="Zaptreino - Conecte seu movimento", layout="wide", page_icon="🏃‍♂️")

try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro ao conectar ao Banco de Dados: {e}")
    st.stop()

aplicar_estilo_css()
estilizar_botoes()

# ============================================================================
# 2. CÉREBRO DO TREINADOR (LÓGICA DE TRIMP CIENTÍFICO)
# ============================================================================

def calcular_trimp_banister(duracao_min, fc_media, fc_max, fc_repouso=60):
    if not fc_media or fc_media <= 0:
        return int(duracao_min * 1.5) 
        
    if fc_max <= fc_repouso: fc_max = 190
    b = 1.92 
    reserva = (fc_media - fc_repouso) / (fc_max - fc_repouso)
    
    try:
        trimp = duracao_min * reserva * 0.64 * math.exp(b * reserva)
        return int(trimp)
    except:
        return int(duracao_min * 1.5)

def processar_sincronizacao(auth_code, user_id):
    try:
        user_data = supabase.table("usuarios_app").select("data_nascimento").eq("id", user_id).execute()
        fc_max_atleta = 190
        
        if user_data.data and user_data.data[0].get('data_nascimento'):
            try:
                ano_nasc = int(user_data.data[0]['data_nascimento'].split('-')[0])
                fc_max_atleta = 220 - (datetime.now().year - ano_nasc)
            except: pass
            
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
            dados_token = {
                "user_id": user_id,
                "athlete_id": response.get('athlete', {}).get('id'),
                "access_token": token,
                "refresh_token": response.get('refresh_token'),
                "expires_at": response.get('expires_at'),
                "updated_at": str(datetime.now())
            }
            supabase.table("auth_strava").upsert(dados_token).execute()
        
            headers = {'Authorization': f'Bearer {token}'}
            atividades = requests.get("https://www.strava.com/api/v3/athlete/activities", 
                                    headers=headers, params={'per_page': 5}).json()
            
            # --- NOVA LÓGICA: SÓ O ÚLTIMO TREINO ---
            if atividades:
                # Pegamos apenas a primeira atividade da lista (a mais recente)
                ultima_act = atividades[0]
                
                if ultima_act['type'] in ['Run', 'VirtualRun', 'TrailRun', 'Ride', 'Walk', 'WeightTraining', 'Workout']:
                    dist = round(ultima_act.get('distance', 0) / 1000, 2)
                    dur_minutos = int(ultima_act.get('moving_time', 0) / 60)
                    fc_media_treino = ultima_act.get('average_heartrate', 0)
                    trimp_real = calcular_trimp_banister(dur_minutos, fc_media_treino, fc_max_atleta)
                    
                    dados = {
                        "id_atleta": user_id,
                        "strava_id": str(ultima_act['id']),
                        "tipo_esporte": ultima_act['type'],
                        "distancia": dist,
                        "duracao": dur_minutos,
                        "data_treino": ultima_act['start_date_local'][:10],
                        "name": ultima_act.get('name', 'Treino'),
                        "trimp_score": trimp_real 
                    }
                    
                    # Salva no banco
                    res_db = supabase.table("atividades_fisicas").upsert(dados, on_conflict="strava_id").execute()
                    
                    # 🚀 ENVIA WHATSAPP APENAS DESTA ÚLTIMA ATIVIDADE
                    if res_db.data:
                        dados_zap = {
                            "distancia": f"{dist} km",
                            "duracao": f"{dur_minutos} min",
                            "trimp_semanal": f"{trimp_real} pts"
                        }
                        nome_atleta = st.session_state.user_info.get('nome', 'Atleta')
                        enviar_notificacao_treino(dados_zap, nome_atleta)

                # Processa as outras 4 atividades apenas para atualizar o banco (sem enviar Zap)
                for act in atividades[1:]:
                     if act['type'] in ['Run', 'VirtualRun', 'TrailRun', 'Ride', 'Walk', 'WeightTraining', 'Workout']:
                        dist_outros = round(act.get('distance', 0) / 1000, 2)
                        dur_outros = int(act.get('moving_time', 0) / 60)
                        trimp_outros = calcular_trimp_banister(dur_outros, act.get('average_heartrate', 0), fc_max_atleta)
                        
                        dados_outros = {
                            "id_atleta": user_id,
                            "strava_id": str(act['id']),
                            "tipo_esporte": act['type'],
                            "distancia": dist_outros,
                            "duracao": dur_outros,
                            "data_treino": act['start_date_local'][:10],
                            "name": act.get('name', 'Treino'),
                            "trimp_score": trimp_outros
                        }
                        supabase.table("atividades_fisicas").upsert(dados_outros, on_conflict="strava_id").execute()
            
            return True
        return False
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")
        return False

# ============================================================================
# 3. GESTÃO DE SESSÃO E ROTEAMENTO OAUTH
# ============================================================================
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
            if processar_sincronizacao(auth_code, target_id):
                st.session_state['just_synced'] = True
            st.query_params.clear()
            st.query_params["session_id"] = target_id
            st.rerun()

# ============================================================================
# 4. FUNÇÃO DE GRÁFICOS
# ============================================================================
def gerar_grafico_analise(df, titulo, dias=7):
    df_temp = df.copy()
    df_temp['data_treino'] = pd.to_datetime(df_temp['data_treino']).dt.tz_localize(None)
    
    hoje = datetime.now().replace(hour=23, minute=59, second=59)
    data_inicio = hoje - timedelta(days=dias)
    df_filtrado = df_temp[df_temp['data_treino'] >= data_inicio].sort_values('data_treino').copy()
    
    if df_filtrado.empty: return None
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(go.Bar(x=df_filtrado['data_treino'], y=df_filtrado['distancia'], 
                          name="Km", marker_color='lightgrey', opacity=0.5), secondary_y=True)
                          
    fig.add_trace(go.Scatter(x=df_filtrado['data_treino'], y=df_filtrado['trimp_score'], 
                               name="Carga (TRIMP)", mode='lines+markers', line=dict(color='#FC4C02', width=3)), secondary_y=False)
    
    fig.update_layout(title_text=titulo, template="plotly_white", hovermode="x unified", showlegend=False, height=400, margin=dict(l=10, r=10, t=50, b=10))
    fig.update_yaxes(title_text="Carga Interna (TRIMP)", secondary_y=False)
    fig.update_yaxes(title_text="Distância (Km)", secondary_y=True, showgrid=False)
    return fig

# ============================================================================
# 5. CONTROLE DE TELAS
# ============================================================================

if not st.session_state.logado:
    renderizar_tela_login(supabase)
else:
    user = st.session_state.user_info
    
    with st.sidebar:
        st.markdown(f"### DataPace Analytics")
        st.write(f"👤 **{user['nome']}**")
        
        is_ativo = not user.get('bloqueado') and user.get('status_pagamento') != False
        if is_ativo:
            renderizar_edicao_perfil(supabase, user)
            st.markdown("---") 
            try:
                client_id = st.secrets["STRAVA_CLIENT_ID"]
                redirect_uri = st.secrets["STRAVA_REDIRECT_URI"]
                link_strava = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope=read,activity:read_all&state={user['id']}"
                st.markdown(f'''<a href="{link_strava}" target="_self"><button style="background-color:#FC4C02;color:white;border:none;padding:10px;width:100%;border-radius:4px;font-weight:bold;cursor:pointer;">Connect Strava</button></a>''', unsafe_allow_html=True)
            except:
                st.error("Erro nas chaves do Strava.")
        
        st.markdown("---")
        if st.button("Sair da Conta", type="secondary", width='stretch'):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    if user.get('is_admin'):
        renderizar_tela_admin(supabase)
    elif user.get('bloqueado') or user.get('status_pagamento') == False:
        renderizar_tela_bloqueio_financeiro()
    else:
        # Layout do Aluno
        c1, c2 = st.columns([3, 1])
        with c1:
            st.title(f"Olá, {user['nome'].split()[0]}! 🏃‍♂️")
        with c2:
            if st.button("🔄 Atualizar Painel"):
                st.cache_data.clear()
                st.rerun()

        res_treinos = supabase.table("atividades_fisicas").select("*").eq("id_atleta", user['id']).order("data_treino", desc=True).execute()
        
        if res_treinos.data:
            df = pd.DataFrame(res_treinos.data)
            df['data_treino'] = pd.to_datetime(df['data_treino']).dt.tz_localize(None)
            
            if st.session_state.get('just_synced'):
                st.session_state['just_synced'] = False
                st.toast("Treinos sincronizados!", icon="📲")

            m1, m2, m3 = st.columns(3)
            m1.metric("Total de Treinos", len(df))
            m2.metric("Distância Total", f"{df['distancia'].sum():.1f} km")
            m3.metric("Carga Média", f"{int(df['trimp_score'].mean())} pts")
            
            # --- TABELA FORMATADA (ARREDONDAMENTOS) ---
            st.dataframe(
                df.head(10)[['data_treino', 'name', 'distancia', 'duracao', 'trimp_score']], 
                width='stretch',
                hide_index=True,
                column_config={
                    "data_treino": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "name": "Atividade",
                    "distancia": st.column_config.NumberColumn("Km", format="%.2f"),
                    "duracao": st.column_config.NumberColumn("Min", format="%d"),
                    "trimp_score": st.column_config.NumberColumn("TRIMP", format="%d"),
                }
            )

            st.markdown("### 📊 Análise de Evolução")
            col1, col2 = st.columns(2)
            fig1 = gerar_grafico_analise(df, "Volume vs Esforço (Último ano)", 365)
            fig2 = gerar_grafico_analise(df, "Consistência Histórica", 3650)
            
            if fig1: col1.plotly_chart(fig1, width='stretch')
            if fig2: col2.plotly_chart(fig2, width='stretch')
        else:
            st.info("Conecte seu Strava para ver seus treinos.")

exibir_logo_rodape()