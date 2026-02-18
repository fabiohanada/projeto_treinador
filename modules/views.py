import streamlit as st
import pandas as pd
import time
import requests
import uuid
from datetime import datetime, date
from twilio.rest import Client
import re
from supabase import create_client

# ============================================================================
# 🛠️ FUNÇÃO DE ENVIO DO WHATSAPP
# ============================================================================

def enviar_notificacao_treino(dados_treino, nome_atleta, telefone_atleta):
    try:
        # 1. Busca credenciais
        sid = st.secrets["twilio"]["TWILIO_SID"].strip()
        token = st.secrets["twilio"]["TWILIO_TOKEN"].strip()
        from_number = f"whatsapp:+{st.secrets['twilio']['TWILIO_PHONE_NUMBER']}"
        
        # 2. LIMPEZA DO TELEFONE
        apenas_numeros = re.sub(r'\D', '', str(telefone_atleta))
        if len(apenas_numeros) <= 11:
            apenas_numeros = "55" + apenas_numeros
        
        to_number = f"whatsapp:+{apenas_numeros}"

        client = Client(sid, token)
        
        # CORPO DA MENSAGEM (FORMATO PADRÃO)
        corpo_msg = (
            f"🏃‍♂️ *Treino Sincronizado*\n\n"
            f"👤 Atleta: {nome_atleta}\n"
            f"📏 Distância: {dados_treino['distancia']}\n"
            f"⏱️ Duração: {dados_treino['duracao']}\n"
            f"📊 TRIMP Semanal: {dados_treino.get('trimp_semanal', '-')}\n"
            f"📊 TRIMP Mensal: {dados_treino.get('trimp_mensal', '-')}"
        )
        
        msg = client.messages.create(body=corpo_msg, from_=from_number, to=to_number)
        return True, msg.sid
    except Exception as e:
        return False, str(e)

# ============================================================================
# 🛠️ FUNÇÕES AUXILIARES DE BANCO
# ============================================================================

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
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Erro no banco: {e}")

# ============================================================================
# 🖥️ TELAS DO SISTEMA
# ============================================================================

def renderizar_tela_login(supabase_client):
    # Apenas o botão de submit (Cadastrar) será laranja
    st.markdown("""
        <style>
        div.stButton > button:first-child {
            background-color: #FC4C02 !important;
            color: white !important;
            border: none !important;
        }
        </style>
    """, unsafe_allow_html=True)

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
                novo_telefone = st.text_input("Telefone (WhatsApp)", placeholder="11999999999")
                
                data_nasc = st.date_input(
                    "Data de Nascimento",
                    value=None,
                    min_value=date(1940, 1, 1),
                    max_value=date.today(),
                    format="DD/MM/YYYY"
                )
                
                nova_senha = st.text_input("Defina uma Senha", type="password")
                confirma_senha = st.text_input("Confirme a Senha", type="password")
                
                st.markdown("---")
                st.markdown("### Termos e Privacidade")
                st.caption("Ao clicar em aceitar, você concorda com os nossos Termos de Uso e Política de Privacidade (LGPD).")
                aceite_termos = st.checkbox("Eu li e aceito os termos e condições.")
                
                botao_cadastrar = st.form_submit_button("Cadastrar", width='stretch')
                
                if botao_cadastrar:
                    if not novo_nome or not novo_email or not novo_telefone or not nova_senha or not data_nasc:
                        st.warning("⚠️ Preencha todos os campos obrigatórios.")
                    elif nova_senha != confirma_senha:
                        st.error("❌ As senhas não coincidem.")
                    elif not aceite_termos:
                        st.error("🔒 É necessário aceitar os termos da LGPD.")
                    else:
                        with st.spinner("Criando conta..."):
                            dados = {
                                "nome": novo_nome, 
                                "email": novo_email.strip().lower(),
                                "telefone": novo_telefone, 
                                "senha": nova_senha,
                                "data_nascimento": str(data_nasc),
                                "is_admin": False, 
                                "status_pagamento": True, 
                                "aceite_lgpd": True
                            }
                            try:
                                supabase_client.table("usuarios_app").insert(dados).execute()
                                st.balloons()
                                st.success("✅ Conta criada com sucesso! Faça seu login.")
                            except Exception as e:
                                if "already exists" in str(e).lower():
                                    st.error("📧 Este e-mail já está cadastrado.")
                                else:
                                    st.error(f"❌ Erro ao cadastrar. Verifique o banco de dados.")

