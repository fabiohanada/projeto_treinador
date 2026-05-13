import streamlit as st
import time
import requests
import uuid
from datetime import date, datetime, timedelta
from twilio.rest import Client
import re
from supabase import create_client
import base64

# ============================================================================
# 1. FUNÇÕES DE NOTIFICAÇÃO (WHATSAPP)
# ============================================================================

def enviar_notificacao_treino(dados_treino, nome_atleta, telefone_atleta=None):
    try:
        sid = st.secrets.get("TWILIO_SID")
        token = st.secrets.get("TWILIO_TOKEN")
        from_raw = str(st.secrets.get("TWILIO_PHONE_NUMBER")).strip()
        
        if telefone_atleta:
            tel_limpo = ''.join(filter(str.isdigit, str(telefone_atleta)))
            if len(tel_limpo) <= 11:
                tel_limpo = f"55{tel_limpo}"
            to_number = f"whatsapp:+{tel_limpo}"
        else:
            to_raw = str(st.secrets.get("MEU_CELULAR")).strip()
            to_number = f"whatsapp:+{to_raw}"

        from_number = f"whatsapp:+{from_raw}"
        client = Client(sid, token)
        
        if dados_treino and dados_treino.get("manutencao"):
            corpo_msg = (
                f"🤖 *Zaptreino Online*\n\n"
                f"Fala {nome_atleta}, o sistema está monitorando seu Strava! ✅"
            )
        else:
            dist = dados_treino.get('distancia', '-')
            tempo = dados_treino.get('duracao_formatada', '00:00')
            t_atual = dados_treino.get('trimp_score', 0)
            e_atual = dados_treino.get('emoji_dia', '🟢')
            t_sem = dados_treino.get('trimp_semanal', '-')
            e_sem = dados_treino.get('emoji_semana', '')
            t_men = dados_treino.get('trimp_mensal', '-')
            e_men = dados_treino.get('emoji_mensal', '')
            nome_atividade = dados_treino.get('name', 'Treino')
            
            dias_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
            data_raw = dados_treino.get('data_treino', datetime.now().strftime('%Y-%m-%d'))
            try:
                data_obj = datetime.strptime(data_raw, '%Y-%m-%d')
                dia_semana = dias_pt[data_obj.weekday()]
                data_formatada = f"{dia_semana}, {data_obj.strftime('%d/%m/%y')}"
            except:
                data_formatada = data_raw

            aviso_especifico = dados_treino.get('aviso_seguranca', '')

            corpo_msg = (
                f"🏃‍♂️ *Zaptreino Alerta*\n\n"
                f"Fala {nome_atleta}, *novo* treino sincronizado! 🔵\n"
                f"🏋️‍♂️ *Atividade:* {nome_atividade}\n"
                f"📅 *Data:* {data_formatada}\n"
                f"📏 Distância: {dist} km\n"
                f"⏱️ Tempo: {tempo}\n"
                f"🔥 *Carga Treino Atual:* {t_atual} {e_atual}\n\n"
                f"📊 *Carga 7d:* {t_sem} {e_sem}\n"
                f"📈 *Carga 30d:* {t_men} {e_men}"
                f"{aviso_especifico}\n\n"
                f"Bora pra cima! 👊"
            )
        
        client.messages.create(body=corpo_msg, from_=from_number, to=to_number)
        return True
    except Exception as e:
        print(f"❌ Erro Crítico no Twilio: {e}")
        return False

# ============================================================================
# 2. FUNÇÕES AUXILIARES DE BANCO
# ============================================================================

