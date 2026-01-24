import requests

# --- PREENCHA AQUI COM SEUS DADOS ---
CLIENT_ID = "197487"
CLIENT_SECRET = "2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f"
CALLBACK_URL = "https://projeto-treinador.onrender.com/webhook" # Verifique se termina com /webhook
VERIFY_TOKEN = "STRAVA"

def atualizar_webhook():
    # 1. Tentar deletar assinaturas antigas para limpar o caminho
    print("🔍 Buscando assinaturas existentes...")
    get_url = f"https://www.strava.com/api/v3/push_subscriptions?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}"
    subs = requests.get(get_url).json()
    
    if isinstance(subs, list) and len(subs) > 0:
        for s in subs:
            sub_id = s['id']
            print(f"🗑️ Deletando assinatura antiga ID: {sub_id}")
            requests.delete(f"https://www.strava.com/api/v3/push_subscriptions/{sub_id}?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}")
    else:
        print("✅ Nenhuma assinatura antiga encontrada.")

    # 2. Criar a nova assinatura apontando para o Render
    print(f"🚀 Criando nova assinatura para: {CALLBACK_URL}")
    dados = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'callback_url': CALLBACK_URL,
        'verify_token': VERIFY_TOKEN
    }
    
    resposta = requests.post("https://www.strava.com/api/v3/push_subscriptions", data=dados)
    print("📊 Resultado do Strava:", resposta.json())

if __name__ == "__main__":
    atualizar_webhook()