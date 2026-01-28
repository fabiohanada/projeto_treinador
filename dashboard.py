import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
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

with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 PAINEL ADMIN
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    if alunos.data:
        for aluno in alunos.data:
            with st.container(border=True):
                c_info, c_btns = st.columns([3, 1])
                with c_info:
                    pago_tag = "✅" if aluno['status_pagamento'] else "❌"
                    st.markdown(f"**Aluno:** {aluno['nome']} {pago_tag}")
                    st.write(f"**Vencimento:** {formatar_data_br(aluno['data_vencimento'])}")
                with c_btns:
                    label = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                    if st.button(label, key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()

# 🚀 DASHBOARD CLIENTE (RESTAURADO COM TUDO)
else:
    st.title(f"🚀 Painel de Treino")
    
    # 1. BLOCO DE INFORMAÇÕES DE ASSINATURA (Restaurado)
    v_str = user.get('data_vencimento', "2000-01-01")
    pago = user.get('status_pagamento', False)
    
    col_venc, col_status = st.columns(2)
    with col_venc:
        st.info(f"📅 **Vencimento:** {formatar_data_br(v_str)}")
    with col_status:
        st_color = "green" if pago else "red"
        st.markdown(f"**Status:** <span style='color:{st_color}; font-weight:bold;'>{'✅ ATIVO' if pago else '❌ PENDENTE'}</span>", unsafe_allow_html=True)

    st.divider()

    # 2. BLOCO DE PAGAMENTO (Só aparece se estiver pendente)
    if not pago:
        with st.expander("💳 Clique aqui para ver o QR Code de Pagamento", expanded=True):
            payload_encoded = urllib.parse.quote(pix_copia_e_cola)
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={payload_encoded}"
            st.markdown(f"""
                <div style="text-align:center; border:2px solid #ff4b4b; padding:20px; border-radius:15px;">
                    <h3>Renovação via PIX (R$ 9,99)</h3>
                    <img src="{qr_url}" width="200"><br><br>
                    <code style="padding:10px; background:#f0f2f6; border-radius:5px;">{chave_pix_visivel}</code>
                </div>
            """, unsafe_allow_html=True)
        st.warning("⚠️ Seu acesso completo será liberado após a confirmação do pagamento.")
        st.stop()

    # 3. CONTEÚDO DOS TREINOS (Tabela + Gráficos)
    st.success(f"Olá {user['nome']}, seus treinos estão liberados!")

    # Dados simulados com a regra de 130 BPM
    df = pd.DataFrame([
        {"Data": "24/01", "Treino": "Rodagem", "Km": 10, "Tempo": 60, "FC": 145},
        {"Data": "25/01", "Treino": "Intervalado", "Km": 8, "Tempo": 45, "FC": 160},
        {"Data": "26/01", "Treino": "Trote", "Km": 5, "Tempo": 35, "FC": 0},
        {"Data": "27/01", "Treino": "Longo", "Km": 15, "Tempo": 95, "FC": 138},
    ])
    df['FC_Final'] = df['FC'].apply(lambda x: 130 if x <= 0 else x)
    df['TRIMP'] = df['Tempo'] * (df['FC_Final'] / 100)

    # Exibição da Planilha
    st.subheader("📋 Planilha de Treinos")
    st.dataframe(df[['Data', 'Treino', 'Km', 'Tempo', 'FC_Final']], use_container_width=True, hide_index=True)

    # Exibição dos Gráficos (Um ao lado do outro)
    st.subheader("📊 Análise de Desempenho")
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        st.write("**Carga TRIMP**")
        st.plotly_chart(px.bar(df, x='Data', y='TRIMP', color_discrete_sequence=['#00bfa5']), use_container_width=True)
    with c_g2:
        st.write("**Frequência Cardíaca**")
        fig_fc = px.line(df, x='Data', y='FC_Final', markers=True)
        fig_fc.add_hline(y=130, line_dash="dash")
        st.plotly_chart(fig_fc, use_container_width=True)

    st.info("💡 Treinos sem registro de FC usam a base de 130 bpm para o cálculo de carga.")
