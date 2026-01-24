import requests

# Dados do seu painel no Strava (https://www.strava.com/settings/api)
CLIENT_ID = "197487"
CLIENT_SECRET = "2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f"
VERIFY_TOKEN = "MEU_TOKEN_SECRETO_ADS" # O mesmo que você colocou no api_strava.py
CALLBACK_URL = "https://donnette-unennobling-dilutely.ngrok-free.dev/webhook"

url = "https://www.strava.com/api/v3/push_subscriptions"

payload = {
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'callback_url': CALLBACK_URL,
    'verify_token': VERIFY_TOKEN
}

response = requests.post(url, data=payload)

print(f"Status Code: {response.status_code}")
print(f"Resposta: {response.json()}")