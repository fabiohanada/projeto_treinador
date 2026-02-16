import requests

# ---------------------------------------------------------
# AQUI VOCÊ VAI COLAR O CÓDIGO QUE VAI PEGAR NO NAVEGADOR
# (Lembre-se: O código muda toda vez, pegue um novo agora!)
CODIGO_DO_NAVEGADOR = "82c2838bf64d6f5473b13e9da96e6a48fd648034" 
# ---------------------------------------------------------

# Seus dados (Já preenchi para facilitar)
CLIENT_ID = '197487' 
CLIENT_SECRET = '2d7e380d8348b5ea2a8e4adf64fdcd69b2ef116f'

print("Trocando o código pelo Refresh Token...")

response = requests.post(
    'https://www.strava.com/oauth/token',
    data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': CODIGO_DO_NAVEGADOR,
        'grant_type': 'authorization_code'
    }
)

dados = response.json()

if response.status_code == 200:
    print("\n✅ SUCESSO! GUARDE ESTE NÚMERO COM A VIDA:")
    print(f"REFRESH_TOKEN: {dados['refresh_token']}")
    print("-" * 30)
    print("Agora você pode usar esse token no seu robô para sempre!")
else:
    print("\n❌ Erro ao pegar token:")
    print(dados)