def renderizar_tela_admin(supabase_client):
    st.title("Painel Administrativo 🔒")
    
    # --- RASTREADOR DE PAGAMENTOS (MANTIDO IGUAL) ---
    try:
        token_mp = st.secrets.get("MP_ACCESS_TOKEN")
        if token_mp:
            res_users = supabase_client.table("usuarios_app").select("id, nome, id_pagamento_mp").execute()
            for aluno in res_users.data:
                mp_id = str(aluno.get('id_pagamento_mp')).strip()
                if mp_id and mp_id != "None":
                    try:
                        url = f"https://api.mercadopago.com/v1/payments/{mp_id}"
                        res_mp = requests.get(url, headers={"Authorization": f"Bearer {token_mp}"}).json()
                        if res_mp.get("status") == "approved":
                            st.success(f"💰 {aluno['nome']} PAGOU!")
                    except: pass
    except Exception as e:
        st.error(f"Erro MP: {e}")

    # --- LISTA DE ALUNOS COM EDITAR/EXCLUIR ---
    try:
        users = supabase_client.table("usuarios_app").select("*").order("nome").execute().data
        if users:
            st.markdown("### 📋 Controle de Alunos")
            
            for user in users:
                if user.get('is_admin'): continue # Pula o admin
                
                # O container visual principal (MANTIDO)
                with st.container(border=True):
                    # Layout original das colunas
                    c1, c2, c3 = st.columns([2, 1.5, 1.5])
                    
                    # Coluna 1: Nome (Visualização)
                    c1.write(f"👤 **{user['nome']}**")
                    
                    # Coluna 2: Vencimento (Funcionalidade existente)
                    data_venc = user.get('data_vencimento') or str(date.today())
                    nova_data = c2.date_input("Venc.", value=datetime.strptime(data_venc, '%Y-%m-%d').date(), key=f"d_{user['id']}", label_visibility="collapsed")
                    if str(nova_data) != data_venc:
                        atualizar_data_vencimento(supabase_client, user['id'], nova_data)
                    
                    # Coluna 3: Botão de Bloqueio (Funcionalidade existente)
                    if user.get('bloqueado'):
                        if c3.button("✅ Liberar", key=f"lib_{user['id']}"):
                            supabase_client.table("usuarios_app").update({"id_pagamento_mp": None}).eq("id", user['id']).execute()
                            alternar_bloqueio(supabase_client, user['id'], True)
                    else:
                        if c3.button("⛔ Bloquear", key=f"bloq_{user['id']}", type="primary"):
                            alternar_bloqueio(supabase_client, user['id'], False)

                    # --- NOVIDADE: ÁREA DE EDIÇÃO E EXCLUSÃO (ESCONDIDA) ---
                    # Usamos um expander para não poluir o layout principal
                    with st.expander("⚙️ Editar / Excluir"):
                        
                        # Formulário de Edição
                        with st.form(key=f"form_edit_{user['id']}"):
                            st.caption("Editar Dados Cadastrais")
                            col_e1, col_e2 = st.columns(2)
                            edit_nome = col_e1.text_input("Nome", value=user['nome'])
                            edit_email = col_e2.text_input("E-mail", value=user['email'])
                            edit_tel = st.text_input("Telefone", value=user.get('telefone', ''))
                            
                            if st.form_submit_button("💾 Salvar Alterações"):
                                try:
                                    supabase_client.table("usuarios_app").update({
                                        "nome": edit_nome,
                                        "email": edit_email,
                                        "telefone": edit_tel
                                    }).eq("id", user['id']).execute()
                                    st.toast("Dados atualizados com sucesso!", icon="✅")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar: {e}")

                        st.markdown("---")
                        
                        # Área de Exclusão (Zona de Perigo)
                        col_del_txt, col_del_btn = st.columns([3, 1])
                        col_del_txt.warning("⚠️ **Zona de Perigo:** A exclusão é irreversível.")
                        
                        # Botão de Excluir separado para evitar clique acidental
                        if col_del_btn.button("🗑️ Excluir", key=f"del_btn_{user['id']}", type="primary"):
                            try:
                                # Deleta o usuário pelo ID
                                supabase_client.table("usuarios_app").delete().eq("id", user['id']).execute()
                                st.success(f"Usuário {user['nome']} removido!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")

    except Exception as e:
        st.error(f"Erro lista: {e}")

