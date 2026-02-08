import streamlit as st
import time

def renderizar_tela_login(supabase_client):
    """Layout v8.9.7 mantido intacto."""
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        st.markdown("<h2 style='text-align: center; color: #FC4C02;'>Área do Atleta</h2>", unsafe_allow_html=True)
        
        aba_login, aba_cadastro = st.tabs(["Fazer Login", "Criar Conta"])
        
        with aba_login:
            with st.form("form_login"):
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                # CORREÇÃO CIRÚRGICA AQUI:
                botao_entrar = st.form_submit_button("Entrar", type="primary", width='stretch')
                
                if botao_entrar:
                    if not email or not senha:
                        st.warning("Preencha todos os campos.")
                    else:
                        with st.spinner("Autenticando..."):
                            email = email.strip().lower()
                            res = supabase_client.table("usuarios_app").select("*").eq("email", email).eq("senha", senha).execute()
                            
                            if res.data:
                                user = res.data[0]
                                st.session_state.user_info = user
                                st.session_state.logado = True
                                
                                # Lógica F5 v9.0 (Mantida)
                                uid = str(user.get('id') or user.get('uuid'))
                                st.query_params["session_id"] = uid
                                
                                st.success(f"Bem-vindo, {user['nome']}!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("E-mail ou senha incorretos.")

        with aba_cadastro:
            with st.form("form_cadastro"):
                novo_nome = st.text_input("Nome Completo")
                novo_email = st.text_input("E-mail")
                novo_telefone = st.text_input("Telefone (WhatsApp)", placeholder="(00) 00000-0000")
                nova_senha = st.text_input("Defina uma Senha", type="password")
                confirma_senha = st.text_input("Confirme a Senha", type="password")
                
                st.markdown("---")
                st.markdown("### Termos e Privacidade")
                st.write("Ao clicar em aceitar, você concorda com os nossos Termos de Uso e Política de Privacidade (LGPD) e permite o processamento de seus dados para fins de análise de performance esportiva.")
                
                aceite_termos = st.checkbox("Eu li e aceito os termos e condições.")
                
                # CORREÇÃO CIRÚRGICA AQUI:
                botao_cadastrar = st.form_submit_button("Cadastrar", width='stretch')
                
                if botao_cadastrar:
                    if not novo_nome or not novo_email or not novo_telefone or not nova_senha:
                        st.warning("Preencha todos os campos.")
                    elif nova_senha != confirma_senha:
                        st.error("As senhas não coincidem.")
                    elif not aceite_termos:
                        st.error("Aceite os termos para continuar.")
                    else:
                        with st.spinner("Criando conta..."):
                            dados_registro = {
                                "nome": novo_nome, "email": novo_email.strip().lower(),
                                "telefone": novo_telefone, "senha": nova_senha,
                            }
                            try:
                                supabase_client.table("usuarios_app").insert(dados_registro).execute()
                                st.success("Conta criada! Faça login na aba ao lado.")
                            except Exception:
                                st.error("Erro ao cadastrar. Verifique se o e-mail já existe.")

def renderizar_tela_admin(supabase_client):
    st.title("Painel Administrativo 🔒")

def renderizar_tela_bloqueio_financeiro():
    st.markdown("---")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.error("⚠️ **ACESSO SUSPENSO**")
        st.warning("Regularize sua mensalidade para acessar os gráficos.")
        with st.container(border=True):
            st.markdown("### 💠 Pagamento via PIX")
            st.code("00020126580014BR.GOV.BCB.PIX...", language="text")
        st.info("Envie o comprovante para liberação imediata.")