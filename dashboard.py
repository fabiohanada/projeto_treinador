import streamlit as st
import pandas as pd
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
    """Função robusta de envio via Twilio"""
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER") 
        
        if not sid or not token:
            st.error("Erro: Credenciais do Twilio ausentes.")
            return False

        client = Client(sid, token)
        
        # Limpa o número de destino: deixa só os números
        tel_limpo = ''.join(filter(str.isdigit, str(telefone_destino)))
        # Limpa o número de origem (Sandbox)
        p_from_limpo = p_from.replace("whatsapp:", "").replace("+", "").strip()
        
        message = client.messages.create(
            body=mensagem,
            from_=f"whatsapp:+{p_from_limpo}",
            to=f"whatsapp:+{tel_limpo}"
        )
        st.toast(f"✅ WhatsApp enviado! (ID: {message.sid[:8]})")
        return True
    except Exception as e:
        st.error(f"Erro no WhatsApp: {str(e)}")
        return False

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

# --- TELA DE LOGIN ---
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

# --- VARIÁVEIS DE USUÁRIO ---
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# =================================================================
# 👨‍🏫 VISÃO ADMINISTRADOR (TREINADOR)
# =================================================================
if eh_admin:
    with st.sidebar:
        st.title(f"👨‍🏫 Treinador: {user['nome']}")
        st.divider()
        
        # Conectar Atleta (Strava)
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
        st.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR NOVO ATLETA</div></a>', unsafe_allow_html=True)

        res_strava = supabase.table("usuarios").select("*").execute()
        
        if res_strava.data:
            atletas = {u['nome']: u for u in res_strava.data}
            sel = st.selectbox("Selecionar Aluno", list(atletas.keys()))
            atleta_foco = atletas[sel]
            
            st.divider()
            dias_filtro = st.radio("Período de Análise", [7, 30, 90, "Tudo"], index=1)
            
            # SINCRONIZAÇÃO E SAÍDA
            if st.button("🔄 Sincronizar Agora", use_container_width=True, type="primary"):
                if sincronizar_dados(atleta_foco['strava_id'], atleta_foco['access_token']):
                    enviar_whatsapp(f"✅ Treinos de {sel} atualizados com sucesso!", user['telefone'])
                    st.toast(f"Dados de {sel} sincronizados!")
                    st.rerun()
            
            if st.button("🚪 Sair do Sistema", use_container_width=True):
                st.session_state.logado = False
                st.rerun()

    # DASHBOARD PRINCIPAL
    if res_strava.data:
        st.title(f"📊 Dashboard: {sel}")
        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", atleta_foco['strava_id']).execute()
        
        if res_atv.data:
            df = pd.DataFrame(res_atv.data)
            df['dt'] = pd.to_datetime(df['data_treino'], utc=True)
            df = df.sort_values('dt')
            
            if dias_filtro != "Tudo":
                cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=int(dias_filtro))
                df = df[df['dt'] >= cutoff]

            # Cálculos ACWR
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            ultima_aguda = df['Aguda'].iloc[-1]
            ultima_cronica = df['Cronica'].iloc[-1]
            ratio = ultima_aguda / ultima_cronica if ultima_cronica > 0 else 0

            # MÉTRICAS DE TOPO
            m1, m2, m3 = st.columns(3)
            m1.metric("Carga Aguda", f"{ultima_aguda:.1f}")
            m2.metric("Carga Crônica", f"{ultima_cronica:.1f}")
            status = "PERIGO" if ratio > 1.5 else "OTIMIZADO" if 0.8 <= ratio <= 1.3 else "ALERTA"
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta=status, delta_color="normal" if status == "OTIMIZADO" else "inverse")

            # Alerta de Risco WhatsApp
            if ratio > 1.5:
                st.warning(f"🚨 {sel} está com carga muito alta!")
                if st.button(f"Enviar Alerta de Risco para {sel}"):
                    msg = f"Atenção {sel}, seu rácio de carga está em {ratio:.2f}. Sugerimos um treino regenerativo."
                    enviar_whatsapp(msg, user['telefone'])

            # META E GRÁFICOS
            st.divider()
            km_semana = df[df['dt'] >= (pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7))]['distancia'].sum()
            st.subheader(f"🏁 Meta Semanal: {km_semana:.1f}km / 40.0km")
            st.progress(min(km_semana/40.0, 1.0))

            c1, c2 = st.columns(2)
            df['data_f'] = df['dt'].dt.strftime('%d/%m')
            with c1:
                st.subheader("🗓️ Volume por Dia")
                st.bar_chart(df.groupby('data_f')['distancia'].sum())
            with c2:
                st.subheader("📈 Carga Aguda vs Crônica")
                st.line_chart(df.set_index('data_f')[['Aguda', 'Cronica']])

            st.subheader("📋 Últimos Treinos")
            df['Pace'] = df['trimp_score'] / df['distancia']
            st.dataframe(df[['data_f', 'tipo_esporte', 'distancia', 'Pace']].tail(5), use_container_width=True)
        else:
            st.info("Aguardando sincronização de treinos.")

# =================================================================
# 🏃‍♂️ VISÃO ATLETA (CLIENTE)
# =================================================================
else:
    with st.sidebar:
        st.title(f"🏃‍♂️ {user['nome']}")
        if st.button("🚪 Sair do Sistema", use_container_width=True):
            st.session_state.logado = False
            st.rerun()

    st.title(f"🚀 Fala, {user['nome']}!")
    meu_id = user.get('strava_id')
    if meu_id:
        res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", meu_id).execute()
        if res_atv.data:
            df = pd.DataFrame(res_atv.data)
            st.metric("Distância Acumulada", f"{df['distancia'].sum():.1f} km")
            st.area_chart(df.tail(15).set_index('data_treino')['distancia'])
        else: st.info("Seu treinador ainda não sincronizou seus dados.")
    else: st.warning("Vincule seu Strava com o treinador.")
