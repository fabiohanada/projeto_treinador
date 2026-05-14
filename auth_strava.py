import requests
import streamlit as st
from supabase import create_client
from datetime import datetime

# Inicializa o cliente Supabase para uso interno nas funções de token
def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def atualizar_token(user_id):
    """
    Busca o refresh_token no banco, pede um novo access_token ao Strava
    e atualiza o banco de dados.
    """
    supabase = get_supabase()
    
    # 1. Busca os dados atuais de auth para esse usuário
    res = supabase.table("auth_strava").select("*").eq("user_id", user_id).execute()
    
    if not res.data:
        print(f"❌ Usuário {user_id} não possui vínculo com Strava no banco.")
        return None
    
    dados_atuais = res.data[0]
    refresh_token_atual = dados_atuais['refresh_token']

    # 2. Faz a requisição de renovação para o Strava
    url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': st.secrets["STRAVA_CLIENT_ID"],
        'client_secret': st.secrets["STRAVA_CLIENT_SECRET"],
        'refresh_token': refresh_token_atual,
        'grant_type': 'refresh_token'
    }
    
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            novo_auth = response.json()
            
            # 3. Prepara os novos dados para salvar
            # O Strava pode devolver um NOVO refresh_token também, é importante salvar!
            novos_dados = {
                "access_token": novo_auth['access_token'],
                "refresh_token": novo_auth.get('refresh_token', refresh_token_atual),
                "expires_at": novo_auth['expires_at']
            }
            
            # 4. Atualiza o Supabase
            supabase.table("auth_strava").update(novos_dados).eq("user_id", user_id).execute()
            
            print(f"✅ Token renovado com sucesso para o usuário {user_id}")
            return novo_auth['access_token']
        else:
            print(f"❌ Erro ao renovar token no Strava: {response.json()}")
            return None
            
    except Exception as e:
        print(f"❌ Erro de conexão na renovação de token: {e}")
        return None

def obter_token_valido(user_id):
    """
    Função principal para ser usada nos seus outros módulos.
    Verifica se o token atual ainda é válido; se não, renova.
    """
    supabase = get_supabase()
    res = supabase.table("auth_strava").select("*").eq("user_id", user_id).execute()
    
    if not res.data:
        return None
        
    auth_data = res.data[0]
    # Verifica se expira nos próximos 5 minutos (margem de segurança)
    agora_timestamp = datetime.now().timestamp()
    
    if agora_timestamp > (auth_data['expires_at'] - 300):
        print(f"⏳ Token de {user_id} expirado ou perto de expirar. Renovando...")
        return atualizar_token(user_id)
    else:
        return auth_data['access_token']