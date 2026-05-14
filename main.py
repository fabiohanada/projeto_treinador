import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from supabase import create_client
from datetime import datetime, timedelta, date
import math 
import threading
import time
import base64
import uuid

# Importação dos módulos customizados
from modules.ui import aplicar_estilo_css, exibir_logo_rodape, estilizar_botoes
from modules.views import renderizar_tela_admin, renderizar_tela_bloqueio_financeiro, enviar_notificacao_treino, renderizar_edicao_perfil

# Importação da sua função de processamento de fila
try:
    from processar_fila import processar_novos_treinos
    from auth_strava import obter_token_valido
except ImportError:
    st.error("Arquivo processar_fila.py não encontrado ou função ausente!")

# ============================================================================
# 1. CONFIGURAÇÕES E CONEXÃO
# ============================================================================
st.set_page_config(page_title="Zaptreino", layout="wide", page_icon="🏃‍♂️")

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
    res = supabase_client.table("usuarios_app").select("*").eq("id", target_id).execute()
    if res.data:
        st.session_state.user_info = res.data[0]
        st.session_state.logado = True
        # Limpa os parâmetros mas mantém o session_id na URL para o app não deslogar ao dar refresh
        st.query_params.clear()
        st.query_params["session_id"] = target_id
        st.rerun()
        
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
# 5. ROTEAMENTO DE TELAS E NOVO DESIGN DE LOGIN
# ============================================================================
if not st.session_state.logado:
    
    # --- BUSCA A IMAGEM NA PASTA ASSETS AGORA ---
    def get_base64_of_bin_file(bin_file):
        try:
            with open(bin_file, 'rb') as f:
                return base64.b64encode(f.read()).decode()
        except Exception as e: 
            return ""

    img_base64 = get_base64_of_bin_file("assets/fundo_runner.png")

    st.markdown(f"""
        <style>
        /* 1. Imagem de Fundo Full Screen */
        .stApp {{
            background-image: url("data:image/png;base64,{img_base64}");
            background-size: cover;
            background-attachment: fixed;
        }}
        
        /* 2. Esconde menus apenas na tela de login */
        [data-testid="stHeader"] {{display: none;}}
        [data-testid="stSidebar"] {{display: none;}}
        .block-container {{padding: 0 !important; max-width: 100% !important; overflow-x: hidden;}}

        /* 3. APLICA O VIDRO FOSCO DIRETAMENTE NA COLUNA DO MEIO */
        div[data-testid="stHorizontalBlock"] > div:nth-child(2) {{
            background: rgba(255, 255, 255, 0.65) !important; 
            border-radius: 20px !important;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border: 1px solid rgba(255, 255, 255, 0.5) !important;
            padding: 30px !important;
            margin-top: 8vh;
        }}

        /* Truque para remover o fundo branco da sua logo_zaptreino.png */
        [data-testid="stImage"] img {{
            mix-blend-mode: multiply;
        }}
        

        /* Deixa o Form invisivel para se misturar na coluna */
        div[data-testid="stForm"] {{
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
        }}

        /* 4. Estilo Botão Laranja */
        div[data-testid="stFormSubmitButton"] button {{
            background-color: #FF5722 !important;
            color: white !important;
            border-radius: 8px !important;
            font-weight: 900 !important;
            height: 45px !important;
            border: none !important;
            text-transform: uppercase;
            transition: 0.3s ease !important;
            margin-top: 15px;
        }}
        div[data-testid="stFormSubmitButton"] button:hover {{
            background-color: #E64A19 !important;
            transform: translateY(-2px);
        }}
        
        /* 5. Ajuste das Abas */
        .stTabs [data-baseweb="tab-list"] {{ justify-content: center; background-color: transparent; }}
        .stTabs [aria-selected="true"] {{ color: #FF5722 !important; border-bottom-color: #FF5722 !important; font-weight: bold; }}
        </style>
    """, unsafe_allow_html=True)

    # Criação das colunas: A do meio (índice 2) recebe o efeito de vidro
    col_vazia_esq, col_painel_dir, col_margem = st.columns([1.8, 1.2, 0.2])

    with col_painel_dir:
        # Tenta carregar a logo, com o truque css ela ficará transparente
        try: st.image("assets/logo_zaptreino.png")
        except: pass
        
        st.markdown("<br>", unsafe_allow_html=True)

        aba_login, aba_cadastro = st.tabs(["Fazer Login", "Criar Conta"])

        with aba_login:
            with st.form("form_login_vidro"):
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                
                if st.form_submit_button("ENTRAR", width="stretch"):
                    if not email or not senha:
                        st.warning("Preencha todos os campos.")
                    else:
                        with st.spinner("Autenticando..."):
                            email = email.strip().lower()
                            try:
                                res = supabase_client.table("usuarios_app").select("*").eq("email", email).eq("senha", senha).execute()
                                if res.data:
                                    user = res.data[0]
                                    st.session_state.user_info = user
                                    st.session_state.logado = True
                                    uid = str(user.get('id') or user.get('uuid'))
                                    st.query_params["session_id"] = uid
                                    st.success(f"Bem-vindo, {user['nome']}!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error("E-mail ou senha incorretos.")
                            except Exception as e:
                                st.error(f"Erro técnico: {e}")

        with aba_cadastro:
            # O SEU CÓDIGO ORIGINAL INTACTO DE CRIAR CONTA
            with st.form("form_cadastro"):
                novo_nome = st.text_input("Nome Completo")
                novo_email = st.text_input("E-mail")
                novo_telefone = st.text_input("Telefone (WhatsApp)", placeholder="+5511999999999")
                
                data_nasc = st.date_input(
                    "Data de Nascimento",
                    value=None,
                    min_value=date(1920, 1, 1), 
                    max_value=date.today(),      
                    format="DD/MM/YYYY"
                )
                nova_senha = st.text_input("Defina uma Senha", type="password")
                confirma_senha = st.text_input("Confirme a Senha", type="password")
                
                st.divider()
                st.markdown("<h4 style='text-align: center;'>Termos e Privacidade</h4>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: gray; font-size: 14px;'>Ao clicar em aceitar, você concorda com os nossos Termos de Uso e Política de Privacidade (LGPD).</p>", unsafe_allow_html=True)
                aceite_termos = st.checkbox("Eu li e aceito os termos e condições.")
                
                botao_cadastrar = st.form_submit_button("Cadastrar", width="stretch")
                
                if botao_cadastrar:
                    if not (novo_nome and novo_email and novo_telefone and nova_senha and data_nasc):
                        st.warning("⚠️ Preencha todos os campos obrigatórios.")
                    elif nova_senha != confirma_senha:
                        st.error("❌ As senhas não coincidem.")
                    elif not aceite_termos:
                        st.error("🔒 É necessário aceitar os termos da LGPD.")
                    else:
                        dados = {
                            "nome": novo_nome, 
                            "email": novo_email.strip().lower(), 
                            "telefone": novo_telefone, 
                            "senha": nova_senha, 
                            "data_nascimento": str(data_nasc), 
                            "is_admin": False, 
                            "status_pagamento": True,
                            "aceite_lgpd": True
                        }
                        try:
                            dados["id"] = str(uuid.uuid4())
                            supabase_client.table("usuarios_app").insert(dados).execute()
                            st.balloons()
                            st.success("Conta criada! Faça login na aba ao lado.")
                        except:
                            st.error("Erro ao cadastrar. E-mail já existe?")

else:
    # ============================================================================
    # TUDO DAQUI PARA BAIXO ESTÁ INTACTO (LÓGICA ORIGINAL DO SISTEMA LOGADO)
    # ============================================================================
    user = st.session_state.user_info
    
    # --- LÓGICA DE BLOQUEIO POR DATA E MANUAL ---
    hoje_data = datetime.now().date()
    data_venc_banco = user.get('data_vencimento')
    
    try:
        vencimento = pd.to_datetime(data_venc_banco).date() if data_venc_banco else hoje_data
    except:
        vencimento = hoje_data

    # Regras de bloqueio
    plano_expirado = hoje_data > vencimento
    bloqueado_manual = user.get('bloqueado', False)
    aluno_bloqueado = bloqueado_manual or plano_expirado
    
    with st.sidebar:
        st.markdown(f"### DataPace\n👤 **{user['nome']}**")
        
        # ============================================================
        # TRAVA DO ADMIN: Só exibe menus de aluno se NÃO for admin
        # ============================================================
        if not user.get('is_admin'):
            
            # Só permite editar perfil, conectar Strava e ver Notificações se NÃO estiver bloqueado/vencido
            if not aluno_bloqueado:
                renderizar_edicao_perfil(supabase_client, user)
                st.markdown("---")
                url_strava = f"https://www.strava.com/oauth/authorize?client_id={st.secrets['STRAVA_CLIENT_ID']}&response_type=code&redirect_uri={st.secrets['STRAVA_REDIRECT_URI']}&approval_prompt=auto&scope=read,activity:read_all&state={user['id']}"
                st.markdown(f'''
                    <a href="{url_strava}" target="_top">
                        <button style="background-color:#FC4C02;color:white;border:none;padding:10px;width:100%;border-radius:4px;font-weight:bold;cursor:pointer;">
                            Sincronizar Strava
                        </button>
                    </a>
                ''', unsafe_allow_html=True)
            
                # O bloco de notificações agora só aparece para alunos liberados
                st.markdown("---")
                st.markdown("### 📲 Notificações")
                
                numero_sandbox = "14155238886"
                codigo_join = "join rule-buy"
                url_zap = f"https://wa.me/{numero_sandbox}?text={codigo_join}"
                
                st.info("Para receber análises no Zap, ative o robô clicando abaixo:")
                st.markdown(f'''
                    <a href="{url_zap}" target="_blank">
                        <button style="background-color:#25D366;color:white;border:none;padding:10px;width:100%;border-radius:4px;font-weight:bold;cursor:pointer;">
                            ✅ ATIVAR WHATSAPP
                        </button>
                    </a>
                ''', unsafe_allow_html=True)
        # ============================================================
        
        # --- BOTÃO SAIR (FICA VISÍVEL PARA TODO MUNDO) ---
        st.sidebar.markdown("---") 
        if st.sidebar.button("Sair da Conta", width='stretch', key="btn_sair_fixo"):
            st.session_state.clear() 
            st.query_params.clear() 
            st.rerun()
            
    # --- ROTEAMENTO FINAL ---
    if user.get('is_admin'):
        renderizar_tela_admin(supabase_client)
    
    elif aluno_bloqueado:
        renderizar_tela_bloqueio_financeiro()
        st.stop() 
        
    else:
        # TELA DO ALUNO (ACESSO LIBERADO)
        if 'sync_inicial' not in st.session_state:
            with st.spinner("Sincronizando seus treinos agora..."):
                processar_fila_treinos(user['id'], origem_botao=True)
                st.session_state['sync_inicial'] = True

        st.title(f"E aí, {user['nome'].split()[0]}! ⚡")
        
        res_t = supabase_client.table("atividades_fisicas").select(
            "data_treino, name, distancia, duracao, trimp_score, trimp_semanal, trimp_mensal"
        ).eq("id_atleta", user['id']).order("data_treino", desc=True).execute()
        
        if res_t.data:
            df = pd.DataFrame(res_t.data)
            df['duracao_formatada'] = df['duracao'].apply(lambda x: f"{int(x)//60:02d}:{int(x)%60:02d}" if pd.notna(x) else "00:00")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Treinos", len(df))
            m2.metric("Km Acumulados", f"{df['distancia'].sum():.1f}")
            m3.metric("Carga Média", f"{int(df['trimp_score'].mean())}")
            
            def formatar_carga(valor, tipo):
                if pd.isna(valor) or valor == 0: return "-"
                if tipo == 'dia':
                    emoji = "🟢" if valor <= 70 else "🟡" if valor <= 150 else "🔴"
                elif tipo == 'sem':
                    emoji = "🟢" if valor <= 400 else "🟡" if valor <= 800 else "🔴"
                else: 
                    emoji = "🟢" if valor <= 1500 else "🟡" if valor <= 3000 else "🔴"
                return f"{int(valor)} {emoji}"

            df['Carga Diária'] = df['trimp_score'].apply(lambda x: formatar_carga(x, 'dia'))
            df['Carga 7 Dias'] = df['trimp_semanal'].apply(lambda x: formatar_carga(x, 'sem'))
            df['Carga 30 Dias'] = df['trimp_mensal'].apply(lambda x: formatar_carga(x, 'men'))

            st.dataframe(
                df[['data_treino', 'name', 'distancia', 'duracao_formatada', 'Carga Diária', 'Carga 7 Dias', 'Carga 30 Dias']].head(15), 
                width='stretch', 
                hide_index=True,
                column_config={
                    "data_treino": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "name": st.column_config.TextColumn("Atividade", width="large"),
                    "distancia": st.column_config.NumberColumn("Km", format="%.2f"),
                    "duracao_formatada": st.column_config.TextColumn("Tempo"),
                    "Carga Diária": st.column_config.TextColumn("TRIMP 🟢"),
                    "Carga 7 Dias": st.column_config.TextColumn("7 Dias 📊"),
                    "Carga 30 Dias": st.column_config.TextColumn("30 Dias 📈"),
                }
            )

            st.markdown("---")
            with st.expander("❓ Entenda as Cores da Carga (Semáforo)"):
                c1, c2, c3 = st.columns(3)
                c1.info("**Diario**\n\n🟢 < 70\n\n🟡 71-150\n\n🔴 > 150")
                c2.warning("**Semanal**\n\n🟢 < 400\n\n🟡 401-800\n\n🔴 > 800")
                c3.error("**Mensal**\n\n🟢 < 1500\n\n🟡 1501-3000\n\n🔴 > 3000")

            c1, c2 = st.columns(2)
            g1 = gerar_grafico_analise(df, "Últimos 7 dias", 7)
            g2 = gerar_grafico_analise(df, "Últimos 30 dias", 30)
            if g1: c1.plotly_chart(g1, width='stretch')
            if g2: c2.plotly_chart(g2, width='stretch')
        else:
            st.info("Nenhum treino encontrado. Conecte seu Strava!")

exibir_logo_rodape()