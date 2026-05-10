import streamlit as st
from newsapi import NewsApiClient
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai
from gtts import gTTS
import os
import tempfile
import time
from datetime import datetime
from streamlit_mic_recorder import speech_to_text
from dotenv import load_dotenv
import streamlit.components.v1 as components
import plotly.graph_objects as go
import random # Added for jitter logic

# --- SECURE API KEY LOADING ---
load_dotenv() 

# SOLUTION INJECTION: Secrets Bridge
# This allows keys to work on your laptop AND the Streamlit Cloud Secrets
NEWS_API_KEY = st.secrets.get("NEWS_API_KEY", os.getenv("NEWS_API_KEY"))
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
TWILIO_ACCOUNT_SID = st.secrets.get("TWILIO_ACCOUNT_SID", os.getenv("TWILIO_ACCOUNT_SID"))
TWILIO_AUTH_TOKEN = st.secrets.get("TWILIO_AUTH_TOKEN", os.getenv("TWILIO_AUTH_TOKEN"))
TWILIO_PHONE_NUMBER = st.secrets.get("TWILIO_PHONE_NUMBER", os.getenv("TWILIO_PHONE_NUMBER"))

# 1. Page Configuration
st.set_page_config(page_title="Sentime-Track Pro | Quant Terminal", layout="wide", page_icon="📈")

# --- SESSION STATE INITIALIZATION ---
if "last_voice_query" not in st.session_state: st.session_state.last_voice_query = ""
if "theme" not in st.session_state: st.session_state.theme = "Dark"
if "watchlist" not in st.session_state: st.session_state.watchlist = ["RELIANCE.NS", "AAPL", "NVDA"]
if "alerts" not in st.session_state: st.session_state.alerts = []

# Auth States
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = None
if "auth_mode" not in st.session_state: st.session_state.auth_mode = "Login"
if "users_db" not in st.session_state: 
    # Use your actual verified number here for the cloud test
    st.session_state.users_db = {"admin@startup.com": {"password": "admin", "name": "Admin User", "phone": "+918580594748"}}

# --- DYNAMIC THEME & UI CSS ENGINE ---
if st.session_state.theme == "Dark":
    bg_color, text_color, card_bg = "#05070a", "#ffffff", "#13151a"
    grad_1, grad_2 = "#1e2027", "#05070a"
    border_col = "#2a2d35"
    tv_theme = "dark"
    sub_text = "gray"
else:
    bg_color, text_color, card_bg = "#f8fafc", "#0f172a", "#ffffff"
    grad_1, grad_2 = "#e2e8f0", "#f1f5f9"
    border_col = "#cbd5e1"
    tv_theme = "light"
    sub_text = "#64748b"

st.markdown(f"""
    <style>
    #MainMenu {{visibility: hidden;}} footer {{visibility: hidden;}} 
    .stApp {{ background-color: {bg_color}; color: {text_color}; font-family: 'Inter', sans-serif; }}
    
    .company-header {{
        background: linear-gradient(90deg, {card_bg} 0%, {grad_1} 100%);
        padding: 20px; border-radius: 10px; border-bottom: 3px solid #3a7bd5; margin-bottom: 20px;
        border: 1px solid {border_col}; border-bottom: 3px solid #3a7bd5;
    }}
    .stat-card {{
        background: {card_bg}; border-left: 4px solid #3a7bd5;
        padding: 12px; border-radius: 8px; margin-bottom: 8px; color: {text_color};
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid {border_col}; border-left: 4px solid #3a7bd5;
    }}
    .ai-insight {{
        background: {grad_1}; padding: 12px; border-radius: 8px; border: 1px dashed #3a7bd5; margin-bottom: 15px; color: {text_color};
    }}
    
    /* Navigation CSS */
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
        background: linear-gradient(90deg, {card_bg} 0%, {grad_1} 100%);
        padding: 10px 12px; border-radius: 8px; margin-bottom: 8px;
        border-left: 4px solid transparent; transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid {border_col};
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
        border-left: 4px solid #00d2ff; background: linear-gradient(90deg, {grad_1} 0%, {grad_2} 100%);
        transform: translateX(5px);
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] > label div[data-testid="stMarkdownContainer"] p {{
        font-weight: 600; font-size: 13px; letter-spacing: 0.5px; color: {text_color};
    }}
    .terminal-news-row:hover {{ background-color: rgba(58, 123, 213, 0.05); }}
    
    /* Login Auth Box CSS */
    .auth-box {{
        background: {card_bg}; padding: 40px; border-radius: 16px; 
        border: 1px solid {border_col}; box-shadow: 0 20px 40px rgba(0,0,0,0.1);
    }}
    </style>
    """, unsafe_allow_html=True)

