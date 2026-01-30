import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import hashlib, urllib.parse, requests
from supabase import create_client
from twilio.rest import Client 

# ==========================================
# VERSÃO: v6.2 (RODAPÉ EM BUTILT-IN BASE64)
# ==========================================

st.set_page_config(page_title="Fábio Assessoria v6.2", layout="wide", page_icon="🏃‍♂️")

# --- CONEXÕES ---
try:
    supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
    
    TW_SID = st.secrets.get("TWILIO_ACCOUNT_SID")
    TW_TOKEN = st.secrets.get("TWILIO_AUTH_TOKEN")
    TW_FROM = st.secrets.get("TWILIO_PHONE_NUMBER")
    TW_TO = st.secrets.get("MEU_CELULAR")
    twilio_pronto = all([TW_SID, TW_TOKEN, TW_FROM, TW_TO])
except Exception as e:
    st.error("Erro nas Secrets.")
    st.stop()

REDIRECT_URI = "https://seu-treino-app.streamlit.app/" 
pix_copia_e_cola = "00020126440014BR.GOV.BCB.PIX0122fabioh1979@hotmail.com52040000530398654040.015802BR5912Fabio Hanada6009SAO PAULO62140510cfnrrCpgWv63043E37" 

# --- FUNÇÕES ---
def hash_senha(senha): return hashlib.sha256(str.encode(senha)).hexdigest()

def formatar_data_br(data_str):
    if not data_str or str(data_str) == "None": return "Pendente"
    try: return datetime.strptime(str(data_str), '%Y-%m-%d').strftime('%d/%m/%Y')
    except: return str(data_str)

def notificar_pagamento_admin(aluno_nome, aluno_email):
    try:
        check = supabase.table("alertas_admin").select("*").eq("email_aluno", aluno_email).eq("lida", False).execute()
        if not check.data:
            supabase.table("alertas_admin").insert({"email_aluno": aluno_email, "mensagem": f"Novo pagamento detectado {aluno_nome.upper()}, confira no banco.", "lida": False}).execute()
    except: pass

def sincronizar_strava(auth_code, aluno_id):
    token_url = "https://www.strava.com/oauth/token"
    payload = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'code': auth_code, 'grant_type': 'authorization_code'}
    try:
        r = requests.post(token_url, data=payload).json()
        if 'access_token' in r:
            token = r['access_token']
            header = {'Authorization': f"Bearer {token}"}
            atividades = requests.get("https://www.strava.com/api/v3/athlete/activities", headers=header).json()
            for act in atividades:
                if act['type'] == 'Run':
                    dados = {"aluno_id": aluno_id, "data": act['start_date_local'][:10], "nome_treino": act['name'], "distancia": round(act['distance'] / 1000, 2), "tempo_min": round(act['moving_time'] / 60, 2), "fc_media": act.get('average_heartrate', 130), "strava_id": str(act['id'])}
                    supabase.table("treinos_alunos").upsert(dados, on_conflict="strava_id").execute()
            return True
    except: return False
    return False

# --- LOGIN ---
if "logado" not in st.session_state: st.session_state.logado = False
params = st.query_params
if "code" in params and "user_mail" in params:
    u = supabase.table("usuarios_app").select("*").eq("email", params["user_mail"]).execute()
    if u.data:
        st.session_state.logado, st.session_state.user_info = True, u.data[0]
        sincronizar_strava(params["code"], u.data[0]['id'])
        st.query_params.clear()
        st.query_params["user_mail"] = u.data[0]['email']

if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🏃‍♂️ Fábio Assessoria</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        tab_login, tab_cadastro = st.tabs(["🔑 Entrar", "📝 Novo Aluno"])
        with tab_login:
            with st.form("login_form"):
                e, s = st.text_input("E-mail"), st.text_input("Senha", type="password")
                if st.form_submit_button("Acessar Painel", use_container_width=True):
                    u = supabase.table("usuarios_app").select("*").eq("email", e).eq("senha", hash_senha(s)).execute()
                    if u.data:
                        st.session_state.logado, st.session_state.user_info = True, u.data[0]
                        st.query_params["user_mail"] = e
                        st.rerun()
                    else: st.error("E-mail ou senha incorretos.")
        with tab_cadastro:
            with st.form("cad_form"):
                n_nome = st.text_input("Nome Completo")
                n_email = st.text_input("E-mail")
                n_senha = st.text_input("Crie uma Senha", type="password")
                aceite = st.checkbox("Li e aceito os Termos de Uso e LGPD.")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    if not aceite: st.error("Aceite os termos.")
                    elif n_nome and n_email and n_senha:
                        try:
                            supabase.table("usuarios_app").insert({"nome": n_nome, "email": n_email, "senha": hash_senha(n_senha), "status_pagamento": False}).execute()
                            st.success("Cadastro realizado!")
                        except: st.error("E-mail já existe.")
    st.stop()

