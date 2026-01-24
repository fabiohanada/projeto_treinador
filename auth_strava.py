import requests
import os
from dotenv import load_dotenv

load_dotenv()

def atualizar_token():
    url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': os.getenv("STRAVA_CLIENT_ID"),
        'client_secret': os.getenv("STRAVA_CLIENT_SECRET"),
        'refresh_token': os.getenv("STRAVA_REFRESH_TOKEN"),
        'grant_type': 'refresh_token'
    }
    
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            print(f"❌ Erro Strava: {response.json()}")
            return None
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return None