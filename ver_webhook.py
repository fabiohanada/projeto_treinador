import requests

params = {
    'client_id': '197487',
    'client_secret': '2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f'
}

print("Consultando assinaturas ativas...")
response = requests.get('https://www.strava.com/api/v3/push_subscriptions', params=params)

print(f"Status: {response.status_code}")
print(f"Sua Assinatura: {response.json()}")