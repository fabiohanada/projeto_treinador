import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib

# 1. CONFIGURAÇÕES E CONSTANTES GLOBAIS
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        if key in st.secrets: return st.secrets[key]
    except: pass
    return os.getenv(key)

# Inicialização Supabase
supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))

# Configurações Strava
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES DE COMUNICAÇÃO ---

def formatar_whatsapp_destino(telefone):
    """Garante que o número seja apenas dígitos e tenha o prefixo correto."""
    apenas_numeros = ''.join(filter(str.isdigit, str(telefone)))
    return f"whatsapp:+{apenas_numeros}"

def enviar_whatsapp(mensagem, telefone_cru):
    """Envia a mensagem tratando possíveis erros 400 da API do Twilio."""
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        phone_from = get_secret("TWILIO_PHONE_NUMBER")
        
        # Garante que o remetente tenha o prefixo 'whatsapp:'
        if not str(phone_from).startswith("whatsapp:"):
            phone_from = f"whatsapp:{phone_from}"
            
        destinatario = formatar_whatsapp_destino(telefone_cru)
        
        client = Client(sid, token)
        msg = client.messages.create(
            body=mensagem,
            from_=phone_from,
            to=destinatario
        )
        st.sidebar.success(f"Notificação enviada! (SID: {msg.sid[:10]}...)")
        return True
    except Exception as e:
        # Aqui capturamos o erro 400 detalhado
        st.sidebar.error(f"Falha no WhatsApp: {e}")
        return False

# --- FUNÇÕES DE DADOS ---

def atualizar_token_strava(refresh_token, strava_id):
    url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID, 
        'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token', 
        'refresh_token': refresh_token
    }
    res = requests.post(url, data=payload)
    if res.status_code == 200:
        novo_access = res.json()['access_token']
        supabase.table("usuarios").update({"access_token": novo_access}).eq("strava_id", strava_id).execute()
        return novo_access
    return None

def sincronizar_dados(strava_id, access_token, refresh_token, nome_atleta, tel_usuario):
    url_atividades = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        res = requests.get(url_atividades, headers=headers, params={'per_page': 5})
        
        # Se expirar, renova e tenta de novo
        if res.status_code == 401:
            novo_token = atualizar_token_strava(refresh_token, strava_id)
            if novo_token:
                headers = {'Authorization': f'Bearer {novo_token}'}
                res = requests.get(url_atividades, headers=headers, params={'per_page': 5})
            else:
                return False

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
                # Upsert seguro
                try:
                    supabase.table("atividades_fisicas").upsert(payload).execute()
                except: continue
            
            if atividades:
                dist_km = atividades[0]['distance'] / 1000
                texto_msg = f"🏃‍♂️ *Treino Sincronizado!*\n\nAtleta: {nome_atleta}\nDistância: {dist_km:.2f}km\nData: {atividades[0]['start_date_local'][:10]}"
                enviar_whatsapp(texto_msg, tel_usuario)
            return True
        return False
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")
        return False

# --- INTERFACE DE ACESSO ---

if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🛡️ Sistema de Monitoramento")
    col1, col2 = st.columns(2)
    with col1:
        e = st.text_input("E-mail")
        s = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            senha_h = hashlib.sha256(str.encode(s)).hexdigest()
            u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", senha_h).execute()
            if u.data:
                st.session_state.logado = True
                st.session_state.user_info = u.data[0]
                st.rerun()
            else: st.error("Acesso negado.")
    st.stop()

# --- DASHBOARD LOGADO ---

st.sidebar.title(f"Treinador: {st.session_state.user_info['nome']}")

# Botão Strava
st.sidebar.markdown(f'''
    <a href="https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all" target="_self" style="text-decoration:none;">
        <div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">
            🟠 CONECTAR AO STRAVA
        </div>
    </a>
''', unsafe_allow_html=True)

# Lista de Atletas do Banco
res_atleta = supabase.table("usuarios").select("*").execute()

if res_atleta.data:
    lista_atletas = {at['nome']: at for at in res_atleta.data}
    atleta_nome = st.sidebar.selectbox("Escolha o Atleta", list(lista_atletas.keys()))
    dados_atleta = lista_atletas[atleta_nome]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        with st.spinner("Buscando dados no Strava..."):
            if sincronizar_dados(
                dados_atleta['strava_id'], 
                dados_atleta['access_token'], 
                dados_atleta.get('refresh_token'), 
                atleta_nome, 
                st.session_state.user_info['telefone']
            ):
                st.toast("Gráficos atualizados!")
                st.rerun()

    # --- VISUALIZAÇÃO DOS GRÁFICOS (LADO A LADO) ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", dados_atleta['strava_id']).execute()
    
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['dt_raw'] = pd.to_datetime(df['data_treino'])
        df['data_eixo_x'] = df['dt_raw'].dt.strftime('%d/%m/%Y')
        df = df.sort_values('dt_raw')

        # Layout de Colunas
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🗓️ Volume por Dia")
            contagem = df.groupby('data_eixo_x').size()
            st.bar_chart(contagem)
            
        with c2:
            st.subheader("📈 Carga Aguda vs Crônica")
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            st.line_chart(df.set_index('data_eixo_x')[['Aguda', 'Cronica']])
    else:
        st.info("Nenhum treino registrado para este atleta.")

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
