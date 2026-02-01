import streamlit as st
import pandas as pd
from datetime import datetime, date

def renderizar_tela_login(supabase):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h1>", unsafe_allow_html=True)
        st.caption("<p style='text-align: center;'>v8.1 - Oficial</p>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["Entrar", "Novo Aluno"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Painel", type="primary", width="stretch"):
                    try:
                        res = supabase.table("usuarios_app").select("*").eq("email", email).execute()
                        if res.data:
                            user = res.data[0]
                            if str(user['senha']) == str(senha):
                                st.session_state.logado = True
                                st.session_state.user_info = user
                                st.rerun()
                            else: st.error("Senha incorreta.")
                        else: st.error("Utilizador não encontrado.")
                    except Exception as e: st.error(f"Erro de conexão: {e}")

        with tab2:
            st.subheader("Cadastro de Novo Aluno")
            with st.form("cadastro_form"):
                n = st.text_input("Nome Completo")
                e = st.text_input("E-mail")
                t = st.text_input("Telefone")
                s = st.text_input("Senha", type="password")
                st.markdown("---")
                # CORREÇÃO 1: Restaurado o termo LGPD com texto claro
                st.info("Termos LGPD: Seus dados serão utilizados apenas para fins de consultoria esportiva e sincronização com o Strava.")
                aceite = st.checkbox("Eu aceito os termos de uso e política de privacidade (LGPD)")
                
                if st.form_submit_button("Finalizar Cadastro", width="stretch"):
                    if aceite and n and e and t and s:
                        try:
                            supabase.table("usuarios_app").insert({
                                "nome": n, "email": e, "telefone": t, "senha": s,
                                "is_admin": False, "status_pagamento": False,
                                "data_vencimento": str(date.today()), "aceite_lgpd": True,
                                "bloqueado": False
                            }).execute()
                            st.success("Cadastro realizado! Aguarde a liberação do seu acesso.")
                        except Exception as err: st.error(f"Erro ao salvar: {err}")
                    else:
                        st.warning("Você precisa preencher tudo e aceitar o termo LGPD.")

def renderizar_tela_admin(supabase):
    st.title("Gestão de Alunos 🚀")
    try:
        res = supabase.table("usuarios_app").select("*").eq("is_admin", False).order("nome").execute()
    except Exception as e:
        st.error(f"Erro: {e}")
        return

    if res.data:
        df = pd.DataFrame(res.data)
        cols = st.columns([2.5, 2, 1.5, 2.5])
        cols[0].write("**Nome**")
        cols[1].write("**Data de Vencimento**")
        cols[2].write("**Status**")
        cols[3].write("**Ação**")
        st.markdown("---")

        for index, row in df.iterrows():
            c1, c2, c3, c4 = st.columns([2.5, 2, 1.5, 2.5])
            c1.write(f"**{row['nome']}**")
            
            # Seletor de Data
            dv = pd.to_datetime(row['data_vencimento'])
            nova_dt = c2.date_input("Venc", value=dv, key=f"dt_{row['id']}", label_visibility="collapsed")
            if nova_dt != dv.date():
                supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt)}).eq("id", row['id']).execute()
                st.rerun()
            
            # Status
            bloq = row.get('bloqueado', False)
            c3.write("🚫 Bloqueado" if bloq else "✅ Ativo")

            # Ações
            b1, b2 = c4.columns(2)
            if b1.button("Liberar", key=f"l_{row['id']}", width="stretch"):
                supabase.table("usuarios_app").update({"bloqueado": False}).eq("id", row['id']).execute()
                st.rerun()
            if b2.button("Bloquear", key=f"b_{row['id']}", width="stretch"):
                supabase.table("usuarios_app").update({"bloqueado": True}).eq("id", row['id']).execute()
                st.rerun()
            st.markdown("<hr style='margin:0.5em 0; opacity:0.1;'>", unsafe_allow_html=True)