def renderizar_tela_bloqueio_financeiro():
    user = st.session_state.user_info
    token_mp = st.secrets.get("MP_ACCESS_TOKEN")
    if not token_mp and "mercadopago" in st.secrets:
        token_mp = st.secrets["mercadopago"].get("MP_ACCESS_TOKEN")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.error("⚠️ ACESSO SUSPENSO")
    st.warning("Para liberar seu acesso aos treinos, regularize sua mensalidade.")

    if not token_mp:
        st.error("Erro de configuração do Pagamento. Contate o suporte.")
        return

    if not user.get('id_pagamento_mp'):
        if st.button("💠 Gerar QR Code PIX"):
            with st.spinner("Gerando cobrança..."):
                url = "https://api.mercadopago.com/v1/payments"
                headers = {"Authorization": f"Bearer {token_mp}", "X-Idempotency-Key": str(uuid.uuid4())}
                payload = {
                    "transaction_amount": 1.00,
                    "description": f"Mensalidade - {user['nome']}",
                    "payment_method_id": "pix",
                    "payer": {"email": user['email']}
                }
                
                try:
                    res = requests.post(url, json=payload, headers=headers).json()
                    if "id" in res:
                        mp_id = str(res["id"])
                        supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
                        supabase.table("usuarios_app").update({"id_pagamento_mp": mp_id}).eq("id", user['id']).execute()
                        st.session_state.user_info['id_pagamento_mp'] = mp_id
                        st.rerun()
                    else:
                        st.error(f"Erro MP: {res.get('message')}")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")
    else:
        mp_id = user['id_pagamento_mp']
        url = f"https://api.mercadopago.com/v1/payments/{mp_id}"
        headers = {"Authorization": f"Bearer {token_mp}"}
        
        try:
            res = requests.get(url, headers=headers).json()
            if res.get("status") == "approved":
                st.success("Pagamento Aprovado! Seu acesso será liberado em instantes.")
                supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
                supabase.table("usuarios_app").update({"bloqueado": False, "status_pagamento": True}).eq("id", user['id']).execute()
                time.sleep(2)
                st.rerun()
            elif "point_of_interaction" in res:
                dados_pix = res["point_of_interaction"]["transaction_data"]
                qr_base64 = dados_pix["qr_code_base64"]
                copia_cola = dados_pix["qr_code"]
                
                with st.container(border=True):
                    c_img, c_info = st.columns([1, 2])
                    c_img.image(f"data:image/jpeg;base64,{qr_base64}", width=200)
                    c_info.info("Escaneie o QR Code ou copie o código abaixo:")
                    c_info.code(copia_cola, language="text")
                
                if st.button("🔄 Verificar se aprovou"):
                    st.rerun()
        except:
            st.warning("Aguardando confirmação do banco...")

def renderizar_edicao_perfil(supabase_client, user):
    """
    Renderiza um formulário retrátil para o atleta editar seus próprios dados.
    Deve ser colocado acima do botão do Strava.
    """
    # Expander para não ocupar espaço visual se não for usado
    with st.expander("⚙️ Editar Meus Dados / Senha", expanded=False):
        with st.form(key="form_edit_proprio_perfil"):
            c1, c2 = st.columns(2)
            
            # Campos preenchidos com os dados atuais
            novo_nome = c1.text_input("Nome", value=user.get('nome', ''))
            novo_tel = c2.text_input("WhatsApp", value=user.get('telefone', ''))
            
            # Tratamento da data (para não dar erro se for None)
            data_atual = user.get('data_nascimento')
            if data_atual:
                val_data = datetime.strptime(str(data_atual), '%Y-%m-%d').date()
            else:
                val_data = date(1990, 1, 1)
                
            nova_data = c1.date_input("Nascimento", value=val_data, format="DD/MM/YYYY")
            nova_senha = c2.text_input("Nova Senha (opcional)", type="password", help="Deixe vazio para manter a atual")
            
            if st.form_submit_button("💾 Atualizar Meus Dados"):
                dados_update = {
                    "nome": novo_nome,
                    "telefone": novo_tel,
                    "data_nascimento": str(nova_data)
                }
                
                # Só atualiza a senha se o usuário digitou algo novo
                if nova_senha:
                    dados_update["senha"] = nova_senha
                
                try:
                    supabase_client.table("usuarios_app").update(dados_update).eq("id", user['id']).execute()
                    
                    # Atualiza a sessão local para refletir a mudança imediatamente
                    st.session_state.user_info.update(dados_update)
                    
                    st.toast("Perfil atualizado com sucesso!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")