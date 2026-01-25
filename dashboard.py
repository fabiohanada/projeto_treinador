import streamlit as st
import pandas as pd
import os
import requests
from supabase import create_client
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from twilio.rest import Client
import hashlib

# 1. Configurações Iniciais
load_dotenv()
st.set_page_config(page_title="Elite Performance", layout="wide")

def get_secret(key):
    try:
        if key in st.secrets: return st.secrets[key]
    except: pass
    return os.getenv(key)

# Conexão Supabase
supabase = create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))

# --- FUNÇÕES DE SEGURANÇA ---
def hash_senha(senha):
    return hashlib.sha256(str.encode(senha)).hexdigest()

def validar_login(email, senha):
    senha_hash = hash_senha(senha)
    res = supabase.table("usuarios_app").select("*").eq("email", email).eq("senha", senha_hash).execute()
    return res.data[0] if res.data else None

def cadastrar_usuario(nome, email, senha):
    senha_hash = hash_senha(senha)
    payload = {"nome": nome, "email": email, "senha": senha_hash}
    try:
        supabase.table("usuarios_app").insert(payload).execute()
        return True
    except:
        return False

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_info = None

# --- TELA DE LOGIN / CADASTRO ---
if not st.session_state.logado:
    st.title("🔐 Acesso Elite Performance")
    
    aba1, aba2 = st.tabs(["Login", "Cadastrar Novo Treinador"])
    
    with aba1:
        email_l = st.text_input("Email")
        senha_l = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            user = validar_login(email_l, senha_l)
            if user:
                st.session_state.logado = True
                st.session_state.user_info = user
                st.rerun()
            else:
                st.error("Email ou senha incorretos.")

    with aba2:
        nome_c = st.text_input("Nome Completo")
        email_c = st.text_input("Email de Acesso")
        senha_c = st.text_input("Criar Senha", type="password")
        if st.button("Finalizar Cadastro"):
            if nome_c and email_c and senha_c:
                if cadastrar_usuario(nome_c, email_c, senha_c):
                    st.success("Cadastro realizado! Vá para a aba Login.")
                else:
                    st.error("Erro ao cadastrar. Email já pode existir.")
    st.stop() # Interrompe o código aqui se não estiver logado

# --- SE CHEGOU AQUI, ESTÁ LOGADO (DASHBOARD) ---
st.sidebar.write(f"Bem-vindo, **{st.session_state.user_info['nome']}**!")
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

# [O RESTO DO SEU CÓDIGO DO DASHBOARD CONTINUA AQUI ABAIXO...]
# (Sincronização, Gráficos, etc.)
st.title("📊 Painel de Performance")
# ... (Cole aqui o restante do seu código anterior)
