import requests

data = {
    'client_id': '197487',
    'client_secret': '2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f',
    'callback_url': 'https://gddseopytaabdxmgubzc.functions.supabase.co/strava-webhook',
    'verify_token': 'fabiostrava2026'
}

print("Enviando solicitação...")
response = requests.post('https://www.strava.com/api/v3/push_subscriptions', data=data)

print(f"Status: {response.status_code}")
print(f"Resposta: {response.text}")