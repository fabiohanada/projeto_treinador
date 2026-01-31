import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import urllib.parse
from modules.utils import hash_senha, formatar_data_br, REDIRECT_URI, PIX_COPIA_COLA, enviar_whatsapp

def renderizar_tela_login(supabase):
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.8, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Aluno"])
        with tab_login:
            with st.form("login_form"):
                e = st.text_input("E-mail")
                s = st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Painel", type="primary", width="stretch"):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado = True
                        st.session_state.user_info = u.data[0]
                        st.rerun()
                    else: st.error("E-mail ou senha incorretos.")

        with tab_cadastro:
            with st.form("cad_form"):
                st.markdown("### 📝 Cadastro de Aluno")
                n_nome = st.text_input("Nome Completo")
                n_email = st.text_input("E-mail")
                n_tel = st.text_input("WhatsApp (Ex: +5511999999999)")
                n_senha = st.text_input("Crie uma Senha", type="password")
                st.markdown("---")
                st.info("🔒 **LGPD:** Você autoriza o uso dos dados de treino para consultoria.")
                aceite = st.checkbox("Li e concordo com os termos.")
                if st.form_submit_button("Finalizar Cadastro", type="primary", width="stretch"):
                    if not aceite: st.warning("Aceite a LGPD.")
                    elif n_nome and n_email and n_senha:
                        try:
                            supabase.table("usuarios_app").insert({"nome": n_nome, "email": n_email, "telefone": n_tel, "senha": hash_senha(n_senha), "status_pagamento": False}).execute()
                            enviar_whatsapp(st.secrets["MEU_CELULAR"], f"🚀 *Novo Aluno:* {n_nome}")
                            st.success("✅ Cadastro feito! Aguarde liberação.")
                        except: st.error("Erro no cadastro.")

def renderizar_tela_admin(supabase):
    st.title("👨‍🏫 Central do Treinador")
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1.5])
            with col1:
                st.subheader(aluno['nome'])
                st.write(f"**Status:** {'✅ ATIVO' if aluno['status_pagamento'] else '❌ BLOQUEADO'}")
            with col2:
                v_data = date.fromisoformat(aluno['data_vencimento']) if aluno.get('data_vencimento') else date.today()
                nova_dt = st.date_input("Vencimento", value=v_data, key=f"d_{aluno['id']}")
            with col3:
                if st.button("💾 Salvar", key=f"s_{aluno['id']}", width="stretch"):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt), "status_pagamento": True}).eq("id", aluno['id']).execute()
                    st.rerun()
                if st.button("🚫 Bloquear" if aluno['status_pagamento'] else "✅ Ativar", key=f"t_{aluno['id']}", width="stretch"):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

def renderizar_tela_aluno(supabase, user, client_id):
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento'):
        st.error("⚠️ Acesso suspenso.")
        st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(PIX_COPIA_COLA)}")
        st.code(PIX_COPIA_COLA)
        st.stop()

    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        c1, c2 = st.columns(2)
        # CORREÇÃO 2026: width="stretch"
        with c1: st.plotly_chart(px.bar(df, x='data', y='distancia', title="Volume (km)"), width="stretch")
        with c2: st.plotly_chart(px.line(df, x='data', y='fc_media', title="FC Média"), width="stretch")
        st.dataframe(df, width="stretch", hide_index=True)
    else: st.info("Conecte seu Strava na barra lateral.")