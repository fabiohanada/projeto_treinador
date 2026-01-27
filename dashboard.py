import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
from twilio.rest import Client
import hashlib

# 1. CONFIGURAÇÕES INICIAIS
load_dotenv()
st.set_page_config(page_title="Seu Treino App", layout="wide")

def get_secret(key):
    try:
        if key in st.secrets: return st.secrets[key]
    except: pass
    return os.getenv(key)

# Conexões
supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))
CLIENT_ID = get_secret("STRAVA_CLIENT_ID")
CLIENT_SECRET = get_secret("STRAVA_CLIENT_SECRET")
REDIRECT_URI = "https://seu-treino-app.streamlit.app" 

# --- FUNÇÕES DE SEGURANÇA E COMUNICAÇÃO ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def enviar_whatsapp(mensagem, telefone):
    """Envia notificação via Twilio WhatsApp Sandbox com rastreio de erros."""
    try:
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        p_from = get_secret("TWILIO_PHONE_NUMBER")
        
        client = Client(sid, token)
        # Limpa o número (apenas dígitos)
        tel_limpo = ''.join(filter(str.isdigit, telefone))
        
        msg = client.messages.create(
            body=mensagem,
            from_=p_from,
            to=f"whatsapp:+{tel_limpo}"
        )
        return True
    except Exception as e:
        # Mostra o erro real na tela para sabermos por que não enviou
        st.error(f"Erro no WhatsApp: {e}")
        return False

def atualizar_token_strava(refresh_token, strava_id):
    """Renova o token do Strava usando o refresh_token."""
    url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token', 'refresh_token': refresh_token
    }
    res = requests.post(url, data=payload)
    if res.status_code == 200:
        novo_access = res.json()['access_token']
        supabase.table("usuarios").update({"access_token": novo_access}).eq("strava_id", strava_id).execute()
        return novo_access
    return None

def sincronizar_dados(strava_id, access_token, refresh_token, nome, telefone):
    """Puxa atividades do Strava e salva no Supabase."""
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        res = requests.get(url, headers=headers, params={'per_page': 10})
        
        # Se o token expirou (401), tenta renovar
        if res.status_code == 401:
            access_token = atualizar_token_strava(refresh_token, strava_id)
            if access_token:
                headers = {'Authorization': f'Bearer {access_token}'}
                res = requests.get(url, headers=headers, params={'per_page': 10})

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
                try:
                    supabase.table("atividades_fisicas").upsert(payload).execute()
                except:
                    continue # Pula se houver erro de duplicata ou banco
            
            if atividades:
                dist = atividades[0]['distance']/1000
                enviar_whatsapp(f"✅ Treino Sincronizado!\nAtleta: {nome}\nDistância: {dist:.2f}km", telefone)
            return True
        return False
    except Exception as e:
        st.error(f"Erro na sincronização: {e}")
        return False

# --- CONTROLE DE ACESSO (LOGIN) ---
if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🏃‍♂️ Seu Treino App")
        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        with tab1:
            e = st.text_input("E-mail", key="l_email")
            s = st.text_input("Senha", type="password", key="l_pass")
            if st.button("Acessar", use_container_width=True):
                u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                if u.data:
                    st.session_state.logado = True
                    st.session_state.user_info = u.data[0]
                    st.rerun()
                else: st.error("E-mail ou senha incorretos.")
        with tab2:
            n_c = st.text_input("Nome", key="c_nome")
            e_c = st.text_input("E-mail", key="c_email")
            t_c = st.text_input("WhatsApp (DDD+Número)", key="c_tel")
            s_c = st.text_input("Senha", type="password", key="c_pass")
            if st.button("Cadastrar", use_container_width=True):
                payload = {"nome": n_c, "email": e_c, "senha": hash_senha(s_c), "telefone": t_c, "is_admin": False}
                supabase.table("usuarios_app").insert(payload).execute()
                st.success("Conta criada! Faça login.")
    st.stop()

# --- DASHBOARD PRINCIPAL ---
st.sidebar.title(f"Olá, {st.session_state.user_info['nome']}")

# Botão Strava
auth_url = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"
st.sidebar.markdown(f'<a href="{auth_url}" target="_self" style="text-decoration:none;"><div style="background-color:#FC4C02;color:white;text-align:center;padding:12px;border-radius:8px;font-weight:bold;margin-bottom:20px;">🟠 CONECTAR AO STRAVA</div></a>', unsafe_allow_html=True)

# Seleção de Atleta
res_strava = supabase.table("usuarios").select("*").execute()
if res_strava.data:
    atletas = {u['nome']: u for u in res_strava.data}
    sel = st.sidebar.selectbox("Selecionar Atleta", list(atletas.keys()))
    d = atletas[sel]

    if st.sidebar.button("🔄 Sincronizar Agora", use_container_width=True):
        if sincronizar_dados(d['strava_id'], d['access_token'], d.get('refresh_token'), sel, st.session_state.user_info['telefone']):
            st.toast("Sucesso!")
            st.rerun()

    # --- ÁREA DE GRÁFICOS (LADO A LADO) ---
    res_atv = supabase.table("atividades_fisicas").select("*").eq("id_atleta", d['strava_id']).execute()
    if res_atv.data:
        df = pd.DataFrame(res_atv.data)
        df['dt_obj'] = pd.to_datetime(df['data_treino'])
        df['apenas_data'] = df['dt_obj'].dt.strftime('%d/%m/%Y')
        df = df.sort_values('dt_obj')

        # Criação das colunas para os gráficos ficarem um ao lado do outro
        graf_col1, graf_col2 = st.columns(2)

        with graf_col1:
            st.subheader("🗓️ Atividades por Dia")
            # Agrupa para remover repetições de horários e focar apenas no dia
            contagem = df.groupby('apenas_data').size()
            st.bar_chart(contagem)
        
        with graf_col2:
            st.subheader("📈 Carga Aguda vs Crônica")
            df['Aguda'] = df['trimp_score'].rolling(7, min_periods=1).mean()
            df['Cronica'] = df['trimp_score'].rolling(28, min_periods=1).mean()
            st.line_chart(df.set_index('apenas_data')[['Aguda', 'Cronica']])
    else:
        st.info("Nenhum treino encontrado. Conecte ou sincronize o Strava.")

st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()
