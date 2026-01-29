import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v2.3 (ADMIN PREMIUM + DASHBOARD)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v2.3", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
STRAVA_CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
REDIRECT_URI = "https://projeto-treinador.streamlit.app/" 
chave_pix_visivel = "fabioh1979@hotmail.com"
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or data_str == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

def gerar_link_strava():
    url = "https://www.strava.com/oauth/authorize"
    params = {"client_id": STRAVA_CLIENT_ID, "response_type": "code", "redirect_uri": REDIRECT_URI, "scope": "activity:read_all", "approval_prompt": "force"}
    return f"{url}?{urllib.parse.urlencode(params)}"

# --- LÓGICA DE ACESSO ---
if "logado" not in st.session_state: st.session_state.logado = False
if "user_mail" in st.query_params and not st.session_state.logado:
    u = supabase.table("usuarios_app").select("*").eq("email", st.query_params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]

if not st.session_state.logado:
    st.markdown("<br><h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        t1, t2 = st.tabs(["🔑 Login", "📝 Cadastro"])
        with t1:
            with st.form("login"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.query_params["user_mail"] = e
                        st.rerun()
                    else: st.error("Dados incorretos.")
        with t2:
            with st.form("cad"):
                n_c, e_c, t_c, s_c = st.text_input("Nome"), st.text_input("E-mail"), st.text_input("Zap"), st.text_input("Senha", type="password")
                if st.form_submit_button("Cadastrar"):
                    supabase.table("usuarios_app").insert({"nome": n_c, "email": e_c, "telefone": t_c, "senha": hash_senha(s_c), "status_pagamento": False, "data_vencimento": str(date.today())}).execute()
                    st.success("Pronto! Faça login.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

with st.sidebar:
    st.title("Menu")
    st.write(f"Conectado como: **{user['nome']}**")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logado = False
        st.query_params.clear()
        st.rerun()

# ==========================================
# 👨‍🏫 PAINEL ADMIN (RESTAURADO)
# ==========================================
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    st.subheader("Gestão de Alunos e Pagamentos")
    
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    
    for aluno in alunos.data:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.markdown(f"### {aluno['nome']}")
                st.caption(f"📧 {aluno['email']}")
                status = "✅ Ativo" if aluno['status_pagamento'] else "❌ Pendente"
                st.markdown(f"**Status:** {status}")
            
            with col2:
                # Tratamento de data para o seletor
                try: 
                    d_atual = datetime.strptime(aluno['data_vencimento'], '%Y-%m-%d').date() if aluno['data_vencimento'] else date.today()
                except: 
                    d_atual = date.today()
                
                nova_data = st.date_input(f"Vencimento", value=d_atual, key=f"dt_{aluno['id']}")
                st.write(f"Atual: {formatar_data_br(aluno['data_vencimento'])}")
            
            with col3:
                st.write("") # Espaçador
                if st.button("💾 Salvar", key=f"sv_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", aluno['id']).execute()
                    st.success("Salvo!")
                
                btn_label = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                if st.button(btn_label, key=f"bt_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

# ==========================================
# 🚀 PAINEL ALUNO
# ==========================================
else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    pago = user.get('status_pagamento', False)
    
    if not pago:
        st.error("Seu acesso expirou ou está pendente.")
        with st.expander("💳 Informações de Pagamento", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.code(chave_pix_visivel, language="text")
        st.stop()

    st.info(f"📅 Seu plano vence em: **{formatar_data_br(user.get('data_vencimento'))}**")
    
    # Botão Strava
    st.markdown(f'<a href="{gerar_link_strava()}" target="_self"><img src="https://branding.strava.com/buttons/connect-with-strava/btn_strava_connectwith_orange.png" width="180"></a>', unsafe_allow_html=True)
    
    # Dados e Gráficos
    treinos = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(treinos.data) if treinos.data else pd.DataFrame([{"data": str(date.today()), "nome_treino": "Aguardando Strava", "distancia": 0, "tempo_min": 0, "fc_media": 130}])

    st.divider()
    st.subheader("📈 Evolução dos Treinos")
    
    c_g1, c_g2 = st.columns(2)
    with c_g1:
        df['TRIMP'] = df['tempo_min'] * (df['fc_media'] / 100)
        st.plotly_chart(px.bar(df, x='data', y='TRIMP', title="Carga de Treino (TRIMP)", color_discrete_sequence=['#FF4B4B']), use_container_width=True)
    with c_g2:
        fig = px.line(df, x='data', y='fc_media', title="Frequência Cardíaca Média", markers=True)
        fig.add_hline(y=130, line_dash="dash", line_color="green", annotation_text="Meta 130bpm")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Histórico de Atividades")
    st.dataframe(df, use_container_width=True, hide_index=True)
