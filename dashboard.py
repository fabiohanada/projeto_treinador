import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import hashlib, urllib.parse
from supabase import create_client

# 1. CONFIGURAÇÕES
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# --- CONFIGURAÇÃO PIX ---
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()
def formatar_data_br(data_str):
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return data_str

# =================================================================
# 🔑 LOGIN E CADASTRO
# =================================================================
if "logado" not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown("<br><h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Cadastro"])
        with tab_login:
            with st.form("login_form"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Sistema", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.rerun()
    st.stop()

# =================================================================
# 🏠 ÁREA LOGADA
# =================================================================
user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# 👨‍🏫 PAINEL ADMIN (Layout Fábio Hanada Original)
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    if alunos.data:
        for aluno in alunos.data:
            with st.container(border=True):
                c_info, c_btns = st.columns([3, 1])
                with c_info:
                    st.markdown(f"**Aluno:** {aluno['nome']}")
                    st.write(f"**Vencimento:** {formatar_data_br(aluno['data_vencimento'])}")
                with c_btns:
                    label = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                    if st.button(label, key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()

# 🚀 DASHBOARD CLIENTE
else:
    st.title(f"🚀 Painel de Treino: {user['nome']}")
    pago = user.get('status_pagamento', False)
    
    if not pago:
        payload_encoded = urllib.parse.quote(pix_copia_e_cola)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={payload_encoded}"
        st.warning("Assinatura Pendente")
        st.markdown(f'<div style="text-align:center;"><img src="{qr_url}"><br><code>{chave_pix_visivel}</code></div>', unsafe_allow_html=True)
        st.stop()

    # --- DADOS DE TREINO (Simulados para Maria) ---
    # Aqui aplicamos a regra: se FC for 0 ou None, vira 130
    dados_maria = [
        {"Data": "24/01", "Treino": "Rodagem", "Km": 10, "Tempo": 60, "FC": 145},
        {"Data": "25/01", "Treino": "Intervalado", "Km": 8, "Tempo": 45, "FC": 160},
        {"Data": "26/01", "Treino": "Trote", "Km": 5, "Tempo": 35, "FC": 0}, # Sem frequência
        {"Data": "27/01", "Treino": "Longo", "Km": 15, "Tempo": 95, "FC": 138},
    ]
    
    df = pd.DataFrame(dados_maria)
    # REGRA DOS 130 BPM
    df['FC_Final'] = df['FC'].apply(lambda x: 130 if x <= 0 else x)
    # CÁLCULO TRIMP SIMPLIFICADO (Tempo x Intensidade baseada na FC)
    df['TRIMP'] = df['Tempo'] * (df['FC_Final'] / 100)

    # --- VISUALIZAÇÃO ---
    tab1, tab2 = st.tabs(["📋 Planilha de Treinos", "📊 Gráficos de Evolução"])

    with tab1:
        st.subheader("Últimas Atividades")
        st.dataframe(df[['Data', 'Treino', 'Km', 'Tempo', 'FC_Final']], use_container_width=True, hide_index=True)

    with tab2:
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.write("**Carga de Treino (TRIMP)**")
            fig_trimp = px.bar(df, x='Data', y='TRIMP', color_discrete_sequence=['#00bfa5'])
            st.plotly_chart(fig_trimp, use_container_width=True)
            

        with col_g2:
            st.write("**Frequência Cardíaca (Média)**")
            # Linha de referência nos 130
            fig_fc = px.line(df, x='Data', y='FC_Final', markers=True)
            fig_fc.add_hline(y=130, line_dash="dash", annotation_text="Base 130 bpm")
            st.plotly_chart(fig_fc, use_container_width=True)
            

    st.divider()
    st.info("💡 Nota: Treinos sem registro de frequência cardíaca são calculados com base em 130 bpm.")
