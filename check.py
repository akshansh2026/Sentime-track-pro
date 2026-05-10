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
import random # INJECTED SOLUTION: Required for jitter logic

# --- SECURE API KEY LOADING ---
load_dotenv() 

# INJECTED SOLUTION: Secrets Bridge
# This ensures keys work locally (.env) AND in the Cloud (Secrets)
NEWS_API_KEY = st.secrets.get("NEWS_API_KEY", os.getenv("NEWS_API_KEY", "YOUR_NEWS_API_KEY_HERE"))
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE"))
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
    # INJECTED SOLUTION: Linked to your verified number for testing
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
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 35px;">
                <div style="margin-bottom: 20px;">
                    <svg width="65" height="65" viewBox="0 0 24 24" fill="none" stroke="#00d2ff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                    </svg>
                </div>
                <h1 style="color: {text_color}; letter-spacing: 3px; font-size: 32px; font-weight: 800; margin: 0;">SENTIME-TRACK <span style="color:#00d2ff;">PRO</span></h1>
                <p style="color: {sub_text}; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; margin-top: 5px;">Advanced Quantitative Terminal</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<div class='auth-box'>", unsafe_allow_html=True)
        auth_col1, auth_col2 = st.columns(2)
        with auth_col1:
            if st.button("LOGIN", use_container_width=True, type="secondary" if st.session_state.auth_mode == "Signup" else "primary"): 
                st.session_state.auth_mode = "Login"
                st.rerun()
        with auth_col2:
            if st.button("REGISTER", use_container_width=True, type="secondary" if st.session_state.auth_mode == "Login" else "primary"): 
                st.session_state.auth_mode = "Signup"
                st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state.auth_mode == "Login":
            log_email = st.text_input("Email Address", placeholder="name@organization.com")
            log_pass = st.text_input("Password", type="password", placeholder="••••••••")
            if st.button("AUTHENTICATE SESSION", use_container_width=True, type="primary"):
                if log_email in st.session_state.users_db and st.session_state.users_db[log_email]["password"] == log_pass:
                    st.session_state.logged_in = True
                    st.session_state.current_user = {"email": log_email, **st.session_state.users_db[log_email]}
                    st.rerun()
                else: st.error("Authentication failed.")
        else:
            reg_name = st.text_input("Full Name")
            reg_email = st.text_input("Email")
            reg_phone = st.text_input("Phone (+91...)")
            reg_pass = st.text_input("Password", type="password")
            if st.button("INITIALIZE PROFILE", use_container_width=True, type="primary"):
                st.session_state.users_db[reg_email] = {"password": reg_pass, "name": reg_name, "phone": reg_phone}
                st.success("Registered! Switch to Login.")
        st.markdown("</div>", unsafe_allow_html=True)