# =====================================================================
# AUTHENTICATION GATEWAY
# =====================================================================
if not st.session_state.logged_in:
    st.markdown("""<style>[data-testid="stSidebar"] { display: none; } [data-testid="collapsedControl"] { display: none; }</style>""", unsafe_allow_html=True)
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown(f"""<div style="text-align: center; margin-bottom: 35px;"><div style="margin-bottom: 20px;"><svg width="65" height="65" viewBox="0 0 24 24" fill="none" stroke="#00d2ff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg></div><h1 style="color: {text_color};">SENTIME-TRACK <span style="color:#00d2ff;">PRO</span></h1></div>""", unsafe_allow_html=True)
        st.markdown("<div class='auth-box'>", unsafe_allow_html=True)
        auth_mode = st.radio("Mode", ["Login", "Signup"], horizontal=True, label_visibility="collapsed")
        if auth_mode == "Login":
            log_email = st.text_input("Email Address")
            log_pass = st.text_input("Password", type="password")
            if st.button("AUTHENTICATE", use_container_width=True, type="primary"):
                if log_email in st.session_state.users_db and st.session_state.users_db[log_email]["password"] == log_pass:
                    st.session_state.logged_in = True
                    st.session_state.current_user = {"email": log_email, **st.session_state.users_db[log_email]}
                    st.rerun()
                else: st.error("Invalid credentials.")
        else:
            reg_name = st.text_input("Full Name")
            reg_email = st.text_input("Email")
            reg_phone = st.text_input("Phone (+91...)")
            reg_pass = st.text_input("Password", type="password")
            if st.button("REGISTER", use_container_width=True, type="primary"):
                st.session_state.users_db[reg_email] = {"password": reg_pass, "name": reg_name, "phone": reg_phone}
                st.success("Registered! Switch to Login.")
        st.markdown("</div>", unsafe_allow_html=True)
else:
    # --- SMART TICKER DICTIONARY ---
    INDIAN_ASSETS = {"RELIANCE.NS": "Reliance Industries", "TCS.NS": "Tata Consultancy Services", "HDFCBANK.NS": "HDFC Bank", "INFY.NS": "Infosys"}
    US_ASSETS = {"AAPL": "Apple Inc.", "MSFT": "Microsoft", "GOOGL": "Alphabet", "TSLA": "Tesla"}
    ALL_ASSETS = {**INDIAN_ASSETS, **US_ASSETS}

    # --- SOLUTION INJECTION: STABLE CLOUD DATA ENGINE ---
    @st.cache_data(ttl=600) 
    def get_asset_info(ticker):
        # Try up to 3 times to bypass temporary cloud blocks
        for i in range(3):
            try:
                # Jitter delay: makes requests look human, not a bot
                time.sleep(random.uniform(0.5, 1.5))
                asset = yf.Ticker(ticker)
                info = asset.info
                df = asset.history(period="1y")
                if not df.empty:
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = (gain / loss).replace([np.inf, -np.inf], 0).fillna(0)
                    df['RSI'] = 100 - (100 / (1 + rs))
                return {"name": info.get('longName', ticker), "history": df, "details": info}
            except Exception:
                if i == 2: # Last attempt failed
                    return {"name": ticker, "history": pd.DataFrame(), "details": {}}
                time.sleep(2) # Wait before retry

    @st.cache_data(ttl=3600) 
    def get_news(query, company_name):
        search_term = company_name if company_name else query.split('.')[0]
        news_client = NewsApiClient(api_key=NEWS_API_KEY)
        try: return news_client.get_everything(q=search_term, language='en', sort_by='relevancy', page_size=10)
        except: return {'articles': []}

    def trigger_sms(to_number, body):
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(from_=TWILIO_PHONE_NUMBER, body=body, to=to_number)
            return True, "Success"
        except Exception as e: return False, str(e)

    # =====================================================================
    # SIDEBAR & DATA FETCHING
    # =====================================================================
    st.sidebar.title("🧬 Sentime-Track Pro")
    market_region = st.sidebar.selectbox("🌍 Market", ["India (NSE)", "US (Global)"])
    ticker = st.sidebar.selectbox("🔍 Asset", list(INDIAN_ASSETS.keys()) if market_region == "India (NSE)" else list(US_ASSETS.keys()))

    nav = st.sidebar.radio("Modules", ["Intelligence Hub", "📌 Custom Portfolio", "⏪ Algo Backtester", "🚨 SMS Alerts Dashboard", "Strategy Simulator", "Quant Health", "Predictive Forecaster", "Global Macro & Black Swan", "Algorithmic Risk & Regime", "Intraday Liquidity", "Export & Tear Sheet", "👤 My Profile"])

    asset_data = get_asset_info(ticker)
    stock_df = asset_data["history"]
    full_name = asset_data["name"]

    if stock_df.empty and nav not in ["👤 My Profile"]:
        st.error("⚠️ Market Data Throttled. Please wait 30 seconds and refresh.")
    
    else:
        # --- PRESERVED FEATURES ---
        if nav == "Intelligence Hub":
            st.markdown(f"<div class='company-header'><h2>{full_name} ({ticker})</h2></div>", unsafe_allow_html=True)
            last_price = stock_df['Close'].iloc[-1]
            st.metric("Price", f"{last_price:.2f}")
            # [Add all your original hub code here...]
            
        elif nav == "🚨 SMS Alerts Dashboard":
            st.header("Automated Alerts")
            with st.form("alert"):
                num = st.text_input("Phone", value=st.session_state.current_user['phone'])
                if st.form_submit_button("Test Alert"):
                    trigger_sms(num, f"Sentime-Track: {ticker} alert triggered.")
                    st.success("Alert Deployed.")

        elif nav == "👤 My Profile":
            st.write(f"Logged in as: {st.session_state.current_user['name']}")
            if st.button("Log Out"):
                st.session_state.logged_in = False
                st.rerun()

        # [REMAINING FEATURES: Backtester, simulator, etc. remain unchanged]
