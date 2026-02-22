import streamlit as st
import time
import requests
import uuid
from datetime import datetime, date
from twilio.rest import Client
import re
from supabase import create_client

# ============================================================================
# 1. FUNÇÕES DE NOTIFICAÇÃO (WHATSAPP)
# ============================================================================

def enviar_notificacao_treino(dados_treino, nome_atleta, telefone_atleta):
    try:
        # Puxa do st.secrets (que configuraremos no Deploy)
        sid = st.secrets["twilio"]["TWILIO_SID"]
        token = st.secrets["twilio"]["TWILIO_TOKEN"]
        from_number = f"whatsapp:+{st.secrets['twilio']['TWILIO_PHONE_NUMBER']}"
        
        # Limpa o número para evitar o erro do "55" duplicado
        apenas_numeros = "".join(filter(str.isdigit, str(telefone_atleta)))
        if not apenas_numeros.startswith('55'):
            apenas_numeros = "55" + apenas_numeros
            
        to_number = f"whatsapp:+{apenas_numeros}"

        client = Client(sid, token)
        
        corpo_msg = (
            f"🤖 *Zaptreino: Treino Sincronizado*\n\n"
            f"👤 Atleta: {nome_atleta}\n"
            f"📏 Distância: {dados_treino['distancia']}\n"
            f"⏱️ Duração: {dados_treino['duracao']}\n"
            f"📊 TRIMP Semanal: {dados_treino.get('trimp_semanal', '-')}"
        )
        
        msg = client.messages.create(body=corpo_msg, from_=from_number, to=to_number)
        return True, msg.sid
    except Exception as e:
        return False, str(e)

# ============================================================================
# 2. FUNÇÕES AUXILIARES DE BANCO
# ============================================================================

def atualizar_data_vencimento(supabase, user_id, nova_data):
    try:
        supabase.table("usuarios_app").update({"data_vencimento": str(nova_data)}).eq("id", str(user_id)).execute()
        st.toast("Data salva!", icon="💾")
    except:
        st.toast("Erro ao salvar data.", icon="⚠️")

def alternar_bloqueio(supabase, user_id, status_atual_bloqueado):
    novo_bloqueio = not status_atual_bloqueado
    try:
        supabase.table("usuarios_app").update({
            "bloqueado": novo_bloqueio,
            "status_pagamento": not novo_bloqueio 
        }).eq("id", str(user_id)).execute()
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"Erro no banco: {e}")

