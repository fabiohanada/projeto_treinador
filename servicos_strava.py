import requests
import os

def buscar_detalhes_treino(id_atividade, access_token):
    """Vai até o Strava e busca os batimentos cardíacos"""
    url = f"https://www.strava.com/api/v3/activities/{id_atividade}"
    headers = {'Authorization': f'Bearer {access_token}'}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        dados = response.json()
        # Extraímos o que interessa para a Folha 2
        info_treino = {
            "duracao_min": round(dados.get("moving_time") / 60, 2),
            "fc_media": dados.get("average_heartrate"),
            "nome": dados.get("name")
        }
        return info_treino
    else:
        print(f"Erro ao buscar treino: {response.status_code}")
        return None