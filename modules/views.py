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
    import streamlit as st
    import requests
    from datetime import datetime, date
    
    st.title("Painel Administrativo 🔒")

    # ===============================================================
    # 🌟 NOVO: VERIFICADOR AUTOMÁTICO DO MERCADO PAGO
    # ===============================================================
    try:
        token_mp = st.secrets.get("MP_ACCESS_TOKEN")
        if token_mp:
            # Busca só quem está bloqueado e tem um PIX gerado no sistema
            pendentes = supabase_client.table("usuarios_app").select("id, nome, id_pagamento_mp").eq("bloqueado", True).not_.is_null("id_pagamento_mp").execute()
            
            for aluno in pendentes.data:
                mp_id = aluno['id_pagamento_mp']
                url = f"https://api.mercadopago.com/v1/payments/{mp_id}"
                headers = {"Authorization": f"Bearer {token_mp}"}
                
                # Consulta o Mercado Pago
                res = requests.get(url, headers=headers).json()
                
                # Se o status for "approved" (pagamento confirmado)
                if res.get("status") == "approved":
                    st.success(f"📢 **NOTIFICAÇÃO:** O aluno(a) **{aluno['nome']}** fez o pagamento! Verifique sua conta e ative o aluno abaixo.")
    except Exception as e:
        pass # Se der algum erro de internet ou faltar o token, o admin continua funcionando normal
    # ===============================================================

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
                            # 🌟 NOVO: Limpa o PIX pago para o aluno poder gerar um novo no mês seguinte
                            supabase_client.table("usuarios_app").update({"id_pagamento_mp": None}).eq("id", user['id']).execute()
                            
                            # Mantém a sua função original intacta
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
    import requests
    import uuid
    from supabase import create_client
    
    user = st.session_state.user_info
    
    try:
        supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        pass
        
    token_mp = st.secrets.get("MP_ACCESS_TOKEN", "")
    
    col_esq, col_center, col_dir = st.columns([1, 2, 1])
    
    with col_center:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.error("⚠️ ACESSO SUSPENSO")
        st.warning("Regularize sua mensalidade para acessar seu painel.")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not token_mp:
            st.info("Sistema de pagamento em manutenção. Avise o treinador Fábio.")
            return

        # 1. SE O ALUNO NÃO TEM PIX GERADO
        if not user.get('id_pagamento_mp'):
            with st.spinner("Gerando chave PIX exclusiva..."):
                url = "https://api.mercadopago.com/v1/payments"
                headers = {"Authorization": f"Bearer {token_mp}", "X-Idempotency-Key": str(uuid.uuid4())}
                payload = {
                    "transaction_amount": 0.01, # 💰 VALOR ALTERADO PARA 1 CENTAVO AQUI PARA TESTES
                    "description": f"Mensalidade - {user['nome']}",
                    "payment_method_id": "pix",
                    "payer": {"email": f"aluno_{user['id']}@fabioassessoria.com"} 
                }
                
                try:
                    res = requests.post(url, json=payload, headers=headers).json()
                    
                    if "id" in res:
                        mp_id = str(res["id"])
                        supabase.table("usuarios_app").update({"id_pagamento_mp": mp_id}).eq("id", user['id']).execute()
                        st.session_state.user_info['id_pagamento_mp'] = mp_id
                        st.rerun()
                    else:
                        st.error("Falha ao gerar o PIX no banco. Tente novamente.")
                except Exception as e:
                    st.error("Erro de comunicação com o sistema bancário.")
                    
        # 2. SE O PIX JÁ ESTÁ GERADO E SALVO, MOSTRA NA TELA
        else:
            mp_id = user['id_pagamento_mp']
            url = f"https://api.mercadopago.com/v1/payments/{mp_id}"
            headers = {"Authorization": f"Bearer {token_mp}"}
            
            try:
                res = requests.get(url, headers=headers).json()
                
                if "point_of_interaction" in res:
                    dados_pix = res["point_of_interaction"]["transaction_data"]
                    qr_base64 = dados_pix["qr_code_base64"]
                    copia_cola = dados_pix["qr_code"]
                    
                    with st.container(border=True):
                        st.markdown("<h3 style='text-align: center;'>💠 Pague via PIX</h3>", unsafe_allow_html=True)
                        
                        col_qr_esq, col_qr, col_qr_dir = st.columns([1, 2, 1])
                        with col_qr:
                            st.image(f"data:image/jpeg;base64,{qr_base64}", width='stretch')
                            
                        st.markdown("<p style='text-align: center; margin-bottom: 5px; color: gray;'>PIX Copia e Cola:</p>", unsafe_allow_html=True)
                        st.code(copia_cola, language="text")
                        
                else:
                    st.warning("Aguardando liberação da chave PIX...")
            except:
                st.error("Erro ao carregar a imagem do QR Code.")

        st.info("Após o pagamento, o sistema alertará o treinador automaticamente.")