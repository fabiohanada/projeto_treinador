import streamlit as st
import pandas as pd
import time
from datetime import datetime, date

# --- FUNÇÕES ADMIN ---
def atualizar_data_vencimento(supabase, user_id, nova_data):
    try:
        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", str(user_id)).execute()
        st.toast("Data salva!", icon="💾")
    except:
        st.toast("Erro ao salvar data.", icon="⚠️")

def alternar_bloqueio(supabase, user_id, status_atual_bloqueado):
    novo_bloqueio = not status_atual_bloqueado
    novo_status = not novo_bloqueio 
    try:
        supabase.table("usuarios_app").update({
            "bloqueado": novo_bloqueio,
            "status_pagamento": novo_status 
        }).eq("id", str(user_id)).execute()
        
        if novo_bloqueio: st.toast("Aluno Bloqueado!", icon="⛔")
        else: st.toast("Aluno Ativado!", icon="✅")
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Erro no banco: {e}")

# --- TELAS ---

def renderizar_tela_login(supabase_client):
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        st.markdown("<h2 style='text-align: center; color: #FC4C02;'>Área do Atleta</h2>", unsafe_allow_html=True)
        aba_login, aba_cadastro = st.tabs(["Fazer Login", "Criar Conta"])
        
        with aba_login:
            with st.form("form_login"):
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                botao_entrar = st.form_submit_button("Entrar", type="primary", width='stretch')
                
                if botao_entrar:
                    if not email or not senha:
                        st.warning("Preencha todos os campos.")
                    else:
                        with st.spinner("Autenticando..."):
                            email = email.strip().lower()
                            try:
                                res = supabase_client.table("usuarios_app").select("*").eq("email", email).eq("senha", senha).execute()
                                if res.data:
                                    user = res.data[0]
                                    st.session_state.user_info = user
                                    st.session_state.logado = True
                                    uid = str(user.get('id') or user.get('uuid'))
                                    st.query_params["session_id"] = uid
                                    st.success(f"Bem-vindo, {user['nome']}!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error("E-mail ou senha incorretos.")
                            except Exception as e:
                                st.error(f"Erro técnico: {e}")

        with aba_cadastro:
            with st.form("form_cadastro"):
                novo_nome = st.text_input("Nome Completo")
                novo_email = st.text_input("E-mail")
                novo_telefone = st.text_input("Telefone (WhatsApp)", placeholder="(00) 00000-0000")
                nova_senha = st.text_input("Defina uma Senha", type="password")
                confirma_senha = st.text_input("Confirme a Senha", type="password")
                st.markdown("---")
                st.markdown("### Termos e Privacidade")
                st.caption("Ao clicar em aceitar, você concorda com os nossos Termos de Uso e Política de Privacidade (LGPD).")
                aceite_termos = st.checkbox("Eu li e aceito os termos e condições.")
                botao_cadastrar = st.form_submit_button("Cadastrar", width='stretch')
                
                if botao_cadastrar:
                    if not novo_nome or not novo_email or not novo_telefone or not nova_senha:
                        st.warning("Preencha todos os campos.")
                    elif nova_senha != confirma_senha:
                        st.error("As senhas não coincidem.")
                    elif not aceite_termos:
                        st.error("Aceite os termos.")
                    else:
                        with st.spinner("Criando conta..."):
                            dados = {
                                "nome": novo_nome, "email": novo_email.strip().lower(),
                                "telefone": novo_telefone, "senha": nova_senha,
                                "is_admin": False, "status_pagamento": True, "aceite_lgpd": True
                            }
                            try:
                                supabase_client.table("usuarios_app").insert(dados).execute()
                                st.success("Conta criada! Faça login.")
                            except:
                                st.error("Erro ao cadastrar. E-mail já existe.")

def renderizar_tela_admin(supabase_client):
    st.title("Painel Administrativo 🔒")
    st.markdown("### 📋 Controle de Alunos")

    try:
        res = supabase_client.table("usuarios_app").select("*").order("nome").execute()
        users = res.data
        if users:
            st.markdown("---")
            c1, c2, c3 = st.columns([2, 1.5, 1.5])
            c1.markdown("**Nome do Aluno**")
            c2.markdown("**Data Expiração** (Editável)")
            c3.markdown("**Ação (Alterar Status)**")
            st.markdown("---")

            for user in users:
                if user.get('is_admin'): continue 
                col_nome, col_data, col_acao = st.columns([2, 1.5, 1.5])
                with col_nome:
                    st.write(f"👤 **{user['nome']}**")
                with col_data:
                    data_atual = user.get('data_vencimento')
                    if data_atual:
                        try: val_data = datetime.strptime(data_atual, '%Y-%m-%d').date()
                        except: val_data = date.today()
                    else: val_data = date.today()
                    nova_data = st.date_input("Vencimento", value=val_data, key=f"d_{user['id']}", label_visibility="collapsed")
                    if str(nova_data) != str(data_atual) and data_atual is not None:
                         atualizar_data_vencimento(supabase_client, user['id'], nova_data)
                with col_acao:
                    is_bloqueado = user.get('bloqueado', False)
                    if is_bloqueado:
                        if st.button("✅ Ativar", key=f"btn_a_{user['id']}", width='stretch'):
                            alternar_bloqueio(supabase_client, user['id'], True)
                    else:
                        if st.button("⛔ Bloquear", key=f"btn_b_{user['id']}", type="primary", width='stretch'):
                            alternar_bloqueio(supabase_client, user['id'], False)
                st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
        else:
            st.info("Nenhum aluno cadastrado.")
    except Exception as e:
        st.error(f"Erro lista: {e}")

def renderizar_tela_bloqueio_financeiro():
    import streamlit as st
    
    col_esq, col_center, col_dir = st.columns([1, 2, 1])
    
    with col_center:
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        st.error("⚠️ ACESSO SUSPENSO")
        st.warning("Regularize sua mensalidade para acessar os gráficos e histórico de treinos.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center;'>💠 Pagamento via PIX</h3>", unsafe_allow_html=True)
            
            col_qr_esq, col_qr, col_qr_dir = st.columns([1, 2, 1])
            with col_qr:
                try:
                    # CORRIGIDO AQUI: Trocamos use_container_width por width='stretch'
                    st.image("assets/qrcodeteste.jpeg", width='stretch')
                except:
                    st.info("A imagem 'qrcodeteste.jpeg' não foi encontrada na pasta 'assets'.")
            
            st.markdown("<p style='text-align: center; margin-bottom: 5px; color: gray;'>PIX Copia e Cola:</p>", unsafe_allow_html=True)
            
            # --- COLE SEU CÓDIGO PIX AQUI ---
            codigo_pix = "00020126400014br.gov.bcb.pix0111287108508050203Pix52040000530398654040.015802BR5912FABIO HANADA6015MOGI DAS CRUZES622905253yBb7pz5vVeUQKXlaL0202mpC63048FC4" 
            
            st.code(codigo_pix, language="text")
            
        
            