# ============================================================================
# 3. TELAS DO SISTEMA
# ============================================================================
def renderizar_tela_login(supabase_client):
    st.markdown("""
        <style>
        /* 1. Box Principal e Topo */
        .block-container {
            padding-top: 3rem !important;
            max-width: 650px !important;
        }

        /* 2. Centraliza TÍTULOS dos campos (E-mail, Senha, etc) */
        div[data-testid="stForm"] label p {
            text-align: center !important;
            width: 100% !important;
            display: flex !important;
            justify-content: center !important;
            font-weight: 500 !important;
        }

        /* 3. Centraliza a caixa da LGPD */
        div[data-testid="stCheckbox"] {
            display: flex !important;
            justify-content: center !important;
        }

        /* 4. PINTA O BOTÃO COM O LARANJA DO ZAPTREINO */
        div[data-testid="stFormSubmitButton"] button {
            background-color: #FF5722 !important; 
            border-color: #FF5722 !important;
            color: white !important;
            border-radius: 8px !important;
            height: 3.5em !important;
            font-weight: bold !important;
            margin-top: 10px !important;
        }
        
        div[data-testid="stFormSubmitButton"] button:hover {
            background-color: #E64A19 !important; 
            border-color: #E64A19 !important;
            color: white !important;
        }

        /* 5. Centraliza Abas e pinta a linha debaixo delas de laranja */
        .stTabs [data-baseweb="tab-list"] {
            justify-content: center;
        }
        .stTabs [aria-selected="true"] {
            color: #FF5722 !important;
            border-bottom-color: #FF5722 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Logo
    col_vazia1, col_logo, col_vazia2 = st.columns([0.5, 2, 0.5])
    with col_logo:
        # CORREÇÃO 1: Substituído para width="stretch"
        st.image("assets/logo_zaptreino.png", width="stretch")
        
    st.markdown("<br>", unsafe_allow_html=True)

    aba_login, aba_cadastro = st.tabs(["Fazer Login", "Criar Conta"])
    
    with aba_login:
        with st.form("form_login"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            
            # CORREÇÃO 2: Substituído para width="stretch"
            if st.form_submit_button("Entrar", width="stretch"):
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
            data_nasc = st.date_input("Data de Nascimento", value=date(1940, 1, 1), format="DD/MM/YYYY")
            nova_senha = st.text_input("Defina uma Senha", type="password")
            confirma_senha = st.text_input("Confirme a Senha", type="password")
            
            st.divider()
            st.markdown("<h4 style='text-align: center;'>Termos e Privacidade</h4>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: gray; font-size: 14px;'>Ao clicar em aceitar, você concorda com os nossos Termos de Uso e Política de Privacidade (LGPD).</p>", unsafe_allow_html=True)
            aceite_termos = st.checkbox("Eu li e aceito os termos e condições.")
            
            # CORREÇÃO 3: Substituído para width="stretch"
            botao_cadastrar = st.form_submit_button("Cadastrar", width="stretch")
            
            if botao_cadastrar:
                if not (novo_nome and novo_email and novo_telefone and nova_senha and data_nasc):
                    st.warning("⚠️ Preencha todos os campos obrigatórios.")
                elif nova_senha != confirma_senha:
                    st.error("❌ As senhas não coincidem.")
                elif not aceite_termos:
                    st.error("🔒 É necessário aceitar os termos da LGPD.")
                else:
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
                        dados["id"] = str(uuid.uuid4())
                        supabase_client.table("usuarios_app").insert(dados).execute()
                        st.balloons()
                        st.success("Conta criada! Faça login na aba ao lado.")
                    except:
                        st.error("Erro ao cadastrar. E-mail já existe?")

def renderizar_tela_admin(supabase_client):
    st.title("Painel Admin 🔒")
    
    # Busca usuários
    try:
        users = supabase_client.table("usuarios_app").select("*").order("nome").execute().data
        if users:
            for user in users:
                # Pula o administrador para ele não aparecer na lista
                if user.get('is_admin'): continue
                
                with st.container(border=True):
                    # Dividimos em 3 colunas para caber a Data de Vencimento no meio
                    c1, c2, c3 = st.columns([2, 1.5, 1.5])
                    
                    # Coluna 1: Nome e Email
                    with c1:
                        # Desce o texto levemente para alinhar com o input de data
                        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                        st.write(f"**{user['nome']}**")
                        st.caption(f"{user['email']}")
                    
                    # --- 2. DATA DE VENCIMENTO ---
                    with c2:
                        venc_atual = user.get('data_vencimento')
                        try:
                            val_venc = datetime.strptime(str(venc_atual), '%Y-%m-%d').date() if venc_atual else date.today()
                        except:
                            val_venc = date.today()
                            
                        nova_data = st.date_input("Vencimento", value=val_venc, key=f"data_{user['id']}")
                        if st.button("💾 Salvar Data", key=f"btn_venc_{user['id']}", width="stretch"):
                            atualizar_data_vencimento(supabase_client, user['id'], nova_data)
                    
                    # --- 1. BOTÕES DE BLOQUEIO (AGORA ALINHADOS) ---
                    with c3:
                        # MÁGICA DO ALINHAMENTO: Empurra o botão exatos 28px para baixo, 
                        # compensando o espaço ocupado pela palavra "Vencimento" na coluna 2.
                        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                        
                        if user.get('bloqueado'):
                            # Botão Liberar (Verde/Padrão)
                            if st.button("🟢 Liberar", key=f"lib_{user['id']}", width="stretch"):
                                alternar_bloqueio(supabase_client, user['id'], True)
                        else:
                            # Botão Bloquear (Vermelho/Laranja com type="primary")
                            if st.button("🔴 Bloquear", key=f"bloq_{user['id']}", type="primary", width="stretch"):
                                alternar_bloqueio(supabase_client, user['id'], False)
                    
                    # --- 3. CAMPOS DE EDIÇÃO DOS ALUNOS ---
                    with st.expander("✏️ Editar / Excluir Aluno"):
                        with st.form(key=f"form_edit_{user['id']}"):
                            col_ed1, col_ed2 = st.columns(2)
                            ed_nome = col_ed1.text_input("Nome", value=user.get('nome', ''))
                            ed_tel = col_ed2.text_input("WhatsApp", value=user.get('telefone', ''))
                            
                            # Botão de salvar a edição do aluno
                            if st.form_submit_button("💾 Atualizar Dados", width="stretch"):
                                try:
                                    supabase_client.table("usuarios_app").update({
                                        "nome": ed_nome,
                                        "telefone": ed_tel
                                    }).eq("id", user['id']).execute()
                                    st.success("Aluno atualizado com sucesso!")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao atualizar: {e}")
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Botão de exclusão definitiva
                        if st.button("🗑️ Excluir Definitivamente", key=f"del_{user['id']}", type="primary", width="stretch"):
                            try:
                                supabase_client.table("usuarios_app").delete().eq("id", user['id']).execute()
                                st.warning("Usuário excluído do sistema.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")

    except Exception as e:
        st.error(f"Erro ao carregar lista de alunos: {e}")

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
    """
    # ==========================================================
    # 1. BUSCA O VENCIMENTO DIRETO DO BANCO DE DADOS
    # ==========================================================
    vencimento_banco = None
    try:
        res = supabase_client.table("usuarios_app").select("data_vencimento").eq("id", user['id']).execute()
        if res.data and len(res.data) > 0:
            vencimento_banco = res.data[0].get("data_vencimento")
    except:
        pass
        
    if not vencimento_banco:
        vencimento_banco = user.get("data_vencimento")

    # Formata a data para exibir
    if vencimento_banco:
        try:
            data_obj = datetime.strptime(str(vencimento_banco).strip(), '%Y-%m-%d')
            data_texto = data_obj.strftime('%d/%m/%Y')
        except:
            data_texto = str(vencimento_banco)
    else:
        data_texto = "Data não definida"

    # MOSTRA A DATA EM DESTAQUE LARANJA
    st.markdown(f"""
        <div style='background-color: #FFF3E0; border-left: 5px solid #FC4C02; padding: 10px; border-radius: 5px; margin-bottom: 15px;'>
            <h4 style='color: #FC4C02; margin: 0; font-size: 16px;'>📅 Vencimento do Plano: {data_texto}</h4>
        </div>
    """, unsafe_allow_html=True)
    # ==========================================================

    with st.expander("⚙️ Editar Meus Dados / Senha", expanded=False):
        with st.form(key="form_edit_proprio_perfil"):
            c1, c2 = st.columns(2)
            
            novo_nome = c1.text_input("Nome", value=user.get('nome', ''))
            novo_tel = c2.text_input("WhatsApp", value=user.get('telefone', ''))
            
            data_atual = user.get('data_nascimento')
            if data_atual:
                try:
                    val_data = datetime.strptime(str(data_atual), '%Y-%m-%d').date()
                except:
                    val_data = date(1990, 1, 1)
            else:
                val_data = date(1990, 1, 1)
                
            nova_data = c1.date_input("Nascimento", value=val_data, format="DD/MM/YYYY")
            nova_senha = c2.text_input("Nova Senha (opcional)", type="password", help="Deixe vazio para manter a atual")
            
            if st.form_submit_button("💾 Atualizar Meus Dados", width="stretch"):
                dados_update = {
                    "nome": novo_nome,
                    "telefone": novo_tel,
                    "data_nascimento": str(nova_data)
                }
                
                if nova_senha:
                    dados_update["senha"] = nova_senha
                
                try:
                    supabase_client.table("usuarios_app").update(dados_update).eq("id", user['id']).execute()
                    
                    st.session_state.user_info.update(dados_update)
                    st.toast("Perfil atualizado com sucesso!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")