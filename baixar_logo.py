import requests

# URL oficial do logo do Strava
url = "https://raw.githubusercontent.com/strava/api/master/docs/images/api_logo_pwrdBy_strava_horiz_light.png"

print("Baixando logo do Strava...")
response = requests.get(url)

if response.status_code == 200:
    with open("strava_logo.png", "wb") as file:
        file.write(response.content)
    print("Sucesso! O arquivo 'strava_logo.png' foi salvo na pasta.")
else:
    print("Erro ao baixar. Verifique sua internet.")