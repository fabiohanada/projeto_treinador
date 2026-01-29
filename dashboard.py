import streamlit as st
import pandas as pd  # <--- Corrigido aqui (estava apenas 'pd')
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client

# ==========================================
# VERSÃO: v3.9 (CORREÇÃO DE IMPORT + NOME COMPLETO)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v3.9", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES SEGURAS ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
except Exception as e:
    st.error("Erro nas Secrets.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): 
    return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

def notificar_pagamento_admin(aluno_nome_completo, aluno_email):
    try:
        supabase.table("alertas_admin").insert({
            "mensagem": f"O ALUNO: {aluno_nome_completo.upper()} acessou a área de pagamento PIX.",
            "lida": False,
            "email_aluno": aluno_email
        }).execute()
    except: pass 

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

# --- LOGICA DE LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if "code" in st.query_params: st.session_state.strava_code = st.query_params["code"]

if "user_mail" in st.query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", st.query_params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]

if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Aluno"])
        with tab_login:
            with st.form("login_form"):
                e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Painel", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.query_params["user_mail"] = e
                        st.rerun()
                    else: st.error("Dados incorretos.")
        with tab_cadastro:
            with st.form("cadastro_form"):
                n_c, e_c, s_c = st.text_input("Nome Completo"), st.text_input("E-mail"), st.text_input("Senha", type="password")
                lgpd = st.checkbox("Li e aceito os Termos de Uso e LGPD.")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    if lgpd and n_c and e_c and s_c:
                        try:
                            supabase.table("usuarios_app").insert({"nome": n_c, "email": e_c, "senha": hash_senha(s_c), "status_pagamento": False, "data_vencimento": str(date.today())}).execute()
                            st.success("Cadastrado! Faça login.")
                        except: st.error("Erro no cadastro.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if not eh_admin:
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope=activity:read_all&approval_prompt=force"
        st.markdown(f'''<a href="{link_strava}" target="_blank" style="text-decoration: none;"><div style="background-color: #FC4C02; color: white; padding: 12px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 20px;">🟠 CONECTAR COM STRAVA</div></a>''', unsafe_allow_html=True)
        if "strava_code" in st.session_state:
            if sincronizar_strava(st.session_state.strava_code, user['id']):
                st.success("Sincronizado!"); del st.session_state.strava_code; st.rerun()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.clear(); st.query_params.clear(); st.rerun()

# --- PAINEL ADMIN (TRANCADO) ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    try:
        alertas = supabase.table("alertas_admin").select("*").eq("lida", False).execute()
        if alertas.data:
            st.warning(f"🔔 Você tem {len(alertas.data)} novos avisos de acesso ao PIX!")
            if st.button("Limpar Alertas"):
                supabase.table("alertas_admin").update({"lida": True}).eq("lida", False).execute()
                st.rerun()
    except: pass 

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
                    st.success("Ok!")
                label_btn = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar Acesso"
                if st.button(label_btn, key=f"ac_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

# --- PAINEL ALUNO ---
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    pago = user.get('status_pagamento', False)
    if not pago:
        notificar_pagamento_admin(user['nome'], user['email'])
        st.error("⚠️ Seu acesso está pendente de renovação ou pagamento.")
        with st.expander("💳 Dados para Pagamento PIX", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.info(f"**Chave PIX (E-mail):** {chave_pix_visivel}")
            st.code(pix_copia_e_cola, language="text")
        st.stop()

    st.info(f"📅 Seu plano vence em: **{formatar_data_br(user.get('data_vencimento'))}**")
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
    else:
        st.warning("Conecte ao Strava na lateral!")