def atualizar_data_vencimento(supabase, user_id, nova_data):
    try:
        data_formatada = nova_data.strftime('%Y-%m-%d')
        supabase.table("usuarios_app").update({"data_vencimento": data_formatada}).eq("id", str(user_id)).execute()
        st.toast("Data salva com sucesso!", icon="💾")
        time.sleep(0.5)
        st.rerun()      
    except Exception as e:
        st.error(f"Erro detalhado do banco: {e}")

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
        .block-container {
            padding-top: 3rem !important;
            max-width: 650px !important;
        }
        div[data-testid="stForm"] label p {
            text-align: center !important;
            width: 100% !important;
            display: flex !important;
            justify-content: center !important;
            font-weight: 500 !important;
        }
        div[data-testid="stCheckbox"] {
            display: flex !important;
            justify-content: center !important;
        }
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
        .stTabs [data-baseweb="tab-list"] {
            justify-content: center;
        }
        .stTabs [aria-selected="true"] {
            color: #FF5722 !important;
            border-bottom-color: #FF5722 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    col_vazia1, col_logo, col_vazia2 = st.columns([0.5, 2, 0.5])
    with col_logo:
       st.image("assets/logo_zaptreino.png", width='stretch')
        
    st.markdown("<br>", unsafe_allow_html=True)

    aba_login, aba_cadastro = st.tabs(["Fazer Login", "Criar Conta"])
    
    with aba_login:
        with st.form("form_login"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            
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
            
            data_nasc = st.date_input(
                "Data de Nascimento",
                value=None,
                min_value=date(1920, 1, 1), 
                max_value=date.today(),      
                format="DD/MM/YYYY"
            )
            nova_senha = st.text_input("Defina uma Senha", type="password")
            confirma_senha = st.text_input("Confirme a Senha", type="password")
            
            st.divider()
            st.markdown("<h4 style='text-align: center;'>Termos e Privacidade</h4>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: gray; font-size: 14px;'>Ao clicar em aceitar, você concorda com os nossos Termos de Uso e Política de Privacidade (LGPD).</p>", unsafe_allow_html=True)
            aceite_termos = st.checkbox("Eu li e aceito os termos e condições.")
            
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
    
    try:
        users = supabase_client.table("usuarios_app").select("*").order("nome").execute().data
        if users:
            for user in users:
                if user.get('is_admin'): continue
                
                hoje = date.today()
                venc_atual = user.get('data_vencimento')
                try:
                    val_venc = datetime.strptime(str(venc_atual), '%Y-%m-%d').date() if venc_atual else hoje
                except:
                    val_venc = hoje
                    
                esta_expirado = hoje > val_venc
                bloqueio_manual = user.get('bloqueado', False)
                aluno_sem_acesso = esta_expirado or bloqueio_manual

                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1.5, 1.5])
                    
                    with c1:
                        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
                        st.write(f"**{user['nome']}**")
                        st.caption(f"{user['email']}")
                        if esta_expirado:
                            st.caption("⚠️ Plano Vencido")
                    
                    with c2:
                        nova_data = st.date_input("Vencimento", value=val_venc, key=f"data_{user['id']}")
                        if st.button("💾 Salvar Data", key=f"btn_venc_{user['id']}", width="stretch"):
                            atualizar_data_vencimento(supabase_client, user['id'], nova_data)
                    
                    with c3:
                        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                        
                        if aluno_sem_acesso:
                            if st.button("🟢 Liberar", key=f"lib_{user['id']}", width="stretch"):
                                alternar_bloqueio(supabase_client, user['id'], True)
                        else:
                            if st.button("🔴 Bloquear", key=f"bloq_{user['id']}", type="primary", width="stretch"):
                                alternar_bloqueio(supabase_client, user['id'], False)
                    
                    with st.expander("✏️ Editar / Excluir Aluno"):
                        with st.form(key=f"form_edit_{user['id']}"):
                            # Linha 1: Nome e WhatsApp
                            col_ed1, col_ed2 = st.columns(2)
                            ed_nome = col_ed1.text_input("Nome", value=user.get('nome', ''), key=f"nome_{user['id']}")
                            ed_tel = col_ed2.text_input("WhatsApp", value=user.get('telefone', ''), key=f"tel_{user['id']}")
                            
                            # Linha 2: E-mail e Nascimento
                            col_ed3, col_ed4 = st.columns(2)
                            ed_email = col_ed3.text_input("E-mail", value=user.get('email', ''), key=f"email_{user['id']}")
                            
                            data_nasc_atual = user.get('data_nascimento')
                            try:
                                val_nasc = datetime.strptime(str(data_nasc_atual), '%Y-%m-%d').date() if data_nasc_atual else date(1990, 1, 1)
                            except:
                                val_nasc = date(1990, 1, 1)
                            ed_nasc = col_ed4.date_input("Nascimento", value=val_nasc, format="DD/MM/YYYY", key=f"nasc_{user['id']}")

                            # Linha 3: Senha e Confirmação de Senha
                            col_ed5, col_ed6 = st.columns(2)
                            ed_senha = col_ed5.text_input("Nova Senha", type="password", key=f"senha_{user['id']}", help="Deixe em branco para manter a senha atual.")
                            ed_conf_senha = col_ed6.text_input("Confirmar Nova Senha", type="password", key=f"conf_senha_{user['id']}")
                            
                            if st.form_submit_button("💾 Atualizar Dados", width="stretch"):
                                if ed_senha and ed_senha != ed_conf_senha:
                                    st.error("❌ As senhas não coincidem. Tente novamente.")
                                else:
                                    try:
                                        dados_update_admin = {
                                            "nome": ed_nome,
                                            "telefone": ed_tel,
                                            "email": ed_email.strip().lower(),
                                            "data_nascimento": str(ed_nasc)
                                        }
                                        # Só atualiza a senha se você digitou alguma coisa
                                        if ed_senha:
                                            dados_update_admin["senha"] = ed_senha

                                        supabase_client.table("usuarios_app").update(dados_update_admin).eq("id", user['id']).execute()
                                        st.success("Aluno atualizado com sucesso!")
                                        time.sleep(1)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro ao atualizar: {e}")
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
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
        if st.button("💠 Gerar Cobrança PIX (R$ 10,00)", width="stretch"):
            with st.spinner("Gerando QR Code..."):
                url = "https://api.mercadopago.com/v1/payments"
                headers = {
                    "Authorization": f"Bearer {token_mp}", 
                    "X-Idempotency-Key": str(uuid.uuid4())
                }
                
                payload = {
                    "transaction_amount": 10.00,
                    "description": f"Mensalidade - {user['nome']}",
                    "payment_method_id": "pix",
                    "payer": {
                        "email": user['email'],
                        "first_name": user['nome'].split()[0]
                    }
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
                        st.error(f"Erro ao gerar: {res.get('message')}")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")
        st.stop() 

    else:
        mp_id = user['id_pagamento_mp']
        url = f"https://api.mercadopago.com/v1/payments/{mp_id}"
        headers = {"Authorization": f"Bearer {token_mp}"}
        
        try:
            res = requests.get(url, headers=headers).json()
            status = res.get("status")

            if status == "approved":
                st.success("✅ Pagamento Aprovado! Liberando acesso...")
                supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
                supabase.table("usuarios_app").update({
                    "bloqueado": False, 
                    "status_pagamento": True,
                    "id_pagamento_mp": None 
                }).eq("id", user['id']).execute()
                time.sleep(2)
                st.rerun()

            elif status == "pending":
                if "point_of_interaction" in res:
                    dados_pix = res["point_of_interaction"]["transaction_data"]
                    qr_base64 = dados_pix["qr_code_base64"]
                    copia_cola = dados_pix["qr_code"]
                    
                    with st.container(border=True):
                        st.info("Aguardando confirmação do PIX...")
                        c1, c2 = st.columns([1, 2])
                        c1.image(f"data:image/jpeg;base64,{qr_base64}", width=180)
                        c2.write("**Copie o código abaixo:**")
                        c2.code(copia_cola, language="text")
                        
                        if st.button("🔄 Verificar se já pagou", width="stretch"):
                            st.rerun()
                        
                        if st.button("❌ Cancelar e gerar novo PIX", type="secondary"):
                            supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
                            supabase.table("usuarios_app").update({"id_pagamento_mp": None}).eq("id", user['id']).execute()
                            st.rerun()
            
            else:
                st.warning("A cobrança anterior expirou.")
                if st.button("Gerar Nova Cobrança"):
                    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
                    supabase.table("usuarios_app").update({"id_pagamento_mp": None}).eq("id", user['id']).execute()
                    st.rerun()

        except:
            st.warning("Consultando status do pagamento...")

def renderizar_edicao_perfil(supabase_client, user):
    vencimento_banco = None
    try:
        res = supabase_client.table("usuarios_app").select("data_vencimento").eq("id", user['id']).execute()
        if res.data and len(res.data) > 0:
            vencimento_banco = res.data[0].get("data_vencimento")
    except:
        pass
        
    if not vencimento_banco:
        vencimento_banco = user.get("data_vencimento")

    if vencimento_banco:
        try:
            data_obj = datetime.strptime(str(vencimento_banco).strip(), '%Y-%m-%d')
            data_texto = data_obj.strftime('%d/%m/%Y')
        except:
            data_texto = str(vencimento_banco)
    else:
        data_texto = "Data não definida"

    st.markdown(f"""
        <div style='background-color: #FFF3E0; border-left: 5px solid #FC4C02; padding: 10px; border-radius: 5px; margin-bottom: 15px;'>
            <h4 style='color: #FC4C02; margin: 0; font-size: 16px;'>📅 Vencimento do Plano: {data_texto}</h4>
        </div>
    """, unsafe_allow_html=True)

    with st.expander("⚙️ Meus Dados e Calibragem Cardíaca", expanded=False):
        
        # ==========================================
        # FORMULÁRIO 1: DADOS PESSOAIS
        # ==========================================
        with st.form(key="form_edit_proprio_perfil"):
            st.subheader("Dados Pessoais")
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
            
            if st.form_submit_button("💾 Atualizar Dados Pessoais", width="stretch"):
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
                    st.toast("Dados pessoais atualizados!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar dados: {e}")

        # ==========================================
        # FORMULÁRIO 2: CALIBRAGEM CARDÍACA
        # ==========================================
        with st.form(key="form_calibragem_cardiaca"):
            st.subheader("💓 Calibragem Cardíaca")
            st.caption("Ajuste sua FC para que o cálculo de carga (TRIMP) seja exato.")
            
            col_fc1, col_fc2 = st.columns(2)
            fc_max = col_fc1.number_input("Sua FC Máxima (bpm)", value=int(user.get('fc_maxima', 185)), min_value=100, max_value=230)
            fc_rep = col_fc2.number_input("Sua FC Repouso (bpm)", value=int(user.get('fc_repouso', 60)), min_value=30, max_value=120)
            
            if st.form_submit_button("❤️ Atualizar Calibragem", width="stretch"):
                dados_update_fc = {
                    "fc_maxima": fc_max, 
                    "fc_repouso": fc_rep 
                }
                try:
                    supabase_client.table("usuarios_app").update(dados_update_fc).eq("id", user['id']).execute()
                    st.session_state.user_info.update(dados_update_fc)
                    st.toast("Calibragem cardíaca atualizada!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar calibragem: {e}")