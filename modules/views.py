import streamlit as st
import pandas as pd
import time
import requests
import uuid
from datetime import datetime, date
from twilio.rest import Client

# ============================================================================
# 🛠️ FUNÇÕES AUXILIARES (BACKEND)
# ============================================================================
def enviar_notificacao_treino(dados_treino, nome_atleta, telefone_atleta):
    from twilio.rest import Client
    import streamlit as st
    try:
        # 1. Busca credenciais
        sid = st.secrets["twilio"]["TWILIO_SID"].strip()
        token = st.secrets["twilio"]["TWILIO_TOKEN"].strip()
        from_number = f"whatsapp:+{st.secrets['twilio']['TWILIO_PHONE_NUMBER']}"
        
        # 2. LIMPEZA RADICAL DO TELEFONE
        # Remove tudo que não for número
        import re
        apenas_numeros = re.sub(r'\D', '', str(telefone_atleta))
        
        # Garante o +55 (Brasil) se o aluno esqueceu de digitar
        if len(apenas_numeros) <= 11:
            apenas_numeros = "55" + apenas_numeros
        
        to_number = f"whatsapp:+{apenas_numeros}"
        
        # DEBUG VISUAL (Apenas para você ver se o número está certo)
        st.toast(f"Tentando enviar para: {to_number}")

        client = Client(sid, token)
        
        corpo_msg = (
            f"🏃‍♂️ *Treino Sincronizado*\n\n"
            f"👤 Atleta: {nome_atleta}\n"
            f"📏 Distância: {dados_treino['distancia']}\n"
            f"⏱️ Duração: {dados_treino['duracao']}\n"
            f"📊 TRIMP Semanal: {dados_treino['trimp_semanal']}\n" # Adicionado \n
            f"📊 TRIMP Mensal: {dados_treino['trimp_mensal']}"
        )
        
        msg = client.messages.create(body=corpo_msg, from_=from_number, to=to_number)
        return True, msg.sid
    except Exception as e:
        st.error(f"❌ ERRO TWILIO: {str(e)}")
        return False, str(e)

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

# ============================================================================
# 🖥️ TELAS DO SISTEMA
# ============================================================================

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
                novo_telefone = st.text_input("Telefone (WhatsApp)", placeholder="+5511999999999")
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
    if "MP_ACCESS_TOKEN" in st.secrets:
        st.sidebar.success("✅ Token MP detectado")
    else:
        st.sidebar.error("❌ Token MP não encontrado")
    
    st.title("Painel Administrativo 🔒")

    with st.expander("💬 Teste de Conexão WhatsApp"):
        numero_destino = st.text_input("Número de Destino", value="+55")
        if st.button("🚀 Enviar Teste"):
            try:
                sid = st.secrets["twilio"]["TWILIO_SID"].strip()
                token = st.secrets["twilio"]["TWILIO_TOKEN"].strip()
                from_num = f"whatsapp:+{st.secrets['twilio']['TWILIO_PHONE_NUMBER']}"
                client = Client(sid, token)
                msg = client.messages.create(body="🤖 Conexão V10.0 OK!", from_=from_num, to=f"whatsapp:{numero_destino}")
                st.success(f"✅ Enviado! ID: {msg.sid}")
            except Exception as e:
                st.error(f"Erro: {e}")

    # --- LISTA DE ALUNOS E FINANCEIRO ---
    try:
        users = supabase_client.table("usuarios_app").select("*").order("nome").execute().data
        if users:
            st.markdown("### 📋 Controle de Alunos")
            for user in users:
                if user.get('is_admin'): continue
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1.5, 1.5])
                    c1.write(f"👤 **{user['nome']}**")
                    
                    data_venc = user.get('data_vencimento') or str(date.today())
                    nova_data = c2.date_input("Venc.", value=datetime.strptime(data_venc, '%Y-%m-%d').date(), key=f"d_{user['id']}")
                    if str(nova_data) != data_venc:
                        atualizar_data_vencimento(supabase_client, user['id'], nova_data)
                    
                    if user.get('bloqueado'):
                        if c3.button("✅ Liberar", key=f"lib_{user['id']}"):
                            alternar_bloqueio(supabase_client, user['id'], True)
                    else:
                        if c3.button("⛔ Bloquear", key=f"bloq_{user['id']}", type="primary"):
                            alternar_bloqueio(supabase_client, user['id'], False)
    except Exception as e:
        st.error(f"Erro ao carregar alunos: {e}")

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
                    "transaction_amount": 1.00, # 💰 VALOR ALTERADO PARA 1 CENTAVO AQUI PARA TESTES
                    "description": f"Mensalidade - {user['nome']}",
                    "payment_method_id": "pix",
                    "payer": {"email": f"aluno_{user['id']}@fabioassessoria.com"} 
                }
                
                try:
                    res = requests.post(url, json=payload, headers=headers).json()
                    
                    # --- CÓDIGO DE DIAGNÓSTICO ---
                    if res.get("status") == 400 or res.get("error"):
                        st.error(f"Erro MP: {res.get('message')} | Causa: {res.get('cause', [{}])[0].get('description')}")
                    # -----------------------------
                    
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

def renderizar_tela_aluno(supabase_client):
    # 1. Marcação Visual de Topo
    st.error("🚨 MODO DE TESTE ATIVADO - SE VOCÊ VÊ ISSO, O CÓDIGO ESTÁ RODANDO")
    st.title(f"Olá, {st.session_state.user_info['nome']}! 🏃‍♂️")
    
    # 2. BOTÃO DE TESTE (Sem expander, sem colunas, direto na tela)
    st.markdown("### 🛠️ TESTE DE WHATSAPP")
    if st.button("🔴 CLIQUE AQUI PARA TESTAR WHATSAPP AGORA"):
        dados_teste = {
            "distancia": "10km", 
            "duracao": "01:00", 
            "trimp_semanal": "150"
        }
        nome = st.session_state.user_info.get('nome')
        tel = st.session_state.user_info.get('telefone')
        
        ok, res = enviar_notificacao_treino(dados_teste, nome, tel)
        
        if ok: 
            st.success(f"✅ SUCESSO! ID: {res}")
        else:
            st.error(f"❌ FALHA: {res}")
    
    st.markdown("---")

    # 3. INTEGRAÇÃO STRAVA
    try:
        client_id = st.secrets.get("STRAVA_CLIENT_ID")
        client_secret = st.secrets.get("STRAVA_CLIENT_SECRET")
        redirect_uri = st.secrets.get("REDIRECT_URI", "http://localhost:8501")
        
        url_auth = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&approval_prompt=force&scope=activity:read_all"
        st.link_button("🟠 Sincronizar Strava", url_auth)
    except Exception as e:
        st.error(f"Erro Strava: {e}")

    # Processamento do código Strava
    code = st.query_params.get("code")
    if code:
        st.info("🔄 Sincronizando...")
        # (Resto da lógica de sincronização que já temos...)