import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timedelta

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def calcular_diagnostico_acwr(id_atleta):
    # 1. Definir datas (7 dias e 28 dias atrás)
    hoje = datetime.now()
    sete_dias_atras = (hoje - timedelta(days=7)).isoformat()
    vinte_oito_dias_atras = (hoje - timedelta(days=28)).isoformat()

    # 2. Buscar carga Aguda (Últimos 7 dias)
    res_aguda = supabase.table("atividades_fisicas") \
        .select("trimp_score") \
        .eq("id_atleta", id_atleta) \
        .gte("data_treino", sete_dias_atras) \
        .execute()
    
    carga_aguda = sum([item['trimp_score'] for item in res_aguda.data]) / 7

    # 3. Buscar carga Crônica (Últimos 28 dias)
    res_cronica = supabase.table("atividades_fisicas") \
        .select("trimp_score") \
        .eq("id_atleta", id_atleta) \
        .gte("data_treino", vinte_oito_dias_atras) \
        .execute()
    
    carga_cronica = sum([item['trimp_score'] for item in res_cronica.data]) / 28

    # 4. Cálculo do ACWR (Rácio)
    if carga_cronica == 0: return 1.0, "Iniciando histórico..."
    
    acwr = round(carga_aguda / carga_cronica, 2)

    # 5. Lógica de Decisão (A cor do semáforo da Folha 3)
    if acwr < 0.8:
        status = "🟢 SUBTREINAMENTO (Pode acelerar!)"
    elif 0.8 <= acwr <= 1.3:
        status = "✅ SWEET SPOT (Evolução Segura)"
    elif 1.3 < acwr <= 1.5:
        status = "⚠️ ALERTA (Risco moderado de lesão)"
    else:
        status = "🚨 PERIGO (Risco alto de lesão! Descanse)"
    
    return acwr, status

if __name__ == "__main__":
    MEU_ID = "7b606745-96e8-446f-8576-a18a3b4abf30"
    valor, msg = calcular_diagnostico_acwr(MEU_ID)
    
    print("-" * 30)
    print(f"RELATÓRIO DE ELITE")
    print("-" * 30)
    print(f"Seu ACWR atual: {valor}")
    print(f"Diagnóstico: {msg}")
    print("-" * 30)