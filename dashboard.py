import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v5.2 (NOTIFICAÇÃO VIA WHATSAPP TWILIO)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v5.2", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES SEGURAS ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
    
    # CREDENCIAIS TWILIO
    TWILIO_SID = st.secrets["TWILIO_ACCOUNT_SID"]
    TWILIO_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
    TWILIO_FROM = st.secrets["TWILIO_PHONE_NUMBER"] # Ex: +14155238886
    TWILIO_TO = st.secrets["MEU_CELULAR"]         # Teu número com +55...
except Exception as e:
    st.error("Erro nas Secrets. Verifique as chaves do Twilio e Supabase.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÃO DISPARO WHATSAPP ---
def enviar_whatsapp_notificacao(aluno_nome):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        # No WhatsApp do Twilio, é obrigatório o prefixo 'whatsapp:'
        msg_corpo = f"Fábio, novo pagamento detectado de {aluno_nome.upper()}. Confira no seu banco!"
        
        client.messages.create(
            from_=f"whatsapp:{TWILIO_FROM}",
            to=f"whatsapp:{TWILIO_TO}",
            body=msg_corpo
        )
    except Exception as e:
        # Silencioso para não travar o app do aluno
        pass

# --- FUNÇÃO DE ALERTA NO PAINEL ---
def notificar_pagamento_admin(aluno_nome_completo, aluno_email):
    try:
        # Verifica se já existe alerta pendente para não repetir SMS/WhatsApp
        check = supabase.table("alertas_admin").select("*").eq("email_aluno", aluno_email).eq("lida", False).execute()
        
        if not check.data:
            msg = f"Novo pagamento detectado {aluno_nome_completo.upper()}, por favor conferir na sua conta bancaria."
            supabase.table("alertas_admin").insert({
                "email_aluno": aluno_email, 
                "mensagem": msg, 
                "lida": False
            }).execute()
            
            # DISPARA O WHATSAPP
            enviar_whatsapp_notificacao(aluno_nome_completo)
    except: 
        pass

# --- RESTANTE DAS FUNÇÕES (IGUAL V5.0/V5.1) ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

def sincronizar_strava(auth_code, aluno_id):
    token_url = "https://www.strava.com/oauth/token"
    payload = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'code': auth_code, 'grant_type': 'authorization_code'}
    try:
        r = requests.post(token_url, data=payload).json()
        if 'access_token' in r:
            token = r['access_token']
            header = {'Authorization': f"Bearer {token}"}
            atividades = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=header).json()
            for act in atividades:
                if act['type'] == 'Run':
                    dados = {
                        "aluno_id": aluno_id, "data": act['start_date_local'][:10],
                        "nome_treino": act['name'], "distancia": round(act['distance'] / 1000, 2),
                        "tempo_min": round(act['moving_time'] / 60, 2), "fc_media": act.get('average_heartrate', 130),
                        "strava_id": str(act['id'])
                    }
                    supabase.table("treinos_alunos").upsert(dados, on_conflict="strava_id").execute()
            return True
    except: return False
    return False

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state: st.session_state.logado = False
params = st.query_params
if "code" in params and "user_mail" in params:
    u = supabase.table("usuarios_app").select("*").eq("email", params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]
        sincronizar_strava(params["code"], u.data[0]['id'])
        st.query_params.clear()
        st.query_params["user_mail"] = u.data[0]['email']

# --- LOGIN ---
if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        with st.form("login_form"):
            e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
            if st.form_submit_button("Acessar Painel", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado, st.session_state.user_info = True, u.data[0]
                    st.query_params["user_mail"] = e
                    st.rerun()
                else: st.error("Dados incorretos.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if not eh_admin:
        redirect_com_email = f"{REDIRECT_URI}?user_mail={user['email']}"
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={urllib.parse.quote(redirect_com_email)}&scope=activity:read_all&approval_prompt=auto"
        st.markdown(f'''<a href="{link_strava}" target="_self" style="text-decoration: none;"><div style="background-color: #FC4C02; color: white; padding: 12px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 20px;">🟠 ATUALIZAR TREINOS (STRAVA)</div></a>''', unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.clear(); st.query_params.clear(); st.rerun()

# --- PAINEL ADMIN ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    st.subheader("🔔 Notificações de Pagamento")
    try:
        res_alertas = supabase.table("alertas_admin").select("*").eq("lida", False).order("created_at", desc=True).execute()
        if res_alertas.data:
            for a in res_alertas.data:
                st.error(f"🚨 {a['mensagem']}")
            if st.button("Marcar todos como lidos", type="primary"):
                supabase.table("alertas_admin").update({"lida": True}).eq("lida", False).execute()
                st.rerun()
        else: st.info("Nenhum pagamento novo pendente.")
        if st.button("🔄 Atualizar Lista"): st.rerun()
    except: st.warning("Aguardando inicialização da tabela...")

    st.divider()
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1.5])
            with col1:
                st.markdown(f"#### {aluno['nome']}")
                st.markdown(f"**Status:** {'✅ Ativo' if aluno['status_pagamento'] else '❌ Bloqueado'}")
            with col2:
                dt_banco = aluno.get('data_vencimento')
                try: val_data = datetime.strptime(str(dt_banco), '%Y-%m-%d').date() if dt_banco and str(dt_banco) != "None" else date.today()
                except: val_data = date.today()
                nova_dt = st.date_input("Vencimento", value=val_data, key=f"dt_{aluno['id']}")
            with col3:
                if st.button("💾 Salvar Data", key=f"sv_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt)}).eq("id", aluno['id']).execute()
                    st.success("Salvo!")
                label_btn = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                if st.button(label_btn, key=f"ac_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

# --- PAINEL ALUNO ---
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento', False):
        notificar_pagamento_admin(user['nome'], user['email'])
        st.error("⚠️ Acesso pendente de pagamento.")
        with st.expander("💳 Dados para Pagamento PIX", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.info(f"**Chave PIX:** {chave_pix_visivel}")
            st.code(pix_copia_e_cola)
        st.stop()
    
    st.info(f"📅 Plano ativo até: **{formatar_data_br(user.get('data_vencimento'))}**")
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['TRIMP'] = df['tempo_min'] * (df['fc_media'] / 100)
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df, x='data', y='TRIMP', title="Carga (TRIMP)", color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with c2:
            fig = px.line(df, x='data', y='fc_media', title="FC Média", markers=True)
            fig.add_hline(y=130, line_dash="dash", line_color="green")
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[['data', 'nome_treino', 'distancia', 'tempo_min', 'fc_media', 'TRIMP']], use_container_width=True, hide_index=True)
    else: st.warning("Nenhum treino encontrado. Use o botão laranja!")
