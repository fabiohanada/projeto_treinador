import streamlit as st
import pandas as pd
from datetime import datetime
import os
import requests
import hashlib
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client

# 1. CONFIGURAÇÕES INICIAIS
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

# Conexões
supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app"

# --- FUNÇÕES CORE ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone_destino):
    """Função de disparo via Twilio"""
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER") 
        client = Client(sid, token)
        tel_limpo = ''.join(filter(str.isdigit, str(telefone_destino)))
        p_from_limpo = p_from.replace("whatsapp:", "").replace("+", "").strip()
        client.messages.create(body=mensagem, from_=f"whatsapp:+{p_from_limpo}", to=f"whatsapp:+{tel_limpo}")
        return True
    except: return False

def sincronizar_dados(strava_id, access_token):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        res = requests.get(url, headers=headers, params={'per_page': 15})
        if res.status_code == 200:
            atividades = res.json()
            for atv in atividades:
                payload = {
                    "id_atleta": int(strava_id),
                    "data_treino": atv['start_date_local'],
                    "trimp_score": atv['moving_time'] / 60,
                    "distancia": atv['distance'] / 1000,
                    "tipo_esporte": atv['type']
                }
                supabase.table("atividades_fisicas").upsert(payload).execute()
            return True
        return False
    except: return False

# --- CONTROLE DE ACESSO ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🏃‍♂️ Seu Treino App")
        with st.container(border=True):
            e = st.text_input("E-mail")
            s = st.text_input("Senha", type="password")
            if st.button("Entrar", use_container_width=True, type="primary"):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado = True
                    st.session_state.user_info = u.data[0]
                    st.rerun()
                else: st.error("E-mail ou senha incorretos.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)
data_hoje = datetime.now().date()

# =================================================================
# 👨‍🏫 VISÃO ADMINISTRADOR (TREINADOR)
# =================================================================
if eh_admin:
    with st.sidebar:
        st.title(f"👨‍🏫 {user['nome']}")
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logado = False
            st.rerun()
    
    st.title("🎮 Painel de Controle do Treinador")
    tab_financeiro, tab_treinos = st.tabs(["💰 Gestão Financeira", "📊 Análise de Performance"])
    
    with tab_financeiro:
        st.subheader("Lista de Alunos e Pagamentos")
        res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
        
        if res_alunos.data:
            df_fin = pd.DataFrame(res_alunos.data)
            for _, aluno in df_fin.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.markdown(f"**{aluno['nome']}**\n{aluno['email']}")
                    
                    # Lógica de status
                    venc = aluno.get('data_vencimento')
                    status_cor = "green" if aluno['status_pagamento'] else "red"
                    c2.markdown(f"<span style='color:{status_cor}'>●</span> {'Ativo' if aluno['status_pagamento'] else 'Inativo'}", unsafe_allow_html=True)
                    c3.write(f"Venc: {venc if venc else '---'}")
                    
                    btn_label = "Bloquear" if aluno['status_pagamento'] else "Liberar"
                    if c4.button(btn_label, key=f"fin_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()
        else:
            st.info("Nenhum aluno cadastrado.")

    with tab_treinos:
        res_strava = supabase.table("usuarios").select("*").execute()
        if res_strava.data:
            atletas = {u['nome']: u for u in res_strava.data}
            sel = st.selectbox("Escolha um Atleta para ver detalhes", list(atletas.keys()))
            atleta_foco = atletas[sel]
            
            if st.button(f"🔄 Sincronizar Strava de {sel}"):
                if sincronizar_dados(atleta_foco['strava_id'], atleta_foco['access_token']):
                    st.success("Dados atualizados!")
                    st.rerun()

# =================================================================
# 🏃‍♂️ VISÃO ATLETA (CLIENTE)
# =================================================================
else:
    # Verifica se o pagamento está em dia
    venc_str = user.get('data_vencimento', '2000-01-01')
    venc_date = datetime.strptime(venc_str if venc_str else '2000-01-01', '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and data_hoje <= venc_date

    tab_treino, tab_pagamento = st.tabs(["🏃 Meus Treinos", "💳 Assinatura Pix"])

    with tab_treino:
        st.title(f"🚀 Fala, {user['nome']}!")
        
        if pago:
            st.success("Sua assinatura está ativa.")
            if st.button("🔄 Sincronizar meus dados do Strava", type="primary"):
                # Busca token na tabela 'usuarios' do Strava usando o nome
                res_t = supabase.table("usuarios").select("access_token").eq("nome", user['nome']).execute()
                if res_t.data:
                    if sincronizar_dados(user['strava_id'], res_t.data[0]['access_token']):
                        st.success("Treinos atualizados!")
                        st.rerun()
                else:
                    st.warning("Vínculo com Strava não encontrado. Fale com o Fábio.")
        else:
            st.error("🚨 Sincronização bloqueada por pendência financeira.")
            st.info("Regularize seu acesso na aba 'Assinatura Pix'.")

        # Gráfico de histórico
        if user.get('strava_id'):
            res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", user['strava_id']).execute()
            if res_atv.data:
                df = pd.DataFrame(res_atv.data)
                st.subheader("Seu volume recente (km)")
                st.line_chart(df.tail(10).set_index('data_treino')['distancia'])

    with tab_pagamento:
        st.header("💳 Central de Pagamento")
        if pago:
            st.success(f"Tudo em dia! Próximo vencimento: {venc_date.strftime('%d/%m/%Y')}")
        else:
            st.warning("Seu plano está expirado.")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Chave Pix (E-mail):**")
                st.code("seu-email@pix.com", language="text")
                st.image("https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=SUA_CHAVE_PIX_AQUI")
            with c2:
                st.write("Após pagar, clique no botão abaixo para avisar o treinador.")
                if st.button("✅ Já realizei o pagamento"):
                    enviar_whatsapp(f"💰 Pagamento: O aluno {user['nome']} informou que pagou o Pix.", "SEU_TELEFONE_AQUI")
                    st.info("Avisamos o Fábio! Seu acesso será liberado em breve.")
