import hashlib
from datetime import datetime
import streamlit as st
from twilio.rest import Client

# URL de retorno do seu site (ajuste se mudar o nome do app no Streamlit Cloud)
REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
PIX_COPIA_COLA = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37"

def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try:
        return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except:
        return str(data_str)

def enviar_whatsapp(numero_destino, mensagem):
    """Envia alerta via Twilio para o seu WhatsApp."""
    try:
        # Pega as chaves das Secrets
        sid = st.secrets["TWILIO_ACCOUNT_SID"]
        token = st.secrets["TWILIO_AUTH_TOKEN"]
        origem = st.secrets["TWILIO_PHONE_NUMBER"] # O número do Twilio
        
        client = Client(sid, token)
        
        # Garante o formato 'whatsapp:+55...'
        if not numero_destino.startswith("whatsapp:"):
            numero_destino = f"whatsapp:{numero_destino}"
            
        message = client.messages.create(
            body=mensagem,
            from_=origem,
            to=numero_destino
        )
        return True, message.sid
    except Exception as e:
        return False, str(e)