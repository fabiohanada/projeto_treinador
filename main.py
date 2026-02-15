import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from supabase import create_client
from datetime import datetime, timedelta

# Importação dos módulos customizados
from modules.ui import aplicar_estilo_css, exibir_logo_rodape, estilizar_botoes
from modules.views import renderizar_tela_login, renderizar_tela_admin, renderizar_tela_bloqueio_financeiro, enviar_notificacao_treino

# ============================================================================
# 1. CONFIGURAÇÕES DE PÁGINA E CONEXÃO
# ============================================================================
st.set_page_config(page_title="DataPace - Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro ao conectar ao Banco de Dados: {e}")
    st.stop()

aplicar_estilo_css()
estilizar_botoes()

# ============================================================================
# 2. LÓGICA DE SINCRONIZAÇÃO (STRAVA -> SUPABASE)
# ============================================================================
def processar_sincronizacao(auth_code, user_id):
    try:
        response = requests.post(
            "https://www.strava.com/api/v3/oauth/token",
            data={
                'client_id': st.secrets.get("STRAVA_CLIENT_ID"),
                'client_secret': st.secrets.get("STRAVA_CLIENT_SECRET"),
                'code': auth_code,
                'grant_type': 'authorization_code'
            }
        ).json()
        
        token = response.get('access_token')
        if token:
            headers = {'Authorization': f'Bearer {token}'}
            # Busca as últimas 5 atividades para garantir que não perdeu nada
            atividades = requests.get("https://www.strava.com/api/v3/athlete/activities", 
                                      headers=headers, params={'per_page': 5}).json()
            
            for act in atividades:
                if act['type'] in ['Run', 'VirtualRun', 'TrailRun', 'Ride', 'Walk']:
                    dist = act['distance'] / 1000
                    dur_minutos = act['moving_time'] / 60
                    # Cálculo de esforço TRIMP (Base v12.0)
                    trimp_calc = int(dur_minutos * 1.5)
                    
                    dados = {
                        "id_atleta": user_id,
                        "strava_id": str(act['id']),
                        "tipo_esporte": act['type'],
                        "distancia": dist,
                        "duracao": int(dur_minutos),
                        "data_treino": act['start_date_local'][:10],
                        "trimp_score": trimp_calc
                    }
                    # Upsert evita duplicidade se o usuário sincronizar duas vezes
                    supabase.table("atividades_fisicas").upsert(dados, on_conflict="strava_id").execute()
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

# Se houver retorno do Strava (auth_code) ou sessão ativa na URL
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
# 4. FUNÇÃO DE GRÁFICOS (ANALÍTICO)
# ============================================================================
def gerar_grafico_analise(df, titulo, dias=7):
    df_temp = df.copy()
    # Tratamento de Timezone para o Plotly não quebrar
    df_temp['data_treino'] = pd.to_datetime(df_temp['data_treino']).dt.tz_localize(None)
    
    hoje = datetime.now()
    data_inicio = hoje - timedelta(days=dias)
    df_filtrado = df_temp[df_temp['data_treino'] > data_inicio].copy()
    
    if df_filtrado.empty: return None
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    # Barras de Distância
    fig.add_trace(go.Bar(x=df_filtrado['data_treino'], y=df_filtrado['distancia'], 
                         name="Km", marker_color='lightgrey', opacity=0.5), secondary_y=True)
    # Linha de Esforço (TRIMP)
    fig.add_trace(go.Scatter(x=df_filtrado['data_treino'], y=df_filtrado['trimp_score'], 
                             name="TRIMP", mode='lines+markers', line=dict(color='#FC4C02', width=3)), secondary_y=False)
    
    fig.update_layout(title_text=titulo, template="plotly_white", hovermode="x unified", showlegend=False, height=400)
    fig.update_yaxes(title_text="Esforço", secondary_y=False)
    fig.update_yaxes(title_text="Km", secondary_y=True, showgrid=False)
    return fig

# ============================================================================
# 5. CONTROLE DE TELAS (ORDEM DE PRIORIDADE)
# ============================================================================

# TELA 1: LOGIN (Se não estiver logado)
if not st.session_state.logado:
    renderizar_tela_login(supabase)

