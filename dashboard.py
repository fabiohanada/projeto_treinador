import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib

# 1. CONFIGURAÇÕES
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        if key in st.secrets: return st.secrets[key]
    except: pass
    return os.getenv(key)

supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
if not st.session_state.logado:
    st.title("🏃‍♂️ Acesso ao Sistema")
    e = st.text_input("E-mail")
    s = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True):
        senha_h = hashlib.sha256(str.encode(s)).hexdigest()
        u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", senha_h).execute()
        if u.data:
            st.session_state.logado, st.session_state.user_info = True, u.data[0]
            st.rerun()
    st.stop()

# --- SIDEBAR FIXO ---
st.sidebar.title(f"Treinador: {st.session_state.user_info['nome']}")
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR NOVO ATLETA</div></a>', unsafe_allow_html=True)

# --- DASHBOARD ---
res_strava = supabase.table("usuarios").select("*").execute()

if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    sel = st.sidebar.selectbox("Selecionar Atleta", list(atletas.keys()))
    d = atletas[sel]

    dias_filtro = st.sidebar.radio("Período de Análise", [7, 30, 90, "Tudo"], index=1)

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        st.toast("Sincronizando...")
        # (A lógica de sincronizar_dados deve estar definida ou chamada aqui)
        st.rerun()

    # --- PROCESSAMENTO DE DADOS ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        # CONVERSÃO PARA DATETIME COM UTC FORÇADO
        df['dt'] = pd.to_datetime(df['data_treino'], utc=True)
        df = df.sort_values('dt')
        
        # Filtro de tempo com Timezone Awareness
        if dias_filtro != "Tudo":
            cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=int(dias_filtro))
            df = df[df['dt'] >= cutoff]

        if not df.empty:
            # Cálculos de Carga
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            ultima_aguda = df['Aguda'].iloc[-1]
            ultima_cronica = df['Cronica'].iloc[-1]
            ratio = ultima_aguda / ultima_cronica if ultima_cronica > 0 else 0

            st.markdown(f"## 📊 Dashboard: {sel}")
            
            # MÉTRICAS
            m1, m2, m3 = st.columns(3)
            m1.metric("Carga Aguda (7d)", f"{ultima_aguda:.1f}")
            m2.metric("Carga Crônica (28d)", f"{ultima_cronica:.1f}")
            status_acwr = "PERIGO" if ratio > 1.5 else "OTIMIZADO" if 0.8 <= ratio <= 1.3 else "ALERTA"
            m3.metric("Rácio ACWR", f"{ratio:.2f}", delta=status_acwr, delta_color="normal" if status_acwr == "OTIMIZADO" else "inverse")

            # META SEMANAL
            st.divider()
            meta_km = 40.0
            inicio_semana = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7)
            km_na_semana = df[df['dt'] >= inicio_semana]['distancia'].sum()
            progresso = min(km_na_semana / meta_km, 1.0)
            st.subheader(f"🏁 Meta Semanal: {km_na_semana:.1f}km / {meta_km}km")
            st.progress(progresso)

            # GRÁFICOS
            df['data_f'] = df['dt'].dt.strftime('%d/%m/%Y')
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🗓️ Volume por Dia")
                st.bar_chart(df.groupby('data_f')['distancia'].sum())
            with c2:
                st.subheader("📈 Carga Aguda vs Crônica")
                st.line_chart(df.set_index('data_f')[['Aguda', 'Cronica']])

            # TABELA
            st.subheader("📋 Últimos Treinos")
            df['Pace'] = df['trimp_score'] / df['distancia']
            tabela_view = df[['data_f', 'tipo_esporte', 'distancia', 'trimp_score', 'Pace']].tail(5).copy()
            st.dataframe(tabela_view, use_container_width=True)
        else:
            st.warning("Sem dados para o período selecionado.")
    else:
        st.info("Nenhum treino encontrado.")

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
