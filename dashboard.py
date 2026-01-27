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
st.set_page_config(page_title="Seu Treino App", layout="wide", page_icon="🏃‍♂️")

def get_secret(key):
    try:
        return st.secrets[key] if key in st.secrets else os.getenv(key)
    except: return None

# Conexões
supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")

# --- FUNÇÕES CORE ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone_destino):
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

# --- TELA DE LOGIN E CADASTRO ---
if "logado" not in st.session_state:
    st.session_state.logado = False

data_hoje = datetime.now().date()

if not st.session_state.logado:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🏃‍♂️ Seu Treino App")
        
        aba_login, aba_cadastro = st.tabs(["Entrar", "Novo Cadastro"])
        
        with aba_login:
            with st.container(border=True):
                e = st.text_input("E-mail", key="login_email")
                s = st.text_input("Senha", type="password", key="login_senha")
                if st.button("Entrar", use_container_width=True, type="primary"):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado = True
                        st.session_state.user_info = u.data[0]
                        st.rerun()
                    else: 
                        st.error("E-mail ou senha incorretos.")
        
        with aba_cadastro:
            with st.container(border=True):
                novo_nome = st.text_input("Nome Completo")
                novo_email = st.text_input("E-mail", key="reg_email")
                novo_tel = st.text_input("WhatsApp (DDD + Número)")
                nova_senha = st.text_input("Crie uma Senha", type="password", key="reg_senha")
                confirmar_senha = st.text_input("Confirme a Senha", type="password")
                
                aceitou_termos = st.checkbox("Aceito os termos de uso e autorizo a análise dos meus dados de treino.")
                
                if st.button("Criar Minha Conta", use_container_width=True):
                    if nova_senha != confirmar_senha:
                        st.error("As senhas não coincidem.")
                    elif not aceitou_termos:
                        st.warning("Você precisa aceitar os termos para continuar.")
                    elif novo_nome and novo_email and nova_senha:
                        check = supabase.table("usuarios_app").select("id").eq("email", novo_email).execute()
                        if check.data:
                            st.error("Este e-mail já está cadastrado.")
                        else:
                            payload = {
                                "nome": novo_nome,
                                "email": novo_email,
                                "telefone": novo_tel,
                                "senha": hash_senha(nova_senha),
                                "is_admin": False,
                                "status_pagamento": False,
                                "data_vencimento": str(data_hoje)
                            }
                            supabase.table("usuarios_app").insert(payload).execute()
                            st.success("Conta criada! Agora faça login na aba 'Entrar'.")
                    else:
                        st.warning("Preencha todos os campos.")
    st.stop()

# --- VARIÁVEIS DE SESSÃO PÓS-LOGIN ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# =================================================================
# 👨‍🏫 VISÃO ADMINISTRADOR (TREINADOR)
# =================================================================
if eh_admin:
    with st.sidebar:
        st.title(f"👨‍🏫 {user['nome']}")
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logado = False
            st.rerun()
    
    st.title("🎮 Painel do Treinador")
    tab_fin, tab_treinos = st.tabs(["💰 Gestão Financeira", "📊 Análise de Performance"])
    
    with tab_fin:
        st.subheader("Controle de Acesso e Pagamentos")
        res_alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
        
        if res_alunos.data:
            df_fin = pd.DataFrame(res_alunos.data)
            for _, aluno in df_fin.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.markdown(f"**{aluno['nome']}**\n{aluno['email']}")
                    
                    status = "✅ Ativo" if aluno['status_pagamento'] else "❌ Bloqueado"
                    c2.write(f"Status: {status}")
                    
                    # Input de data direto na linha
                    nova_data = c3.date_input("Vencimento", value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d').date(), key=f"date_{aluno['id']}")
                    
                    if c4.button("Inverter Status", key=f"btn_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({
                            "status_pagamento": not aluno['status_pagamento'],
                            "data_vencimento": str(nova_data)
                        }).eq("id", aluno['id']).execute()
                        st.rerun()
        else:
            st.info("Nenhum aluno cadastrado.")

    with tab_treinos:
        st.write("Selecione um aluno na barra lateral para analisar dados do Strava.")

# =================================================================
# 🏃‍♂️ VISÃO ATLETA (CLIENTE)
# =================================================================
else:
    # Lógica de bloqueio por data e status
    venc_str = user.get('data_vencimento', '2000-01-01')
    venc_date = datetime.strptime(venc_str, '%Y-%m-%d').date()
    pago = user.get('status_pagamento', False) and data_hoje <= venc_date

    tab_treino, tab_pagamento = st.tabs(["🏃 Meus Treinos", "💳 Assinatura Pix"])

    with tab_treino:
        st.title(f"🚀 Fala, {user['nome']}!")
        
        if pago:
            st.success(f"Assinatura ativa até {venc_date.strftime('%d/%m/%Y')}")
            if st.button("🔄 Sincronizar Strava", type="primary"):
                res_t = supabase.table("usuarios").select("access_token", "strava_id").eq("nome", user['nome']).execute()
                if res_t.data:
                    if sincronizar_dados(res_t.data[0]['strava_id'], res_t.data[0]['access_token']):
                        st.success("Dados atualizados!")
                        st.rerun()
                else:
                    st.warning("Vincule seu Strava com o Fábio.")
        else:
            st.error("🚨 Sincronização bloqueada por falta de pagamento.")
            st.info("Regularize seu acesso na aba ao lado.")

    with tab_pagamento:
        st.header("💳 Pagamento via Pix")
        if pago:
            st.success("Tudo certo com sua conta!")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Chave Pix:** `seu-email@pix.com` (Copie e cole)")
                st.image("https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=CHAVE_PIX_EXEMPLO")
            with c2:
                if st.button("✅ Já realizei o pagamento"):
                    enviar_whatsapp(f"💰 O aluno {user['nome']} informou pagamento.", "5511999999999")
                    st.info("Avisamos o Fábio! Seu acesso será liberado em breve.")
