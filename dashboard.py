import streamlit as st
import pandas as pd
import os
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt

load_dotenv()

# Conectar ao banco
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

st.set_page_config(page_title="Elite Performance Dashboard", layout="wide")
st.title("🚀 Painel de Performance de Elite")

# 1. Buscar dados do Supabase
def carregar_dados():
    response = supabase.table("atividades_fisicas").select("*").execute()
    
    if not response.data:
        return pd.DataFrame()
    
    df = pd.DataFrame(response.data)
    
    # Ajuste aqui: trocamos 'created_at' por 'data_treino'
    if 'data_treino' in df.columns:
        df['data_treino'] = pd.to_datetime(df['data_treino'])
        df = df.sort_values('data_treino')
    else:
        st.error("Coluna 'data_treino' não encontrada no banco!")
        
    return df

df_treinos = carregar_dados()

if not df_treinos.empty:
    # 2. Cálculos para o Gráfico
    # Média de 7 dias (Agudo) e 28 dias (Crônico)
    df_treinos['Carga_Aguda'] = df_treinos['trimp_score'].rolling(window=7, min_periods=1).mean()
    df_treinos['Carga_Cronica'] = df_treinos['trimp_score'].rolling(window=28, min_periods=1).mean()
    df_treinos['ACWR'] = df_treinos['Carga_Aguda'] / df_treinos['Carga_Cronica']

    # 3. Layout do Dashboard
    col1, col2, col3 = st.columns(3)
    
    ultimo_acwr = df_treinos['ACWR'].iloc[-1]
    
    with col1:
        st.metric("ACWR Atual", f"{ultimo_acwr:.2f}")
    with col2:
        status = "✅ Seguro" if 0.8 <= ultimo_acwr <= 1.3 else "⚠️ Risco"
        st.metric("Status de Lesão", status)
    with col3:
        st.metric("Total de Treinos", len(df_treinos))

    # 4. Gráfico de Evolução
    st.subheader("Evolução da Carga (TRIMP)")
    fig, ax = plt.subplots(figsize=(10, 4))
    
    # IMPORTANTE: Trocamos 'created_at' por 'data_treino' aqui também!
    ax.plot(df_treinos['data_treino'], df_treinos['Carga_Aguda'], label="Aguda (7d)", color="blue")
    ax.plot(df_treinos['data_treino'], df_treinos['Carga_Cronica'], label="Crônica (28d)", color="red", linestyle="--")
    
    # Preenchimento da Zona Segura (Corredor de Performance)
    ax.fill_between(df_treinos['data_treino'], 
                    0.8 * df_treinos['Carga_Cronica'], 
                    1.3 * df_treinos['Carga_Cronica'], 
                    color='green', alpha=0.1, label="Zona Segura")
    
    ax.set_xlabel("Data do Treino")
    ax.set_ylabel("Carga (TRIMP)")
    ax.legend()
    # Focar o gráfico nos últimos 30 dias para não ficar esse vazio
    from datetime import datetime, timedelta
    ax.set_xlim([datetime.now() - timedelta(days=30), datetime.now() + timedelta(days=2)])
    st.pyplot(fig)
else:
    st.warning("Ainda não há treinos registrados no banco de dados.")