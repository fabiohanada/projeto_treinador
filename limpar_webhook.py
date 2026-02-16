import requests

# ID da assinatura velha que queremos apagar
subscription_id = '327002'

# Credenciais do DONO da assinatura (197487)
params = {
    'client_id': '197487', 
    'client_secret': '2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f'
}

print(f"Deletando assinatura {subscription_id}...")

# O ID precisa ir NA URL: .../push_subscriptions/327002
url = f'https://www.strava.com/api/v3/push_subscriptions/{subscription_id}'

response = requests.delete(url, params=params)

print(f"Status: {response.status_code}")
# Se retornar 204 = Sucesso!