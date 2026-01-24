import os
import requests
import math
import uvicorn
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from supabase import create_client
from auth_strava import atualizar_token 
from notificador_whatsapp import enviar_whatsapp

load_dotenv()

app = FastAPI()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def calcular_trimp_direto(duracao_seg, fc_media):
    """Calcula o TRIMP (Esforço) baseado na duração e FC média"""
    duracao_min = duracao_seg / 60
    fc_repouso = 55
    fc_maxima = 190
    
    # Intensidade (Reserva Cardíaca)
    v_intensidade = (fc_media - fc_repouso) / (fc_maxima - fc_repouso)
    # Fórmula de Banister
    trimp = duracao_min * v_intensidade * (0.64 * math.exp(1.92 * v_intensidade))
    return round(trimp, 2)

@app.get("/webhook")
async def validar_webhook(request: Request):
    params = request.query_params
    challenge = params.get("hub.challenge")
    token = params.get("hub.verify_token")
    
    # O Strava exige que você retorne exatamente o challenge que ele enviou
    if token == "STRAVA":
        return {"hub.challenge": challenge}
    
    return {"status": "token invalido"}

@app.post("/webhook")
async def receber_evento_strava(request: Request):
    dados = await request.json()
    
    if dados.get("object_type") == "activity":
        id_atividade = dados.get("object_id")
        print(f"🔱 Nova atividade detectada! ID: {id_atividade}")

        token_valido = atualizar_token()
        
        if token_valido:
            url_strava = f"https://www.strava.com/api/v3/activities/{id_atividade}"
            headers = {'Authorization': f'Bearer {token_valido}'}
            resp = requests.get(url_strava, headers=headers)
            
            if resp.status_code == 200:
                info = resp.json()
                nome_treino = info.get("name")
                duracao_seg = info.get("moving_time")
                fc_media = info.get("average_heartrate")

                # AJUSTE PARA TESTE: Se não houver FC, define 130 para não ignorar o treino
                if not fc_media:
                    print(f"⚠️ Treino '{nome_treino}' sem batimentos. Usando 130bpm para teste.")
                    fc_media = 130

                # Agora o processo continua sempre
                score = calcular_trimp_direto(duracao_seg, fc_media)
                
                # Arredondando para inteiros para evitar erro de sintaxe no banco
                dados_treino = {
                    "id_atleta": "7b606745-96e8-446f-8576-a18a3b4abf30",
                    "duracao_min": int(duracao_seg / 60), # Convertido para INT
                    "fc_media": int(fc_media),           # Convertido para INT
                    "trimp_score": int(score),           # Convertido para INT
                    "data_treino": "now()" 
                }
                
                try:
                    supabase.table("atividades_fisicas").insert(dados_treino).execute()
                    print(f"✅ Treino '{nome_treino}' salvo no Supabase! TRIMP: {score}")

                    msg = (f"🚀 *Treino Sincronizado!*\n\n"
                           f"🏃‍♂️ Atividade: *{nome_treino}*\n"
                           f"📊 Esforço: *{score} TRIMP*\n"
                           f"⏱️ Duração: {round(duracao_seg/60, 1)} min\n\n"
                           f"🔗 Veja sua evolução no Dashboard!")
                    
                    # Envia a notificação
                    enviar_whatsapp(msg, "+5511969603611") 
                    print("📲 WhatsApp enviado!")

                except Exception as e:
                    print(f"❌ Erro ao salvar/notificar: {e}")
            else:
                print(f"❌ Erro Strava: {resp.status_code}")
                
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)