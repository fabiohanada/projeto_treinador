import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client

# ==========================================================
# VERSÃO: v7.0 MASTER (TODAS AS FUNCIONALIDADES UNIFICADAS)
# ==========================================================

st.set_page_config(page_title="Fábio Assessoria v7.0", layout="wide", page_icon="🏃‍♂️")

# --- 1. CONEXÕES E SEGREDOS ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
except Exception as e:
    st.error("Erro crítico nas configurações (Secrets). Verifique o Streamlit Cloud.")
    st.stop()

# --- 2. CONFIGURAÇÕES GERAIS ---
REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- 3. FUNÇÕES AUXILIARES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

# --- 4. CSS (RODAPÉ E ESTILO) ---
st.markdown("""
    <style>
    /* Garante espaço para o rodapé não cobrir conteúdo */
    .main .block-container { padding-bottom: 120px; }
    
    /* Rodapé Fixo e Blindado */
    .footer-strava {
        position: fixed; bottom: 0; left: 0; width: 100%;
        background-color: white; text-align: right;
        padding: 10px 30px; border-top: 1px solid #eee; z-index: 999;
    }
    /* Proteção contra distorção da logo */
    .strava-logo { width: 150px !important; height: auto !important; }
    
    /* Estilo dos cards do Admin */
    div[data-testid="stVerticalBlockBorderWrapper"] { 
        border: 1px solid #f0f2f6; 
        border-radius: 10px; 
        padding: 15px;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 5. CONTROLE DE SESSÃO ---
if "logado" not in st.session_state: st.session_state.logado = False

# --- TELA DE LOGIN / CADASTRO ---
if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Aluno"])
        
        # ABA LOGIN
        with tab_login:
            with st.form("login_form"):
                e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Painel", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.rerun()
                    else: st.error("E-mail ou senha incorretos.")
        
        # ABA CADASTRO (COM LGPD E TELEFONE)
        with tab_cadastro:
            with st.form("cad_form"):
                n_nome = st.text_input("Nome Completo")
                n_email = st.text_input("E-mail")
                n_tel = st.text_input("Celular / WhatsApp") # --> RESTAURADO
                n_senha = st.text_input("Crie uma Senha", type="password")
                
                st.markdown("---")
                # --> LGPD RESTAURADA
                aceite = st.checkbox("Li e aceito os Termos de Uso e LGPD 🔒")
                with st.expander("📄 Ver Termos Detalhados"):
                    st.write("Ao se cadastrar, você concorda que seus dados de treino (Strava) serão utilizados exclusivamente para análise de performance pelo treinador Fábio Hanada.")
                
                if st.form_submit_button("Criar Conta", use_container_width=True):
                    if not aceite:
                        st.error("⚠️ É obrigatório aceitar os termos da LGPD.")
                    elif n_nome and n_email and n_senha:
                        try:
                            # Inserção completa no banco
                            supabase.table("usuarios_app").insert({
                                "nome": n_nome, "email": n_email, "telefone": n_tel, 
                                "senha": hash_senha(n_senha), "status_pagamento": False
                            }).execute()
                            st.success("Cadastro realizado! Aguarde a ativação pelo Fábio.")
                        except: st.error("Erro: Este e-mail provavelmente já existe.")
    st.stop()

# --- DADOS DO USUÁRIO LOGADO ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- 6. BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if not eh_admin:
        # Botão Strava Oficial
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={urllib.parse.quote(REDIRECT_URI + '?user_mail=' + user['email'])}&scope=activity:read_all&approval_prompt=auto"
        st.markdown(f'''<a href="{link_strava}" target="_self" style="text-decoration: none;"><div style="background-color: #FC4C02; color: white; padding: 12px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 20px;">Connect with STRAVA</div></a>''', unsafe_allow_html=True)
    
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state.clear(); st.rerun()

# --- 7. TELA DO ADMIN ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    st.write("---")
    
    # Busca alunos
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    if not alunos.data:
        st.info("Nenhum aluno cadastrado.")
    
    for aluno in alunos.data:
        with st.container(border=True):
            # Layout de 3 colunas solicitado
            c1, c2, c3 = st.columns([2, 2, 1.5])
            
            with c1:
                st.subheader(aluno['nome'])
                st.caption(f"📧 {aluno['email']}")
                if aluno.get('telefone'): st.caption(f"📞 {aluno['telefone']}")
                st.write(f"**Status:** {'✅ ATIVO' if aluno['status_pagamento'] else '❌ BLOQUEADO'}")
            
            with c2:
                # Seletor de Data
                v_data = date.fromisoformat(aluno['data_vencimento']) if aluno.get('data_vencimento') else date.today()
                nova_dt = st.date_input("Vencimento", value=v_data, key=f"d_{aluno['id']}")
                st.caption(f"Vence em: {formatar_data_br(str(nova_dt))}")
            
            with c3:
                st.write("") # Espaçamento para alinhar botões
                # Botão Salvar
                if st.button("💾 Salvar Data", key=f"s_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt), "status_pagamento": True}).eq("id", aluno['id']).execute()
                    st.success("Salvo!")
                    st.rerun()
                
                # Botão Dinâmico (Ativar/Bloquear) --> RESTAURADO
                if aluno['status_pagamento']:
                    if st.button("🚫 Bloquear", key=f"b_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": False}).eq("id", aluno['id']).execute()
                        st.rerun()
                else:
                    if st.button("✅ Ativar", key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": True}).eq("id", aluno['id']).execute()
                        st.rerun()

# --- 8. TELA DO ALUNO (DASHBOARD) ---
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    
    # VERIFICAÇÃO DE PAGAMENTO (COM FINANCEIRO VISÍVEL)
    if not user.get('status_pagamento'):
        st.error("⚠️ Seu acesso está suspenso. Realize a renovação abaixo.")
        
        # --> FINANCEIRO RESTAURADO AQUI
        with st.expander("💳 DADOS PARA PAGAMENTO (PIX)", expanded=True):
            c_pix1, c_pix2 = st.columns([1, 3])
            with c_pix1:
                st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(pix_copia_e_cola)}")
            with c_pix2:
                st.markdown("**Chave PIX (Copia e Cola):**")
                st.code(pix_copia_e_cola)
                st.write("Envie o comprovante para o treinador para reativar seu acesso.")
        
        st.markdown("---")
        st.warning("O conteúdo do treino ficará visível após a confirmação do pagamento.")
        st.stop() # Só para aqui, depois de mostrar o PIX.
    
    # Conteúdo liberado
    st.info(f"📅 Plano ativo até: **{formatar_data_br(user.get('data_vencimento'))}**")
    
    # Gráficos
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df, x='data', y='distancia', title="Volume Diário (km)", color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with c2: st.plotly_chart(px.line(df, x='data', y='fc_media', title="Evolução FC Média"), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum treino sincronizado ainda. Use o botão na barra lateral para conectar ao Strava.")

# --- 9. RODAPÉ STRAVA OFICIAL (PROTEGIDO) ---
st.markdown(f"""
    <div class="footer-strava">
        <img src="https://strava.github.io/api/images/api_logo_pwrdBy_strava_horiz_light.png" class="strava-logo" alt="Powered by Strava">
    </div>
    """, unsafe_allow_html=True)
