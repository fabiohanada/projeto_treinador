import time
import requests
from datetime import datetime, timedelta
import math
from supabase import create_client
from twilio.rest import Client
import streamlit as st
import pandas as pd # Adicione esta importação para tratar datas

# Configurações lidas do st.secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"⚠️ ERRO Supabase: {e}")

def calcular_trimp_banister(duracao_min, fc_media, fc_max, fc_repouso=60):
    if not fc_media or fc_media <= 0: return int(duracao_min * 1.5)
    reserva = (fc_media - fc_repouso) / (fc_max - fc_repouso)
    try:
        trimp = duracao_min * reserva * 0.64 * math.exp(1.92 * reserva)
        return int(trimp)
    except: return int(duracao_min * 1.5)

def buscar_acumulados_trimp(user_id, trimp_atual):
    hoje = datetime.now()
    uma_semana = (hoje - timedelta(days=7)).strftime('%Y-%m-%d')
    um_mes = (hoje - timedelta(days=30)).strftime('%Y-%m-%d')

    res = supabase.table("atividades_fisicas").select("trimp_score, data_treino").eq("id_atleta", user_id).gte("data_treino", um_mes).execute()
    
    total_7d = trimp_atual
    total_30d = trimp_atual

    if res.data:
        for treino in res.data:
            score = treino.get('trimp_score', 0)
            data_t = treino.get('data_treino')
            if data_t >= uma_semana:
                total_7d += score
            total_30d += score
            
    return int(total_7d), int(total_30d)

def processar_novos_treinos(user_id_especifico=None, origem_botao=False):
    tipo = "BOTÃO" if origem_botao else "ROBÔ"
    print(f"🤖 [{tipo}] Iniciando verificação... {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        query = supabase.table("auth_strava").select("*")
        if user_id_especifico:
            query = query.eq("user_id", user_id_especifico)
        
        usuarios = query.execute().data
        if not usuarios: return

        for u in usuarios:
            user_id = u['user_id']
            
            # --- [NOVA TRAVA FINANCEIRA] ---
            # Busca os dados do usuário para checar bloqueio e vencimento
            u_info_db = supabase.table("usuarios_app").select("nome, telefone, bloqueado, data_vencimento").eq("id", user_id).execute()
            if u_info_db.data:
                u_data = u_info_db.data[0]
                hoje_date = datetime.now().date()
                
                # Converte data de vencimento
                try:
                    venc_date = pd.to_datetime(u_data['data_vencimento']).date() if u_data['data_vencimento'] else hoje_date
                except:
                    venc_date = hoje_date

                # Se estiver bloqueado ou vencido, pula o processamento deste usuário
                if u_data.get('bloqueado') or hoje_date > venc_date:
                    print(f"🚫 [{tipo}] {u_data['nome']} ignorado (Bloqueado ou Vencido).")
                    continue 
            # --- [FIM DA TRAVA] ---

            token = u['access_token']
            
            # Refresh Token
            if u.get('expires_at') and time.time() > (u['expires_at'] - 600):
                res_refresh = requests.post("https://www.strava.com/api/v3/oauth/token",
                    data={'client_id': st.secrets["STRAVA_CLIENT_ID"], 'client_secret': st.secrets["STRAVA_CLIENT_SECRET"],
                          'refresh_token': u['refresh_token'], 'grant_type': 'refresh_token'}).json()
                if 'access_token' in res_refresh:
                    token = res_refresh['access_token']
                    supabase.table("auth_strava").update({"access_token": token, "expires_at": res_refresh['expires_at']}).eq("user_id", user_id).execute()

            headers = {'Authorization': f'Bearer {token}'}
            after_date = int((datetime.now() - timedelta(days=2)).timestamp())
            atividades = requests.get(f"https://www.strava.com/api/v3/athlete/activities?after={after_date}", headers=headers).json()

            if isinstance(atividades, list):
                for act in atividades:
                    strava_id = str(act['id'])
                    existe = supabase.table("atividades_fisicas").select("id, notificacao").eq("strava_id", strava_id).execute()
                    ja_notificado = existe.data[0].get('notificacao', False) if existe.data else False

                    # --- [NOVA LÓGICA DO BOTÃO] ---
                    # Só entra se for treino novo OU se o botão foi clicado (para atualizar gráficos)
                    if not existe.data or origem_botao:
                        dist = act.get('distance', 0) / 1000
                        dur_min = int(act.get('moving_time', 0) / 60)
                        if dur_min < 5 and dist < 0.5: continue 

                        trimp_atual = calcular_trimp_banister(dur_min, act.get('average_heartrate', 0), 190)
                        t_semanal, t_mensal = buscar_acumulados_trimp(user_id, trimp_atual)

                        emoji_dia = "🟢" if trimp_atual <= 70 else "🟡" if trimp_atual <= 150 else "🔴"
                        emoji_sem = "🟢" if t_semanal <= 400 else "🟡" if t_semanal <= 800 else "🔴"
                        emoji_men = "🟢" if t_mensal <= 1500 else "🟡" if t_mensal <= 3000 else "🔴"

                        alertas = []
                        if emoji_dia == "🔴": alertas.append(f"Treino Atual ({trimp_atual})")
                        if emoji_sem == "🔴": alertas.append(f"Carga 7 dias ({t_semanal})")
                        if emoji_men == "🔴": alertas.append(f"Carga 30 dias ({t_mensal})")

                        aviso_seg = ""
                        if alertas:
                            texto_alertas = " e ".join(alertas)
                            aviso_seg = f"\n\n⚠️ *Atenção:* Sua carga de {texto_alertas} está alta! Se sentir dor ou cansaço excessivo, fale com o Prof. Fabio Hanada. 👊"

                        data_bruta = act.get('start_date_local', '')
                        data_limpa = data_bruta[:10] if data_bruta else None

                        dados_banco = {
                            "id_atleta": user_id, 
                            "strava_id": strava_id,
                            "data_treino": data_limpa,
                            "distancia": round(dist, 2), 
                            "duracao": dur_min,
                            "name": act.get('name'), 
                            "trimp_score": trimp_atual,
                            "trimp_semanal": t_semanal,
                            "trimp_mensal": t_mensal,
                            "notificacao": True
                        }

                        dados_notificacao = dados_banco.copy()
                        dados_notificacao.update({
                            "duracao_formatada": f"{dur_min//60:02d}:{dur_min%60:02d}",
                            "emoji_dia": emoji_dia,
                            "emoji_semana": emoji_sem,
                            "emoji_mensal": emoji_men,
                            "aviso_seguranca": aviso_seg
                        })
                        
                        if not existe.data:
                            supabase.table("atividades_fisicas").insert(dados_banco).execute()
                            # Notifica apenas treinos novos
                            from modules.views import enviar_notificacao_treino
                            enviar_notificacao_treino(dados_notificacao, u_data['nome'], u_data.get('telefone'))
                        else:
                            # Treino já existe: apenas atualiza os dados para o gráfico (sem enviar WhatsApp de novo)
                            supabase.table("atividades_fisicas").update(dados_banco).eq("strava_id", strava_id).execute()
                            print(f"📊 Dados de {u_data['nome']} atualizados via botão (sem novo Zap).")

    except Exception as e:
        print(f"❌ Erro Fila: {e}")

if __name__ == "__main__":
    while True:
        processar_novos_treinos()
        time.sleep(300)