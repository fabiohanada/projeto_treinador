from twilio.rest import Client
import os
from dotenv import load_dotenv

# Isso garante que o arquivo leia o seu .env
load_dotenv()

def enviar_whatsapp(mensagem, para_numero):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    
    # TESTE DE DEBUG: Se aparecer None no terminal, o erro está no .env
    # print(f"DEBUG SID: {account_sid}") 

    desde_numero = 'whatsapp:+14155238886' 
    
    try:
        # Se as variáveis estiverem vazias, o Client vai dar erro
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_=desde_numero,
            body=mensagem,
            to=f'whatsapp:{para_numero}'
        )
        return message.sid
    except Exception as e:
        print(f"Erro ao enviar WhatsApp: {e}")
        return None