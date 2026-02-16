import requests

# DADOS REAIS DESCOBERTOS NO LOG
CLIENT_ID = '197487' 
CLIENT_SECRET = '2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f'
CALLBACK_URL = 'https://gddseopytaabdxmgubzc.functions.supabase.co/strava-webhook'
VERIFY_TOKEN = 'fabiostrava2026'

auth_params = {
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET
}

print(f"--- PASSO 1: Verificando assinaturas do App {CLIENT_ID} ---")
r_get = requests.get('https://www.strava.com/api/v3/push_subscriptions', params=auth_params)
subs = r_get.json()
print(f"Assinaturas encontradas: {subs}")

# Se tiver assinatura velha, apaga
if len(subs) > 0:
    old_id = subs[0]['id']
    print(f"\n--- PASSO 2: Apagando assinatura antiga (ID: {old_id}) ---")
    
    # O ID vai na URL, as credenciais nos parametros
    delete_url = f'https://www.strava.com/api/v3/push_subscriptions/{old_id}'
    r_del = requests.delete(delete_url, params=auth_params)
    
    if r_del.status_code == 204:
        print("✅ Assinatura antiga apagada com sucesso!")
    elif r_del.status_code == 404:
        print("⚠️ Erro 404: O Strava diz que não existe, mas listou antes. Pode ser 'Zombie Subscription'.")
    else:
        print(f"❌ Erro ao apagar: {r_del.status_code} - {r_del.text}")

print(f"\n--- PASSO 3: Criando Nova Assinatura no Supabase ---")
create_data = {
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'callback_url': CALLBACK_URL,
    'verify_token': VERIFY_TOKEN
}

# Tentamos criar a nova
r_post = requests.post('https://www.strava.com/api/v3/push_subscriptions', data=create_data)

print(f"STATUS FINAL: {r_post.status_code}")
print(f"RESPOSTA: {r_post.text}")

if r_post.status_code == 201:
    print("\n🎉🎉🎉 SUCESSO TOTAL! O SERVIDOR ESTÁ CONECTADO! 🎉🎉🎉")