user = st.session_state.user_info
eh_admin = user.get('is_admin', False)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {user['nome']}")
    if not eh_admin:
        redirect_com_email = f"{REDIRECT_URI}?user_mail={user['email']}"
        link_strava = f"https://www.strava.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={urllib.parse.quote(redirect_com_email)}&scope=activity:read_all&approval_prompt=auto"
        st.markdown(f'''<a href="{link_strava}" target="_self" style="text-decoration: none;"><div style="background-color: #FC4C02; color: white; padding: 12px; border-radius: 6px; text-align: center; font-weight: bold; margin-bottom: 20px;">Connect with STRAVA</div></a>''', unsafe_allow_html=True)
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.clear(); st.query_params.clear(); st.rerun()

# --- CONTEÚDO ---
if eh_admin:
    st.title("👨‍🏫 Central do Treinador")
    res_alertas = supabase.table("alertas_admin").select("*").eq("lida", False).execute()
    if res_alertas.data:
        for a in res_alertas.data: st.error(f"🚨 {a['mensagem']}")
    st.divider()
    alunos = supabase.table("usuarios_app").select("*").eq("is_admin", False).execute()
    for aluno in alunos.data:
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 1.5, 1.5])
            with c1: st.markdown(f"**{aluno['nome']}**\n\nStatus: {'✅ Ativo' if aluno['status_pagamento'] else '❌ Bloqueado'}")
            with c2:
                venc_atual = datetime.strptime(str(aluno.get('data_vencimento', date.today())), '%Y-%m-%d').date() if aluno.get('data_vencimento') else date.today()
                nova_dt = st.date_input("Vencimento", value=venc_atual, key=f"d_{aluno['id']}")
            with c3:
                if st.button("💾 Salvar", key=f"s_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"data_vencimento": str(nova_dt), "status_pagamento": True}).eq("id", aluno['id']).execute()
                    st.rerun()
                txt_btn = "🔒 Bloquear" if aluno['status_pagamento'] else "🔓 Liberar"
                if st.button(txt_btn, key=f"b_{aluno['id']}", use_container_width=True):
                    supabase.table("usuarios_app").update({"status_pagamento": not aluno['status_pagamento']}).eq("id", aluno['id']).execute()
                    st.rerun()

else:
    st.title(f"🚀 Dashboard: {user['nome']}")
    if not user.get('status_pagamento'):
        notificar_pagamento_admin(user['nome'], user['email'])
        st.error("⚠️ Acesso pendente de renovação.")
        with st.expander("💳 Dados para Pagamento PIX", expanded=True):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(pix_copia_e_cola)}")
            st.code(pix_copia_e_cola)
        st.stop()
    
    st.info(f"📅 Plano ativo até: **{formatar_data_br(user.get('data_vencimento'))}**")
    res = supabase.table("treinos_alunos").select("*").eq("aluno_id", user['id']).order("data", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['TRIMP'] = df['tempo_min'] * (df['fc_media'] / 100)
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.bar(df, x='data', y='TRIMP', title="Carga de Treino", color_discrete_sequence=['#FC4C02']), use_container_width=True)
        with c2: st.plotly_chart(px.line(df, x='data', y='fc_media', title="FC Média", markers=True), use_container_width=True)
        st.dataframe(df[['data', 'nome_treino', 'distancia', 'tempo_min', 'fc_media', 'TRIMP']], use_container_width=True, hide_index=True)

