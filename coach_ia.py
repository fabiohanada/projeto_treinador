import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Se você não tiver chave agora, o código vai imprimir o que seria enviado para a IA
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def gerar_orientacao_ia(nome_atleta, valor_acwr, status):
    # O "Prompt" é o segredo do sucesso de um SaaS de IA
    prompt = f"""
    Você é um treinador de elite de triatlo. 
    O seu atleta {nome_atleta} tem um ACWR (Acute:Chronic Workload Ratio) de {valor_acwr}.
    O status atual é: {status}.
    
    Escreva uma mensagem curta (máximo 3 frases) para o WhatsApp dele:
    1. Explique o que o número significa.
    2. Dê uma recomendação prática de treino para amanhã.
    3. Use um tom motivador mas profissional.
    """

    try:
        # Chamada real para a API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Você é um treinador olímpico."},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception:
        # Mock (Simulação) caso você esteja sem chave ou sem internet
        return f"Treinador diz: Olá {nome_atleta}! Seu rácio está em {valor_acwr}. {status}. Continue focado no plano!"

if __name__ == "__main__":
    # Testando a integração
    msg = gerar_orientacao_ia("Seu Nome", 1.1, "✅ SWEET SPOT (Evolução Segura)")
    print("\n--- MENSAGEM DO TREINADOR IA ---")
    print(msg)