else:
    # --- ASSET DICTIONARY ---
    INDIAN_ASSETS = {"RELIANCE.NS": "Reliance Industries", "TCS.NS": "Tata Consultancy Services", "HDFCBANK.NS": "HDFC Bank", "INFY.NS": "Infosys"}
    US_ASSETS = {"AAPL": "Apple Inc.", "MSFT": "Microsoft", "GOOGL": "Alphabet", "NVDA": "NVIDIA"}
    ALL_ASSETS = {**INDIAN_ASSETS, **US_ASSETS}

    # --- SYSTEM CONFIG ---
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel('gemini-3-flash-preview')
    except: ai_model = None

    # --- INJECTED SOLUTION: STABLE DATA ENGINE ---
    @st.cache_data(ttl=3600) 
    def get_asset_info(ticker):
        for i in range(3): # SOLUTION: 3 Retries to bypass cloud blocks
            try:
                time.sleep(random.uniform(0.5, 1.5)) # SOLUTION: Jitter delay
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
            except:
                if i == 2: return {"name": ticker, "history": pd.DataFrame(), "details": {}}
                time.sleep(2)

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
            return True, "Sent"
        except Exception as e: return False, str(e)

    # --- SIDEBAR GENERATION ---
    st.sidebar.title("🧬 Sentime-Track Pro")
    market_region = st.sidebar.selectbox("🌍 Market", ["India (NSE)", "US (Global)"])
    ticker = st.sidebar.selectbox("🔍 Asset", list(INDIAN_ASSETS.keys()) if market_region == "India (NSE)" else list(US_ASSETS.keys()))

    nav = st.sidebar.radio("Modules", ["Intelligence Hub", "📌 Custom Portfolio", "⏪ Algo Backtester", "🚨 SMS Alerts Dashboard", "Strategy Simulator", "Quant Health", "Predictive Forecaster", "Global Macro & Black Swan", "Algorithmic Risk & Regime", "Intraday Liquidity", "Export & Tear Sheet", "👤 My Profile"], label_visibility="collapsed")

    # --- DATA PROCESSING ---
    asset_data = get_asset_info(ticker)
    stock_df = asset_data["history"]
    full_name, details = asset_data["name"], asset_data["details"]
    news_data = get_news(ticker, full_name)

    if stock_df.empty and nav not in ["👤 My Profile"]:
        st.warning("⚠️ Market Data Throttled. Please wait 30 seconds.")
    else:
        if nav not in ["📌 Custom Portfolio", "👤 My Profile"]:
            st.markdown(f"<div class='company-header'><h2>{full_name} ({ticker})</h2></div>", unsafe_allow_html=True)
            last_price = float(stock_df['Close'].iloc[-1])

        # --- MODULES (YOUR ORIGINAL FEATURES) ---
        if nav == "👤 My Profile":
            user_initial = st.session_state.current_user['name'][0].upper()
            st.markdown(f"<div style='background:{card_bg}; padding:40px; border-radius:12px; border:1px solid {border_col};'><h1>{st.session_state.current_user['name']}</h1><p style='color:#00CC96;'>🟢 PRO SUBSCRIPTION ACTIVE</p><hr><p>Email: {st.session_state.current_user['email']}</p><p>Phone: {st.session_state.current_user['phone']}</p></div>", unsafe_allow_html=True)
            if st.button("🛑 Secure Log Out", type="primary"):
                st.session_state.logged_in = False
                st.rerun()

        elif nav == "Intelligence Hub":
            col1, col2, col3 = st.columns(3)
            current_rsi = stock_df['RSI'].iloc[-1]
            rsi_color = "#FF4B4B" if current_rsi > 70 else "#00CC96" if current_rsi < 30 else "#FFD700"
            with col1: st.markdown(f"<div class='stat-card'><h5>Price</h5><h3>{last_price:.2f}</h3></div>", unsafe_allow_html=True)
            with col2: st.markdown(f"<div class='stat-card'><h5>RSI (14)</h5><h3 style='color:{rsi_color}'>{current_rsi:.1f}</h3></div>", unsafe_allow_html=True)
            with col3: st.markdown(f"<div class='stat-card'><h5>Mkt Cap</h5><h3>{details.get('marketCap', 0)/1e9:.1f}B</h3></div>", unsafe_allow_html=True)
            components.html(f"""<div style="height:500px;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"autosize":true,"symbol":"{ticker}","interval":"D","theme":"{tv_theme}","style":"1","container_id":"tv"}});</script><div id="tv" style="height:500px;"></div></div>""", height=500)

        elif nav == "🚨 SMS Alerts Dashboard":
            st.header("SMS Engine")
            with st.form("alert"):
                phone = st.text_input("Mobile Number", value=st.session_state.current_user['phone'])
                if st.form_submit_button("Deploy Alert"):
                    success, log = trigger_sms(phone, f"ALERT: {ticker} Price Target Reached.")
                    if success: st.success("SMS Deployed.")
                    else: st.error(f"Error: {log}")

        elif nav == "⏪ Algo Backtester":
            st.subheader("Golden Cross Analysis")
            stock_df['SMA50'] = stock_df['Close'].rolling(50).mean()
            stock_df['SMA200'] = stock_df['Close'].rolling(200).mean()
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=stock_df.index, y=stock_df['Close'], name="Price"))
            fig.add_trace(go.Scatter(x=stock_df.index, y=stock_df['SMA50'], name="SMA 50"))
            fig.add_trace(go.Scatter(x=stock_df.index, y=stock_df['SMA200'], name="SMA 200"))
            fig.update_layout(template="plotly_dark" if st.session_state.theme == "Dark" else "plotly_white")
            st.plotly_chart(fig, use_container_width=True)

        # [All other original features go here following this pattern]