else:
    user = st.session_state.user_info
    
    # --- BARRA LATERAL (SIDEBAR) ---
    with st.sidebar:
        st.markdown(f"### DataPace Analytics")
        st.write(f"👤 **{user['nome']}**")
        
        # Só habilita sincronização se o usuário não estiver bloqueado
        is_ativo = not user.get('bloqueado') and user.get('status_pagamento') != False
        if is_ativo:
            client_id = st.secrets.get('STRAVA_CLIENT_ID')
            redirect_uri = st.secrets.get("REDIRECT_URI")
            link_strava = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope=read,activity:read_all&state={user['id']}"
            
            st.markdown(f'''<a href="{link_strava}" target="_self"><button style="background-color:#FC4C02;color:white;border:none;padding:10px;width:100%;border-radius:4px;font-weight:bold;cursor:pointer;">🔄 Sincronizar Strava</button></a>''', unsafe_allow_html=True)

        st.markdown("---")
        if st.button("Sair da Conta", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    # TELA 2: PAINEL ADMIN (Se for administrador)
    if user.get('is_admin'):
        renderizar_tela_admin(supabase)
        
    # TELA 3: BLOQUEIO FINANCEIRO (Se estiver bloqueado ou sem pagamento)
    elif user.get('bloqueado') or user.get('status_pagamento') == False:
        renderizar_tela_bloqueio_financeiro()
        
    # TELA 4: DASHBOARD DO ALUNO (Fluxo normal)
    else:
        st.title(f"Olá, {user['nome'].split()[0]}! 🏃‍♂️")

        # Busca dados no Supabase
        res_treinos = supabase.table("atividades_fisicas").select("*").eq("id_atleta", user['id']).order("data_treino", desc=True).execute()
        
        if res_treinos.data:
            df = pd.DataFrame(res_treinos.data)
            df['data_treino'] = pd.to_datetime(df['data_treino']).dt.tz_localize(None)
            agora = datetime.now()

            # --- DISPARO AUTOMÁTICO WHATSAPP (PÓS-SINCRONIZAÇÃO) ---
            if st.session_state.get('just_synced'):
                ultimo = df.iloc[0]
                soma_7d = df[df['data_treino'] > (agora - timedelta(days=7))]['trimp_score'].sum()
                soma_30d = df[df['data_treino'] > (agora - timedelta(days=30))]['trimp_score'].sum()
                
                status_w = "Ideal ✅" if soma_7d < 600 else "Alto ⚠️"
                status_m = "Consistente ✅" if soma_30d > 1000 else "Baixo 📉"

                dados_zap = {
                    "distancia": f"{ultimo['distancia']:.2f} km",
                    "duracao": f"{int(ultimo['duracao'])} min",
                    "trimp_semanal": status_w,
                    "trimp_mensal": status_m
                }
                
                enviar_notificacao_treino(dados_zap, user['nome'], user.get('telefone'))
                st.session_state['just_synced'] = False
                st.toast("Notificação enviada ao WhatsApp!", icon="📲")

            # --- INTERFACE DE MÉTRICAS ---
            m1, m2, m3 = st.columns(3)
            m1.metric("Total de Treinos", len(df))
            m2.metric("Distância Total", f"{df['distancia'].sum():.1f} km")
            m3.metric("Média de Esforço", f"{int(df['trimp_score'].mean())} pts")
            
            st.markdown("### 📋 Histórico Recente")
            df_show = df.head(10).copy()
            df_show['Data'] = df_show['data_treino'].dt.strftime('%d/%m/%Y')
            st.dataframe(df_show[['Data', 'distancia', 'duracao', 'trimp_score']], 
                         use_container_width=True, hide_index=True)

            st.markdown("### 📊 Análise de Carga")
            col1, col2 = st.columns(2)
            fig1 = gerar_grafico_analise(df, "Volume vs Esforço (7 dias)", 7)
            fig2 = gerar_grafico_analise(df, "Consistência Mensal (30 dias)", 30)
            if fig1: col1.plotly_chart(fig1, use_container_width=True)
            if fig2: col2.plotly_chart(fig2, use_container_width=True)
            
        else:
            st.info("Bem-vindo! Sincronize seu Strava no menu lateral para carregar seus treinos.")

# ============================================================================
# 6. RODAPÉ JURÍDICO (APARECE EM TODAS AS TELAS)
# ============================================================================
exibir_logo_rodape()