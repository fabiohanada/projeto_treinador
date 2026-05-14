import time
import requests
from datetime import datetime, timedelta
import math
from supabase import create_client
import streamlit as st
import pandas as pd

# Importação da nossa nova lógica de tokens
from auth_strava import obter_token_valido

# Configurações lidas do st.secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"⚠️ ERRO Supabase: {e}")

def calcular_trimp_banister(duracao_min, fc_media, fc_max, fc_repouso=60):
    """Calcula a carga de treino baseada na FC Máxima individual do aluno."""
    if not fc_media or fc_media <= 0: 
        return int(duracao_min * 1.5)
    
    max_heart = fc_max if fc_max and fc_max > 0 else 185
    
    try:
        reserva = (fc_media - fc_repouso) / (max_heart - fc_repouso)
        reserva = max(0, min(reserva, 1)) 
        
        trimp = duracao_min * reserva * 0.64 * math.exp(1.92 * reserva)
        return int(trimp)
    except Exception as e:
        print(f"Erro no cálculo TRIMP: {e}")
        return int(duracao_min * 1.5)

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
            
            # --- BUSCA DADOS DO ALUNO ---
            u_info_db = supabase.table("usuarios_app").select("nome, telefone, bloqueado, data_vencimento, fc_maxima").eq("id", user_id).execute()
            
            if not u_info_db.data:
                continue
                
            u_data = u_info_db.data[0]
            hoje_date = datetime.now().date()
            fc_aluno = u_data.get('fc_maxima', 185)

            # --- CHECAGEM DE BLOQUEIO/VENCIMENTO ---
            try:
                venc_date = pd.to_datetime(u_data['data_vencimento']).date() if u_data['data_vencimento'] else hoje_date
            except:
                venc_date = hoje_date

            if u_data.get('bloqueado') or hoje_date > venc_date:
                print(f"🚫 [{tipo}] {u_data['nome']} ignorado (Bloqueado/Vencido).")
                continue 

            # --- OBTENÇÃO DO TOKEN (Lógica centralizada) ---
            token = obter_token_valido(user_id)
            if not token:
                print(f"⚠️ [{tipo}] Não foi possível validar token para {u_data['nome']}")
                continue

            # --- BUSCA NO STRAVA ---
            headers = {'Authorization': f'Bearer {token}'}
            after_date = int((datetime.now() - timedelta(days=2)).timestamp())
            atividades = requests.get(f"https://www.strava.com/api/v3/athlete/activities?after={after_date}", headers=headers).json()

            if isinstance(atividades, list):
                for act in atividades:
                    strava_id = str(act['id'])
                    nome_atividade = act.get('name', 'Treino')
                    fc_media = act.get('average_heartrate', 0) 
                    
                    existe = supabase.table("atividades_fisicas").select("id, notificacao").eq("strava_id", strava_id).execute()
                    
                    # Processa se for novo ou se clicou no botão (para forçar atualização)
                    if not existe.data or origem_botao:
                        dist = act.get('distance', 0) / 1000
                        dur_min = int(act.get('moving_time', 0) / 60)
                        
                        if dur_min < 5 and dist < 0.5: continue 

                        # CÁLCULO DE CARGA
                        if fc_media and fc_media > 0:
                            trimp_atual = calcular_trimp_banister(dur_min, fc_media, fc_aluno)
                            nota_manual = ""
                        else:
                            trimp_atual = int(dur_min * 1.5)
                            nota_manual = "\n\n⚠️ *Nota:* Treino sem dados de FC. Carga estimada pelo tempo."

                        t_semanal, t_mensal = buscar_acumulados_trimp(user_id, trimp_atual)

                        # SEMÁFORO DE CARGA
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
                            aviso_seg = f"\n\n⚠️ *Atenção:* Sua carga de {texto_alertas} está alta! Fale com o Prof. Fabio Hanada. 👊"

                        aviso_seg += nota_manual
                        data_bruta = act.get('start_date_local', '')
                        data_limpa = data_bruta[:10] if data_bruta else None

                        dados_banco = {
                            "id_atleta": user_id, 
                            "strava_id": strava_id,
                            "data_treino": data_limpa,
                            "distancia": round(dist, 2), 
                            "duracao": dur_min,
                            "name": nome_atividade,
                            "trimp_score": trimp_atual,
                            "trimp_semanal": t_semanal,
                            "trimp_mensal": t_mensal,
                            "notificacao": True
                        }

                        # ENVIO DE NOTIFICAÇÃO (Apenas se for novo)
                        if not existe.data:
                            supabase.table("atividades_fisicas").insert(dados_banco).execute()
                            
                            # Prepara dados para o template da mensagem
                            dados_notificacao = dados_banco.copy()
                            dados_notificacao.update({
                                "duracao_formatada": f"{dur_min//60:02d}:{dur_min%60:02d}",
                                "emoji_dia": emoji_dia,
                                "emoji_semana": emoji_sem,
                                "emoji_mensal": emoji_men,
                                "aviso_seguranca": aviso_seg
                            })
                            
                            from modules.views import enviar_notificacao_treino
                            enviar_notificacao_treino(dados_notificacao, u_data['nome'], u_data.get('telefone'))
                        else:
                            # Se já existe, apenas atualiza os números (útil se o aluno mudar o nome da atividade no Strava)
                            supabase.table("atividades_fisicas").update(dados_banco).eq("strava_id", strava_id).execute()

    except Exception as e:
        print(f"❌ Erro Fila: {e}")

if __name__ == "__main__":
    # Loop para rodar como serviço independente se necessário
    while True:
        processar_novos_treinos()
        time.sleep(300)