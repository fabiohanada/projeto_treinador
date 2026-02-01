import requests
import numpy as np
from datetime import datetime, timedelta

def buscar_e_salvar_treinos(supabase, access_token, user_id):
    url = "https://www.strava.com/api/v3/athlete/activities?per_page=30"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            atividades = response.json()
            dados = []
            hr_max, hr_rest = 190, 60
            for atv in atividades:
                fc = atv.get("average_heartrate", 0)
                dur = atv["moving_time"] / 60
                trimp = 0
                if fc > 0:
                    hrr = (fc - hr_rest) / (hr_max - hr_rest)
                    trimp = dur * hrr * (0.64 * np.exp(1.92 * hrr))
                dados.append({
                    "aluno_id": user_id, "strava_id": str(atv["id"]), "nome": atv["name"],
                    "data": atv["start_date_local"][:10], "distancia": round(atv["distance"] / 1000, 2),
                    "tempo_segundos": atv["moving_time"], "fc_media": fc, "trimp": round(trimp, 2)
                })
            if dados:
                supabase.table("treinos_alunos").upsert(dados, on_conflict="strava_id").execute()
                supabase.table("usuarios_app").update({"ultimo_sync": datetime.now().isoformat()}).eq("id", user_id).execute()
            return True
    except: return False

def verificar_necessidade_update(supabase, user):
    ultimo = user.get("ultimo_sync")
    token = user.get("strava_access_token")
    if not token: return False
    if not ultimo or (datetime.now() - datetime.fromisoformat(ultimo) > timedelta(hours=1)):
        return buscar_e_salvar_treinos(supabase, token, user["id"])
    return False