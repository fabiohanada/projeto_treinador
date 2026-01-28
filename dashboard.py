import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib, urllib.parse
from supabase import create_client

# 1. CONFIGURAÇÕES (Layout Fiel 27/01)
st.set_page_config(page_title="Fábio Assessoria", layout="wide", page_icon="🏃‍♂️")

# --- CONFIGURAÇÃO PIX ---
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# CSS para restaurar o visual exato e tabelas limpas
st.markdown("""
    <style>
    span.no-style { text-decoration: none !important; color: inherit !important; border-bottom: none !important; }
    [data-testid="stHorizontalBlock"] > div:nth-child(2) [data-testid="stVerticalBlock"] { max-width: 450px; margin: 0 auto; }
    .stButton>button { border-radius: 5px; }
    
    /* Estilo das tabelas antigas */
    .stDataFrame { border: 1px solid #e6e9ef; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

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
    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

# 👨‍🏫 PAINEL ADMIN (Layout Fábio Hanada Original)
if eh_admin:
    st.title("👨‍🏫 Painel Administrativo")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    if alunos.data:
        for aluno in alunos.data:
            with st.container(border=True):
                c_info, c_btns = st.columns([3, 1])
                with c_info:
                    pago_badge = "✅" if aluno['status_pagamento'] else "❌"
                    st.markdown(f"**Aluno:** {aluno['nome']} {pago_badge}")
                    st.write(f"**Vencimento:** {formatar_data_br(aluno['data_vencimento'])}")
                    nova_data = st.date_input("Alterar data", value=datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d'), key=f"d_{aluno['id']}")
                with c_btns:
                    if st.button("💾 Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                        st.rerun()
                    label = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                    if st.button(label, key=f"a_{aluno['id']}", use_container_width=True):
                        supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                        st.rerun()

# 🚀 DASHBOARD CLIENTE (Formato Antigo de Tabela)
else:
    st.title("🚀 Meus Treinos")
    pago = user.get('status_pagamento', False)
    
    with st.expander("💳 Assinatura e Pagamento", expanded=not pago):
        if not pago:
            payload_encoded = urllib.parse.quote(pix_copia_e_cola)
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={payload_encoded}"
            st.markdown(f"""
                <div style="text-align:center; border:2px solid #00bfa5; padding:20px; border-radius:15px;">
                    <h3>💳 Renovação via PIX (R$ 9,99)</h3>
                    <img src="{qr_url}" width="200"><br><br>
                    <code style="padding:10px; background:#f0f2f6; border-radius:5px;">{chave_pix_visivel}</code>
                </div>
            """, unsafe_allow_html=True)
            st.stop()

    st.success(f"Olá {user['nome']}, sua planilha de treinos atualizada:")

    # --- TABELA DE TREINOS FORMATO ANTIGO ---
    data_treinos = {
        "Data": ["28/01/2026", "29/01/2026", "30/01/2026", "31/01/2026"],
        "Treino": ["Adaptação e Mobilidade", "Fortalecimento Core", "Resistência Aeróbica", "Técnica e Corrida"],
        "Distância": ["5.0 km", "---", "8.2 km", "3.0 km"],
        "Tempo": ["32:10", "45:00", "54:30", "25:00"],
        "Ritmo (Pace)": ["6:26 /km", "N/A", "6:38 /km", "8:20 /km"]
    }
    
    df_treinos = pd.DataFrame(data_treinos)
    
    # Exibição em tabela limpa (Format antiga)
    st.dataframe(df_treinos, use_container_width=True, hide_index=True)

    st.divider()
    st.info("💡 Clique em qualquer linha para ver detalhes ou exportar os dados.")
