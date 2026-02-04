import streamlit as st
import pandas as pd
import plotly.express as px
import requests  # Necessário para a troca do token Strava
from supabase import create_client

# Importa as funções do arquivo ui.py (que deve estar na pasta modules)
# Se o ui.py estiver na mesma pasta do main, mude para: from ui import ...
from modules.ui import aplicar_estilo_css, exibir_botao_strava_sidebar, exibir_logo_rodape
from modules.views import renderizar_tela_login, renderizar_tela_admin

# --- CONFIGURAÇÕES GERAIS ---
CHAVE_PIX = "seu-pix@email.com"  # <--- CONFIRA SUA CHAVE
WHATSAPP = "5511969603611"
VERSAO = "v8.1"

st.set_page_config(page_title=f"Fábio Assessoria {VERSAO}", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÃO SUPABASE ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Erro crítico: Banco de dados indisponível.")
    st.stop()

aplicar_estilo_css()

# --- LÓGICA DE CALLBACK DO STRAVA (OAUTH) ---
# Isso captura o código quando o usuário volta do site do Strava
if "code" in st.query_params:
    code = st.query_params["code"]
    try:
        res = requests.post("https://www.strava.com/oauth/token", data={
            'client_id': st.secrets["STRAVA_CLIENT_ID"],
            'client_secret': st.secrets["STRAVA_CLIENT_SECRET"],
            'code': code,
            'grant_type': 'authorization_code'
        })
        
        if res.status_code == 200:
            tokens = res.json()
            # Aqui você pode salvar o token no Supabase se desejar
            # Exemplo: supabase.table("users").update({"strava_token": tokens['access_token']}).eq("email", user_email).execute()
            st.session_state['strava_access_token'] = tokens['access_token']
            st.toast("Strava conectado com sucesso!", icon="✅")
        else:
            st.error(f"Erro ao conectar Strava: {res.json()}")
            
        # Limpa a URL para não processar o código novamente
        st.query_params.clear()
    except Exception as e:
        st.error(f"Erro na conexão: {e}")

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    renderizar_tela_login(supabase)
else:
    user = st.session_state.user_info
    
    # --- SIDEBAR (Barra Lateral) ---
    with st.sidebar:
        st.markdown(f"### Fábio Assessoria `{VERSAO}`")
        st.write(f"👤 **{user['nome']}**")
        st.write(f"🔑 Perfil: **{'Treinador' if user.get('is_admin') else 'Aluno'}**")
        st.markdown("---")
        
        # Botão Strava (Corrigido e integrado)
        if not user.get('is_admin'):
            st.write("**Sincronização:**")
            # Verifica se já tem token na sessão para dar feedback visual (opcional)
            if 'strava_access_token' in st.session_state:
                st.success("Strava Conectado ✅")
            else:
                exibir_botao_strava_sidebar() 
            
            st.markdown("---")
        
        if st.button("Sair / Logoff", key="btn_logout", help="Sair do sistema"):
            st.session_state.clear()
            st.rerun()

    # --- ÁREA PRINCIPAL ---
    if user.get('is_admin', False):
        renderizar_tela_admin(supabase)
    else:
        # TELA DO ALUNO - BLOQUEIO
        if user.get('bloqueado', False):
            st.warning("### ⚠️ Acesso Suspenso")
            
            c1, c2 = st.columns([1, 1])
            with c1:
                st.markdown("#### 1. Pagamento via PIX")
                st.write(f"Chave: `{CHAVE_PIX}`")
                st.write("**Favorecido:** Fabio Hanada")
                
                # QR Code (URL direta e segura)
                qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={CHAVE_PIX}&bgcolor=ffffff"
                st.image(qr_url, caption="Escaneie para pagar", width=200)
            
            with c2:
                st.markdown("#### 2. Comprovante")
                msg = f"Olá Fábio, realizei o pagamento. Login: {user['email']}"
                link_zap = f"https://wa.me/{WHATSAPP}?text={msg.replace(' ', '%20')}"
                
                st.markdown(f"""
                    <br>
                    <a href="{link_zap}" target="_blank" style="text-decoration:none;">
                        <div style="background-color:#25D366; color:white; padding:15px; border-radius:10px; text-align:center; font-weight:bold;">
                            ✅ ENVIAR NO WHATSAPP
                        </div>
                    </a>
                """, unsafe_allow_html=True)

        # TELA DO ALUNO - ATIVO
        else:
            st.title(f"Olá, {user['nome']}! 🏃‍♂️")
            try:
                res_t = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).execute()
                if res_t.data:
                    df = pd.DataFrame(res_t.data)
                    df = df.sort_values('data')
                    df['Data_Exibicao'] = pd.to_datetime(df['data']).dt.strftime('%d/%m')
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader("Volume (Km)")
                        st.plotly_chart(px.bar(df, x='Data_Exibicao', y='distancia', color_discrete_sequence=['#1f77b4']), use_container_width=True)
                    with c2:
                        st.subheader("Carga (TRIMP)")
                        st.plotly_chart(px.area(df, x='Data_Exibicao', y='trimp', color_discrete_sequence=['#0044cc']), use_container_width=True)
                    
                    st.dataframe(df[['nome', 'data', 'distancia', 'trimp']], hide_index=True, use_container_width=True)
                else:
                    st.info("Nenhum treino encontrado. Conecte seu Strava na barra lateral para importar atividades.")
            except Exception as e:
                st.warning(f"Verificando dados... ({e})")

    # Logo Rodapé (Sempre visível no final da execução)
    exibir_logo_rodape()