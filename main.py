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
st.set_page_config(page_title="DataPace - Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

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
    """
    Calcula o TRIMP (Impulso de Treino) usando o método de Banister.
    Usa a FC Máxima real baseada na idade do aluno.
    """
    if not fc_media or fc_media <= 0:
        return int(duracao_min * 1.5) 
        
    if fc_max <= fc_repouso: fc_max = 190

    # Fator de ponderação (b) - Padrão masculino
    b = 1.92 
    
    reserva = (fc_media - fc_repouso) / (fc_max - fc_repouso)
    
    try:
        trimp = duracao_min * reserva * 0.64 * math.exp(b * reserva)
        return int(trimp)
    except:
        return int(duracao_min * 1.5)

def processar_sincronizacao(auth_code, user_id):
    try:
        # 1. BUSCA A IDADE DO ATLETA NO BANCO
        user_data = supabase.table("usuarios_app").select("data_nascimento").eq("id", user_id).execute()
        
        fc_max_atleta = 190 
        
        if user_data.data and user_data.data[0].get('data_nascimento'):
            nasc_str = user_data.data[0]['data_nascimento']
            try:
                ano_nasc = int(nasc_str.split('-')[0])
                ano_atual = datetime.now().year
                idade = ano_atual - ano_nasc
                fc_max_atleta = 220 - idade
            except:
                pass 
            
        # 2. TROCA O CÓDIGO PELO TOKEN DO STRAVA
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
        
        # 3. IMPORTA E PROCESSA OS TREINOS
        if token:
            headers = {'Authorization': f'Bearer {token}'}
            atividades = requests.get("https://www.strava.com/api/v3/athlete/activities", 
                                    headers=headers, params={'per_page': 10}).json()
            
            for act in atividades:
                if act['type'] in ['Run', 'VirtualRun', 'TrailRun', 'Ride', 'Walk', 'WeightTraining', 'Workout']:
                    
                    dist = act.get('distance', 0) / 1000
                    dur_minutos = act.get('moving_time', 0) / 60
                    fc_media_treino = act.get('average_heartrate', 0)
                    
                    # CÁLCULO CIENTÍFICO
                    trimp_real = calcular_trimp_banister(dur_minutos, fc_media_treino, fc_max_atleta)
                    
                    dados = {
                        "id_atleta": user_id,
                        "strava_id": str(act['id']),
                        "tipo_esporte": act['type'],
                        "distancia": dist,
                        "duracao": int(dur_minutos),
                        "data_treino": act['start_date_local'][:10],
                        "name": act.get('name', 'Treino sem nome'),
                        "trimp_score": trimp_real 
                    }
                    
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
    df_temp['data_treino'] = pd.to_datetime(df_temp['data_treino']).dt.tz_localize(None)
    
    hoje = datetime.now()
    data_inicio = hoje - timedelta(days=dias)
    df_filtrado = df_temp[df_temp['data_treino'] > data_inicio].copy()
    
    if df_filtrado.empty: return None
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(go.Bar(x=df_filtrado['data_treino'], y=df_filtrado['distancia'], 
                          name="Km", marker_color='lightgrey', opacity=0.5), secondary_y=True)
                          
    fig.add_trace(go.Scatter(x=df_filtrado['data_treino'], y=df_filtrado['trimp_score'], 
                             name="Carga (TRIMP)", mode='lines+markers', line=dict(color='#FC4C02', width=3)), secondary_y=False)
    
    fig.update_layout(title_text=titulo, template="plotly_white", hovermode="x unified", showlegend=False, height=400)
    fig.update_yaxes(title_text="Carga Interna (TRIMP)", secondary_y=False)
    fig.update_yaxes(title_text="Distância (Km)", secondary_y=True, showgrid=False)
    return fig

# ============================================================================
# 5. CONTROLE DE TELAS (ORDEM DE PRIORIDADE)
# ============================================================================

# TELA 1: LOGIN
if not st.session_state.logado:
    renderizar_tela_login(supabase)

else:
    user = st.session_state.user_info
    
    # --- BARRA LATERAL (SIDEBAR) ---
    with st.sidebar:
        st.markdown(f"### DataPace Analytics")
        st.write(f"👤 **{user['nome']}**")
        
        is_ativo = not user.get('bloqueado') and user.get('status_pagamento') != False
        if is_ativo:
            
            renderizar_edicao_perfil(supabase, user)
            st.markdown("---") 

            client_id = st.secrets.get('STRAVA_CLIENT_ID')
            redirect_uri = st.secrets.get("REDIRECT_URI")
            link_strava = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope=read,activity:read_all&state={user['id']}"
            
            st.markdown(f'''<a href="{link_strava}" target="_self"><button style="background-color:#FC4C02;color:white;border:none;padding:10px;width:100%;border-radius:4px;font-weight:bold;cursor:pointer;">🔗 Reconectar Strava</button></a>''', unsafe_allow_html=True)
            st.caption("Use apenas se precisar revalidar a conta.")

        st.markdown("---")
        # Mantive use_container_width=True aqui pois botões ainda usam esse padrão em muitas versões
        if st.button("Sair da Conta", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    # TELA 2: PAINEL ADMIN
    if user.get('is_admin'):
        renderizar_tela_admin(supabase)
        
    # TELA 3: BLOQUEIO FINANCEIRO
    elif user.get('bloqueado') or user.get('status_pagamento') == False:
        renderizar_tela_bloqueio_financeiro()
        
    # TELA 4: DASHBOARD DO ALUNO (Fluxo normal)
    else:
        c1, c2 = st.columns([3, 1])
        with c1:
            primeiro_nome = user['nome'].split()[0]
            st.title(f"Olá, {primeiro_nome}! 🏃‍♂️")
        with c2:
            if st.button("🔄 Atualizar Painel"):
                st.cache_data.clear()
                st.rerun()

        res_treinos = supabase.table("atividades_fisicas").select("*").eq("id_atleta", user['id']).order("data_treino", desc=True).execute()
        
        if res_treinos.data:
            df = pd.DataFrame(res_treinos.data)
            
            df['data_treino'] = pd.to_datetime(df['data_treino']).dt.tz_localize(None)
            df['distancia'] = pd.to_numeric(df['distancia'], errors='coerce').fillna(0)
            df['trimp_score'] = pd.to_numeric(df['trimp_score'], errors='coerce').fillna(0)
            df['duracao'] = pd.to_numeric(df['duracao'], errors='coerce').fillna(0)
            
            agora = datetime.now()

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

            m1, m2, m3 = st.columns(3)
            m1.metric("Total de Treinos", len(df))
            m2.metric("Distância Total", f"{df['distancia'].sum():.1f} km")
            m3.metric("Carga Média (TRIMP)", f"{int(df['trimp_score'].mean())} pts")
            
            st.markdown("### 📋 Histórico Recente")
            df_show = df.head(10).copy()
            df_show['Data'] = df_show['data_treino'].dt.strftime('%d/%m/%Y')
            
            if 'name' not in df_show.columns:
                df_show['name'] = 'Treino Importado'

            # CORREÇÃO AQUI: Mudança para width='stretch'
            st.dataframe(
                df_show[['Data', 'name', 'distancia', 'duracao', 'trimp_score']], 
                width='stretch',  # <--- CORRIGIDO
                hide_index=True,
                column_config={
                    "name": "Nome da Atividade",
                    "distancia": st.column_config.NumberColumn("Distância (km)", format="%.2f"),
                    "duracao": st.column_config.NumberColumn("Tempo (min)", format="%d"),
                    "trimp_score": st.column_config.ProgressColumn(
                        "Carga Interna (TRIMP)", 
                        format="%d", 
                        min_value=0, 
                        max_value=300,
                        help="Pontuação de esforço baseada na sua FC Máxima"
                    )
                }
            )

            st.markdown("### 📊 Análise de Evolução")
            col1, col2 = st.columns(2)
            fig1 = gerar_grafico_analise(df, "Volume vs Esforço (7 dias)", 7)
            fig2 = gerar_grafico_analise(df, "Consistência Mensal (30 dias)", 30)
            
            # CORREÇÃO AQUI: Mudança para width='stretch'
            if fig1: col1.plotly_chart(fig1, width='stretch') # <--- CORRIGIDO
            if fig2: col2.plotly_chart(fig2, width='stretch') # <--- CORRIGIDO
            
        else:
            st.info("Bem-vindo à DataPace! Conecte seu Strava no menu lateral para importar seus treinos.")

# ============================================================================
# 6. RODAPÉ JURÍDICO
# ============================================================================
exibir_logo_rodape()