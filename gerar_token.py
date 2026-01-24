import requests

# Seus dados que já vimos no seu .env
client_id = "197487"
client_secret = "2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f"

# 1. COLOQUE AQUI o código que você pegou na URL do navegador após autorizar
# (Aquele que fica depois de code=...)
codigo_da_url = "b72ff4f694ea0dabaa158d0d065746017efb80a4"

url = "https://www.strava.com/oauth/token"
payload = {
    "client_id": client_id,
    "client_secret": client_secret,
    "code": codigo_da_url,
    "grant_type": "authorization_code"
}

response = requests.post(url, data=payload)
print(response.json())