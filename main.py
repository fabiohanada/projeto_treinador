import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from modules.ui import aplicar_estilo_css, exibir_rodape_strava
from modules.views import renderizar_tela_login, renderizar_tela_admin

# CONFIGURAÇÕES GERAIS
CHAVE_PIX = "seu-pix@email.com" 
WHATSAPP = "5511969603611"
VERSAO = "v8.1"

st.set_page_config(page_title=f"Fábio Assessoria {VERSAO}", layout="wide", page_icon="🏃‍♂️")

try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Erro de conexão com o banco de dados.")
    st.stop()

aplicar_estilo_css()

# Inicializa estado de login
if "logado" not in st.session_state: 
    st.session_state.logado = False

if not st.session_state.logado:
    renderizar_tela_login(supabase)
else:
    user = st.session_state.user_info
    
    # --- PAINEL LATERAL (SIDEBAR) UNIVERSAL ---
    # Agora aparece para Admin e para Alunos
    with st.sidebar:
        st.markdown(f"### Fábio Assessoria `{VERSAO}`")
        st.write(f"👤 Usuário: **{user['nome']}**")
        st.write(f"🔑 Perfil: **{'Treinador' if user.get('is_admin') else 'Aluno'}**")
        st.markdown("---")
        
        if st.button("Sair / Logoff", width="stretch", type="secondary"):
            st.session_state.clear()
            st.rerun()

    # --- LÓGICA DE TELAS ---
    if user.get('is_admin', False):
        # Tela do Treinador
        renderizar_tela_admin(supabase)
    else:
        # Tela do Aluno (com verificação de bloqueio)
        if user.get('bloqueado', False):
            st.warning("### ⚠️ Acesso Suspenso")
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"Para desbloquear, realize o PIX para a chave abaixo:")
                st.code(CHAVE_PIX, language=None)
                st.write("**Nome:** Fabio Hanada")
                qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={CHAVE_PIX}"
                st.image(qr_url, caption="Escaneie para pagar")
            
            with c2:
                msg = f"Olá Fábio, paguei meu plano. Meu email: {user['email']}"
                st.markdown(f'''
                    <a href="https://wa.me/{WHATSAPP}?text={msg.replace(" ", "%20")}" target="_blank" style="text-decoration:none;">
                        <div style="background-color:#25D366;color:white;padding:20px;border-radius:10px;text-align:center;font-weight:bold;">
                            ✅ ENVIAR COMPROVANTE AGORA
                        </div>
                    </a>
                ''', unsafe_allow_html=True)
        else:
            # Tela do Aluno Ativo
            st.title(f"Olá, {user['nome']}! 🏃‍♂️")
            
            try:
                res_t = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).execute()
                if res_t.data:
                    df = pd.DataFrame(res_t.data)
                    df = df.sort_values('data')
                    df['Data_Exibicao'] = pd.to_datetime(df['data']).dt.strftime('%d/%m')
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Volume (Km)")
                        st.plotly_chart(px.bar(df, x='Data_Exibicao', y='distancia', color_discrete_sequence=['#1f77b4']), use_container_width=True)
                    with col2:
                        st.subheader("Carga (TRIMP)")
                        st.plotly_chart(px.area(df, x='Data_Exibicao', y='trimp', color_discrete_sequence=['#0044cc']), use_container_width=True)
                    
                    st.dataframe(df[['nome', 'data', 'distancia', 'trimp']], hide_index=True, use_container_width=True)
                else:
                    st.info("Sincronize seus treinos no Strava para ver as estatísticas.")
            except:
                st.warning("Aguardando sincronização de treinos...")
            
            exibir_rodape_strava()