# --- RODAPÉ INFALÍVEL (IMAGEM EMBUTIDA NO CÓDIGO) ---
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.divider()
# Logotipo horizontal 'Powered by Strava' em Base64
strava_logo_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAKAAAABACAYAAABfLbxXAAAACXBIWXMAAAsTAAALEwEAmpwYAAADJGlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDAgNzkuMTYwNDUxLCAyMDE3LzA1LzA2LTAxOjA4OjIxICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIiB4bWxuczp4bXBSTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1sbnM6c3RSZWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZVJlZiMiIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDozRTI2ODFCNERCMUExMUU4ODIwM0U0OThDMkFFMkM3RiIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDozRTI2ODFCM0RCMUExMUU4ODIwM0U0OThDMkFFMkM3RiIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ0MgKFdpbmRvd3MpIj4gPHhtcE1NOkRlcml2ZWRGcm9tIHN0UmVmOmluc3RhbmNlSUQ9InhtcC5paWQ6M0M4NkJEMUREQjA5MTFFODg3NTVCOEEzODVFMDAzOTciIHN0UmVmOmRvY3VtZW50SUQ9InhtcC5kaWQ6M0M4NkJEMUVEQjA5MTFFODg3NTVCOEEzODVFMDAzOTciLz4gPC9yZGY6RGVzY3JpcHRpb24+IDwvcmRmOlJERj4gPC94OnhtcG1ldGE+IDw/eHBhY2tldCBlbmQ9InciPz500v0sAAAFVUlEQVR4Ae3dW2hcVRzH8f9JmqatidZWTfSiaCOitS8VQYv1UvGlYvFFfKmo9clXfRER9Unf9EXxQfGl6IP6pIofFPHSSh9EUYstSIsatUnTtE3S9P99Z87p7GQyOzt7Zs5M9vlgmDln9v7v2Xv2P/vstfbeZ6YpIIvK6uS8Vp06v+qT3mX9D708p79On9LfoK/q99pXv9G+f9Bf1p+yXy6O20tD689G7Y6D3v6A9lR2n+V5Xf2I/ov2f6i608T0GqA079A39AetN+qf6j/pN+g36A+pM868P9V/qf9R/6v+X/0B/UH9Ef0Z/Vn9Sfs+S86L6Z3A/R8MAn9D75H7+D5B+S/y+W96r9C9W8yFzE/L/I78L/XvK/I35V/K/3T8y8m9jPxPyP88v2v41vC7id/N/I6p/B7m9zK/m/m99O9l6vO87+V3K/9X9H+V91/h9w6/9/i9S++v6X09ve+m96P0fpze99L7cXo/Tu8n6P0EvZ+i9zP0fo7eB+l9kN6H6f0IvY/S+zF6H6f3E/S+l9736v2U3k8v9tOL9dOL9dOL9dOL9dOL9dOL9dOL9dOL9X/0L9ZPL9ZPL9ZPL9ZPL9ZPL9ZPL9ZPL9ZPL9ZPL9ZPL/7Wv9gf9m/S79Ef9+7S79ef9u7Tn/Lu05/x7tdf8u7XX/Hu19/2HtBf8R7UX/Me0t/0vtef9p7W3/O+19f/7mS70/A7uW630u2mu812u+luM91uuttst9vutrtut+N2u+52O+6+R7v/8W5v3X0Pd/vr7nuo219336Pdvrv77u726+77eLe/7m7X3fbv9NfN3+Gvmd/Nr9mfN7+Ofu78OfNr5ufN79afKb86f1p/lvzq+Pnxc+Pnzs+Nnxu/f/zM+Jnxa8Y/Yfzj58XPi58XPy9+Xvy8+Hnx8+Lnx8+Lnx8+L35e/Lz4efHz4ufFz4ufFz8vfl78vPh58fPi58XPi58XPy/+ef5jxt9u/G3G32b8bebfZvwdxu8yfpfxdxh/h/GvN/71xl9t/NXGX2X8XcavNP6Vxj9u/OPGP27848Y/bvzjxt9u/O3G32787cZfafxK419p/CrjVxp/tfGrjF9l/FXGX2X8VcZfbfzVxl9t/NXGrzT+W8af8H7T8p/Y92+2P2Y92/Vvt98x/7T1T1m/Y/6m+Zute7X97fPXWl+zvrH9r9vPWH/Y+vXW7Xq6XU+36+l2Pd2up9v1dLuebtfT7Xq6XU+36+l2Pd2u76S79fR0u56ebtfT0+16erpdT0+36+npdj093a6np9v19HS7np5u19PT0+16eXq6XS9PT7fr5enpdr08Pd2ul6en2/Xy9HS7Xp6ebtfL09Ptenl6un36P9p1p/0L9Xm6L6f7crp/f79An9LfoE/pb9BX9Xvtq99o3z/oL+tP2S8Xx+2lofc/0Psz+hP6K/oLetfA8M9Y/8v+S/Yf+5f9eP2zW/+m7H/R/p/9f9v/Y/v/tv8f9/8f9///7P8Z/xn7P/v7O9Zz7P/v/o9X9+H9H/vH68949Xm6z+lO72P9fXr6T/9u/QX6C/ov+m/6Nfof+h36L7ru9S/9Ov0vXTfdf9Gv09Xp/UXXv7u96X/vunV/0fXm3nXL/UXX/769uXe9ueu++X9v/2V9Y+vW9df7fL3L9O7T09XpPaunq9N7Rk+vAUpzXn9df9p+qXid3D/O9I/v77Ouv76m9289/S97/9L8jP4X+of1X7T/p9V6n1Xr6X9p/Y/+Uf1vXT9p/YfW96v9v6t6X09Pr997TfV7r6vXz75/6/Wz7z+vXj/7fm+un33/96vXz76frp99/6fVf/F79f8B7Qd8v61pE7EAAAAASUVORK5CYII="

# Aplicando o rodapé blindado
st.write("") # Espaço
st.markdown(
    f"""
    <div style="display: flex; justify-content: flex-end; align-items: center; padding: 10px;">
        <img src="{strava_logo_base64}" width="150">
    </div>
    """, 
    unsafe_allow_html=True
)
