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

# --- SECURE API KEY LOADING (INJECTED SOLUTION: SECRETS BRIDGE) ---
load_dotenv() 

# This allows the app to work on your laptop (.env) AND the Cloud (Secrets)
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
    # INJECTED SOLUTION: Linked to your verified number for cloud testing
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
    st.markdown("""
        <style>
            [data-testid="stSidebar"] { display: none; }
            [data-testid="collapsedControl"] { display: none; }
        </style>
    """, unsafe_allow_html=True)

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
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("AUTHENTICATE SESSION", use_container_width=True, type="primary"):
                if log_email in st.session_state.users_db and st.session_state.users_db[log_email]["password"] == log_pass:
                    st.session_state.logged_in = True
                    st.session_state.current_user = {"email": log_email, **st.session_state.users_db[log_email]}
                    st.rerun()
                else:
                    st.error("Authentication failed. Invalid credentials.")

        else:
            reg_name = st.text_input("Full Name / Organization")
            reg_email = st.text_input("Email Address")
            reg_phone = st.text_input("Phone Number (with +CountryCode)")
            reg_pass = st.text_input("Create Password", type="password")
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("INITIALIZE PROFILE", use_container_width=True, type="primary"):
                if reg_email in st.session_state.users_db:
                    st.error("Email already registered. Please login.")
                elif not reg_email or not reg_pass or not reg_name:
                    st.error("Please complete all fields.")
                else:
                    st.session_state.users_db[reg_email] = {"password": reg_pass, "name": reg_name, "phone": reg_phone}
                    st.success("Registration complete. Switching to login...")
                    time.sleep(1)
                    st.session_state.auth_mode = "Login"
                    st.rerun()
                    
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align:center; margin-top:20px;'><p style='color:{sub_text}; font-size:12px;'>© 2026 Sentime-Track OS • Secure Access Gateway</p></div>", unsafe_allow_html=True)

# =====================================================================
# MAIN APP
# =====================================================================
else:
    # --- SMART TICKER DICTIONARY ---
    INDIAN_ASSETS = {
        "RELIANCE.NS": "Reliance Industries", "TCS.NS": "Tata Consultancy Services", "HDFCBANK.NS": "HDFC Bank", 
        "INFY.NS": "Infosys", "ICICIBANK.NS": "ICICI Bank", "HINDUNILVR.NS": "Hindustan Unilever", 
        "ITC.NS": "ITC Limited", "SBI.NS": "State Bank of India", "BHARTIARTL.NS": "Bharti Airtel", 
        "KOTAKBANK.NS": "Kotak Mahindra Bank", "LT.NS": "Larsen & Toubro", "AXISBANK.NS": "Axis Bank", 
        "ASIANPAINT.NS": "Asian Paints", "MARUTI.NS": "Maruti Suzuki", "TITAN.NS": "Titan Company", 
        "BAJFINANCE.NS": "Bajaj Finance", "WIPRO.NS": "Wipro", "HCLTECH.NS": "HCL Technologies"
    }

    US_ASSETS = {
        "AAPL": "Apple Inc.", "MSFT": "Microsoft", "GOOGL": "Alphabet (Google)", "AMZN": "Amazon",
        "META": "Meta Platforms (Facebook)", "TSLA": "Tesla", "NVDA": "NVIDIA", "BRK-B": "Berkshire Hathaway",
        "JPM": "JPMorgan Chase", "V": "Visa", "UNH": "UnitedHealth", "MA": "Mastercard",
        "PG": "Procter & Gamble", "HD": "Home Depot", "DIS": "Walt Disney", "PYPL": "PayPal"
    }

    ALL_ASSETS = {**INDIAN_ASSETS, **US_ASSETS}

    # --- SYSTEM CONFIG ---
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel('gemini-3-flash-preview')
    except Exception as e:
        ai_model = None
        st.sidebar.warning("AI Configuration Error: Check API key in .env file.")

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
            except Exception:
                if i == 2: return {"name": ticker, "history": pd.DataFrame(), "details": {}}
                time.sleep(2)

    @st.cache_data(ttl=3600) 
    def get_news(query, company_name):
        search_term = company_name if company_name else query.split('.')[0]
        news_client = NewsApiClient(api_key=NEWS_API_KEY)
        try:
            return news_client.get_everything(q=search_term, language='en', sort_by='relevancy', page_size=10)
        except Exception as e:
            return {'articles': [], 'error': str(e)}

    # --- SMS NOTIFICATION ENGINE ---
    def trigger_sms(to_number, body):
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
            return False, "Twilio credentials missing in .env"
        
        to_number = str(to_number).strip()
        if to_number.startswith('0') and len(to_number) == 11:
            to_number = '+91' + to_number[1:]
        elif not to_number.startswith('+'):
            to_number = '+' + to_number

        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                from_=TWILIO_PHONE_NUMBER,
                body=body,
                to=to_number
            )
            return True, "SMS sent successfully"
        except Exception as e:
            return False, str(e)

    # =====================================================================
    # SIDEBAR GENERATION
    # =====================================================================
    st.sidebar.title("🧬 Sentime-Track Pro")

    with st.sidebar.expander("📌 My Portfolio Watchlist", expanded=False):
        st.session_state.watchlist = st.multiselect(
            "Manage Assets", 
            options=list(ALL_ASSETS.keys()), 
            default=st.session_state.watchlist,
            format_func=lambda x: ALL_ASSETS[x]
        )

    market_region = st.sidebar.selectbox("🌍 Market Region", ["India (NSE)", "US (Global)"])
    options = list(INDIAN_ASSETS.keys()) if market_region == "India (NSE)" else list(US_ASSETS.keys())
    ticker = st.sidebar.selectbox("🔍 Target Asset", options=options, format_func=lambda x: f"{ALL_ASSETS[x]} ({x})", index=1 if market_region == "India (NSE)" else 0)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧭 Modules")

    nav = st.sidebar.radio(
        "Select Module", 
        [
            "Intelligence Hub", 
            "📌 Custom Portfolio", 
            "⏪ Algo Backtester", 
            "🚨 SMS Alerts Dashboard",
            "Strategy Simulator", 
            "Quant Health", 
            "Predictive Forecaster", 
            "Global Macro & Black Swan", 
            "Algorithmic Risk & Regime", 
            "Intraday Liquidity", 
            "Export & Tear Sheet",
            "👤 My Profile" 
        ],
        label_visibility="collapsed"
    )

    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    
    with st.sidebar.expander("⚙️ Settings", expanded=False):
        st.markdown("#### 🎛️ App Preferences")
        theme_choice = st.radio("Theme Mode", ["Dark", "Light"], index=0 if st.session_state.theme == "Dark" else 1)
        if theme_choice != st.session_state.theme:
            st.session_state.theme = theme_choice
            st.rerun()
        accent_choice = st.selectbox("🎙️ Voice Accent", ["British (UK)", "American (US)", "Australian (AU)", "Indian (IN)"])
        tld_map = {"British (UK)": "co.uk", "American (US)": "com", "Australian (AU)": "com.au", "Indian (IN)": "co.in"}

    st.sidebar.caption("© 2026 Sentime-Track OS")

    # 3. DATA PROCESSING
    asset_data = get_asset_info(ticker)
    stock_df = asset_data["history"]
    full_name = asset_data["name"]
    details = asset_data["details"]
    raw_symbol = ticker.split('.')[0]
    news_data = get_news(raw_symbol, full_name)

    tv_symbol = f"BSE:{raw_symbol}" if market_region == "India (NSE)" else raw_symbol
    tv_timezone = "Asia/Kolkata" if market_region == "India (NSE)" else "America/New_York"

    # 4. MAIN INTERFACE
    if stock_df.empty and nav not in ["📌 Custom Portfolio", "👤 My Profile"]:
        st.warning(f"⚠️ Market Data Throttled. Please wait 30 seconds.")
    else:
        if nav not in ["📌 Custom Portfolio", "👤 My Profile"]:
            st.markdown(f"""
                <div class="company-header">
                    <p style="color:#3a7bd5; margin:0; font-weight:bold; text-transform:uppercase; letter-spacing:1.5px; font-size: 13px;">Quant Terminal | {datetime.now().strftime('%H:%M:%S')}</p>
                    <h2 style="margin:0;">{full_name} <span style="color:{sub_text}; font-size:18px;">({ticker})</span></h2>
                </div>
            """, unsafe_allow_html=True)
            last_price = float(stock_df['Close'].iloc[-1])

        # -------------------------------------------------------------
        # MODULE: MY PROFILE (FIXED HTML FORMATTING)
        # -------------------------------------------------------------
        if nav == "👤 My Profile":
            user_initial = st.session_state.current_user['name'][0].upper()
            
            st.markdown(f"""
<div style="background: linear-gradient(135deg, {grad_1} 0%, {card_bg} 100%); padding: 40px; border-radius: 12px; border: 1px solid {border_col}; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
    <div style="display: flex; align-items: center; gap: 20px;">
        <div style="width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%); display: flex; justify-content: center; align-items: center; color: white; font-size: 36px; font-weight: bold; box-shadow: 0 4px 10px rgba(58, 123, 213, 0.4);">
            {user_initial}
        </div>
        <div>
            <h1 style="color:{text_color}; margin:0; letter-spacing: 1px;">{st.session_state.current_user['name']}</h1>
            <p style="color:#00CC96; font-size: 14px; margin-top:5px; font-weight: 600;">🟢 PRO SUBSCRIPTION ACTIVE</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
            
            st.markdown(f"""
<div style="background:{card_bg}; padding: 25px; border-radius: 10px; border: 1px solid {border_col}; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px;">
    <h5 style="color:{sub_text}; margin-bottom: 20px; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">Registered Credentials</h5>
    <strong style="font-size: 12px; color:{sub_text};">Email Address</strong><br>
    <span style="font-size: 16px; color:{text_color}; font-weight: 500;">{st.session_state.current_user['email']}</span><br><br>
    <strong style="font-size: 12px; color:{sub_text};">Phone / SMS Destination</strong><br>
    <span style="font-size: 16px; color:{text_color}; font-weight: 500;">{st.session_state.current_user['phone']}</span>
</div>
""", unsafe_allow_html=True)
            
            if st.button("🛑 Secure Log Out & Terminate Session", type="primary"):
                st.session_state.logged_in = False
                st.session_state.current_user = None
                st.rerun()

        # -------------------------------------------------------------
        # MODULE: INTELLIGENCE HUB
        # -------------------------------------------------------------
        elif nav == "Intelligence Hub":
            col1, col2, col3, col4 = st.columns([1, 1, 1, 1.5])
            current_rsi = stock_df['RSI'].iloc[-1]
            
            analyzer = SentimentIntensityAnalyzer()
            articles = news_data.get('articles', [])
            titles = [a['title'] for a in articles if a['title']]
            avg_sentiment = sum([analyzer.polarity_scores(t)['compound'] for t in titles])/len(titles) if titles else 0

            rsi_color = "#FF4B4B" if current_rsi > 70 else "#00CC96" if current_rsi < 30 else "#FFD700"
            quant_score = (100 - current_rsi) * 0.4 + (avg_sentiment * 30) + 20

            with col1: st.markdown(f"<div class='stat-card'><h5 style='margin:0; color:{sub_text}; font-size:13px;'>Sentiment Score</h5><h3 style='color:#00d2ff; margin:5px 0;'>{avg_sentiment:.2f}</h3></div>", unsafe_allow_html=True)
            with col2: st.markdown(f"<div class='stat-card'><h5 style='margin:0; color:{sub_text}; font-size:13px;'>RSI (14)</h5><h3 style='color:{rsi_color}; margin:5px 0;'>{current_rsi:.1f}</h3></div>", unsafe_allow_html=True)
            with col3: st.markdown(f"<div class='stat-card'><h5 style='margin:0; color:{sub_text}; font-size:13px;'>Quant Score</h5><h3 style='color:#3a7bd5; margin:5px 0;'>{quant_score:.0f}/100</h3></div>", unsafe_allow_html=True)
            with col4:
                st.markdown(f"<h5 style='margin:0 0 5px 0; font-size:14px; color:{text_color};'>Fundamental Check</h5>", unsafe_allow_html=True)
                st.caption(f"Market Cap: **{details.get('marketCap', 0)/1e9:.2f}B**")
                try:
                    vol_ratio = stock_df['Volume'].iloc[-1] / stock_df['Volume'].rolling(20).mean().iloc[-1] if stock_df['Volume'].rolling(20).mean().iloc[-1] > 0 else 1
                    if vol_ratio > 1.5: st.markdown(f"<span style='color:#FFD700; font-weight:bold; font-size:13px;'>⚠️ Whale Alert: Vol {vol_ratio:.1f}x Avg</span>", unsafe_allow_html=True)
                except: pass

            if articles and ai_model:
                st.markdown(f"<div class='ai-insight'><strong style='font-size:14px; color:{text_color};'>🔮 AI Narrative Synthesis</strong><br>", unsafe_allow_html=True)
                try:
                    syn = ai_model.generate_content(f"In 2 brief sentences, what is the dominant market sentiment for {full_name} based on these headlines: {' '.join(titles[:5])}").text
                    st.markdown(f"<span style='font-size:13px; color:{text_color};'>{syn}</span>", unsafe_allow_html=True)
                except Exception: st.warning("⚠️ AI API Rate Limit Reached.")
                st.markdown("</div>", unsafe_allow_html=True)

            components.html(f"""<div style="height:500px;width:100%; border: 1px solid {border_col}; border-radius: 8px; overflow:hidden;"><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"autosize":true,"symbol":"{tv_symbol}","interval":"D","timezone":"{tv_timezone}","theme":"{tv_theme}","style":"1","locale":"en","container_id":"tv"}});</script><div id="tv" style="height:500px;"></div></div>""", height=500)
            
            st.markdown(f"<h4 style='margin-top:20px; color:{text_color};'>📰 Advanced News Terminal</h4>", unsafe_allow_html=True)
            if articles:
                for art in articles[:10]:
                    art_score = analyzer.polarity_scores(art['title'])['compound']
                    s_color, s_text = ("#00CC96", "POS") if art_score > 0.15 else ("#FF4B4B", "NEG") if art_score < -0.15 else ("gray", "NEU")
                    st.markdown(f"""
                        <div class="terminal-news-row" style="background:{card_bg}; border: 1px solid {border_col}; border-radius: 4px; margin-bottom: 8px; display: flex; align-items: center; padding: 10px 12px; border-left: 3px solid {s_color};">
                            <div style="width: 130px; font-family: monospace; font-size: 11px; color: {sub_text};">{art['publishedAt'][:16].replace('T', ' ')}</div>
                            <div style="width: 140px; font-family: monospace; font-size: 11px; color: #3a7bd5; font-weight: 600;">{art['source']['name'][:15].upper()}</div>
                            <div style="flex-grow: 1; padding-left: 15px; border-left: 1px solid {border_col};"><a href="{art['url']}" target="_blank" style="text-decoration:none; color:{text_color}; font-size: 13px;">{art['title']}</a></div>
                            <div style="width: 50px; text-align: right;"><span style="color: {s_color}; font-family: monospace; font-size: 12px; font-weight: 600;">{s_text}</span></div>
                        </div>
                    """, unsafe_allow_html=True)

        # -------------------------------------------------------------
        # MODULE: CUSTOM PORTFOLIO
        # -------------------------------------------------------------
        elif nav == "📌 Custom Portfolio":
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, {grad_1} 0%, {grad_2} 100%); padding: 15px; border-radius: 10px; border: 1px solid #3a7bd5; margin-bottom: 20px; text-align: center;">
                <h3 style="color:#00d2ff; margin:0; letter-spacing: 1px;">📌 MY CUSTOM WATCHLIST</h3>
            </div>
            """, unsafe_allow_html=True)
            
            if not st.session_state.watchlist:
                st.info("Your watchlist is empty. Add assets from the sidebar menu to track them here.")
            else:
                cols = st.columns(4) 
                for idx, sym in enumerate(st.session_state.watchlist):
                    try:
                        w_df = yf.Ticker(sym).history(period="5d")
                        if not w_df.empty and len(w_df) >= 2:
                            w_price = w_df['Close'].iloc[-1]
                            w_prev = w_df['Close'].iloc[-2]
                            w_pct = ((w_price - w_prev) / w_prev) * 100
                            p_color = "#00CC96" if w_pct >= 0 else "#FF4B4B"
                            p_sign = "+" if w_pct >= 0 else ""
                            
                            with cols[idx % 4]:
                                st.markdown(f"""
                                <div style="background:{card_bg}; padding:15px; border-radius:8px; border-top:3px solid {p_color}; border-left: 1px solid {border_col}; border-right: 1px solid {border_col}; border-bottom: 1px solid {border_col}; margin-bottom:15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                                    <h5 style="margin:0; color:{sub_text}; font-size:11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{ALL_ASSETS.get(sym, sym)}</h5>
                                    <h4 style="margin:4px 0; font-size:15px; color:{text_color};">{sym}</h4>
                                    <h2 style="color:{text_color}; margin:0; font-size:22px;">{w_price:.2f}</h2>
                                    <p style="color:{p_color}; font-weight:bold; margin:0; font-size:13px;">{p_sign}{w_pct:.2f}%</p>
                                </div>
                                """, unsafe_allow_html=True)
                    except: pass

        elif nav == "⏪ Algo Backtester":
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, {grad_1} 0%, {grad_2} 100%); padding: 20px; border-radius: 12px; border: 1px solid #FFD700; margin-bottom: 25px; text-align: center;">
                <h2 style="color:#FFD700; margin:0; letter-spacing: 2px;">⏪ HISTORICAL BACKTESTING ENGINE</h2>
                <p style="color:{sub_text}; font-size: 14px; margin-top:5px;">Prove algorithmic profitability vs. Buy & Hold over the last year.</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.write(f"**Strategy Selected:** Golden Cross (SMA 50 > SMA 200) for **{full_name}**")
            
            try:
                with st.spinner("Running historical simulations..."):
                    hist_df = yf.Ticker(ticker).history(period="2y") 
                    if not hist_df.empty and len(hist_df) > 200:
                        hist_df['SMA_50'] = hist_df['Close'].rolling(window=50).mean()
                        hist_df['SMA_200'] = hist_df['Close'].rolling(window=200).mean()
                        
                        hist_df['Signal'] = np.where(hist_df['SMA_50'] > hist_df['SMA_200'], 1, 0)
                        hist_df['Daily_Return'] = hist_df['Close'].pct_change()
                        hist_df['Strategy_Return'] = hist_df['Daily_Return'] * hist_df['Signal'].shift(1)
                        
                        plot_df = hist_df.tail(252).copy()
                        plot_df['Cumulative_Market'] = (1 + plot_df['Daily_Return']).cumprod() * 100
                        plot_df['Cumulative_Strategy'] = (1 + plot_df['Strategy_Return']).cumprod() * 100
                        
                        market_return = plot_df['Cumulative_Market'].iloc[-1] - 100
                        strat_return = plot_df['Cumulative_Strategy'].iloc[-1] - 100
                        
                        c1, c2 = st.columns(2)
                        with c1: st.markdown(f"<div class='stat-card'><p style='margin:0; font-size:13px; color:{sub_text};'>Buy & Hold Return (1Y)</p><h2 style='color:{'#00CC96' if market_return > 0 else '#FF4B4B'}; margin:5px 0;'>{market_return:.2f}%</h2></div>", unsafe_allow_html=True)
                        with c2: st.markdown(f"<div class='stat-card'><p style='margin:0; font-size:13px; color:{sub_text};'>Strategy Return (1Y)</p><h2 style='color:{'#00CC96' if strat_return > 0 else '#FF4B4B'}; margin:5px 0;'>{strat_return:.2f}%</h2></div>", unsafe_allow_html=True)
                        
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Cumulative_Market'], name="Buy & Hold", line=dict(color="gray", width=2)))
                        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['Cumulative_Strategy'], name="Golden Cross Algo", line=dict(color="#FFD700", width=3)))
                        fig.update_layout(template="plotly_dark" if st.session_state.theme == "Dark" else "plotly_white", title="Algorithmic Performance vs Market", paper_bgcolor=bg_color, plot_bgcolor=card_bg, font=dict(color=text_color))
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Not enough historical data to compute a 200-day moving average.")
            except Exception as e: st.error(f"Algorithmic Backtester Error: {e}")

        elif nav == "🚨 SMS Alerts Dashboard":
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, {grad_1} 0%, {grad_2} 100%); padding: 20px; border-radius: 12px; border: 1px solid #FF4B4B; margin-bottom: 25px; text-align: center;">
                <h2 style="color:#FF4B4B; margin:0; letter-spacing: 2px;">🚨 AUTOMATED SMS ALERTS</h2>
                <p style="color:{sub_text}; font-size: 14px; margin-top:5px;">Set and monitor automated text message triggers.</p>
            </div>
            """, unsafe_allow_html=True)

            with st.form("alert_form", clear_on_submit=False):
                st.markdown(f"<h4 style='color:{text_color};'>➕ Create New SMS Alert</h4>", unsafe_allow_html=True)
                a_col1, a_col2, a_col3 = st.columns(3)
                with a_col1: a_metric = st.selectbox("Trigger Metric", ["Price", "RSI"])
                with a_col2: a_cond = st.selectbox("Condition", ["Goes Above", "Drops Below"])
                with a_col3: a_val = st.number_input("Target Value", min_value=0.0, value=last_price if a_metric == "Price" else 50.0)
                
                a_contact = st.text_input("Delivery Destination (Phone Number)", value=st.session_state.current_user.get('phone', ''))
                
                if st.form_submit_button("Deploy Alert Engine", type="primary"):
                    if not a_contact: st.error("Please provide a Phone Number.")
                    else:
                        st.session_state.alerts.append({
                            "asset": ticker, "name": full_name, "metric": a_metric, "condition": a_cond, 
                            "value": a_val, "contact": a_contact, "status": "Active 🟢", "id": len(st.session_state.alerts)+1
                        })
                        st.success(f"Alert deployed! Monitoring {a_metric} for {ticker}.")
            
            st.markdown("---")
            c1, c2 = st.columns([3, 1])
            with c1: st.markdown(f"<h4 style='color:{text_color};'>📡 Active Alert Triggers</h4>", unsafe_allow_html=True)
            with c2: 
                if st.button("🔔 Run & Test Alerts Now", use_container_width=True):
                    with st.spinner("Checking market conditions & sending SMS..."):
                        for alert in st.session_state.alerts:
                            if alert["status"] != "Active 🟢": continue
                            msg_body = f"🚨 Sentime-Track Pro: {alert['asset']} {alert['metric']} triggered your target: {alert['condition']} {alert['value']}!"
                            success, log = trigger_sms(alert["contact"], msg_body)
                            if success: st.success(f"SMS sent to {alert['contact']}")
                            else: st.error(f"SMS Failed to {alert['contact']}: {log}")

            if not st.session_state.alerts: st.info("No active alerts. Create one above.")
            else:
                for alert in reversed(st.session_state.alerts):
                    st.markdown(f"""
                    <div style="background:{card_bg}; padding: 15px; border-radius: 8px; border-left: 4px solid #00d2ff; border-top: 1px solid {border_col}; border-bottom: 1px solid {border_col}; border-right: 1px solid {border_col}; margin-bottom: 10px; display:flex; justify-content:space-between; align-items:center;">
                        <div><span style="color:{sub_text}; font-size:12px;">Alert ID: #{alert['id']} • Mobile: {alert['contact']}</span><br>
                        <strong style="color:{text_color};">{alert['asset']}</strong> - If {alert['metric']} {alert['condition']} <strong style="color:{text_color};">{alert['value']}</strong></div>
                        <div style="font-family:monospace; background:rgba(0, 204, 150, 0.1); padding: 5px 10px; border-radius:4px; color:#00CC96; font-size:13px; border: 1px solid #00CC96;">{alert['status']}</div>
                    </div>
                    """, unsafe_allow_html=True)

        elif nav == "Export & Tear Sheet":
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, {grad_1} 0%, {grad_2} 100%); padding: 35px; border-radius: 12px; border: 1px dashed #3a7bd5; text-align: center; margin-bottom: 20px;">
                <h2 style="color:{text_color}; margin-bottom: 5px;">📄 EXECUTIVE TEAR SHEET & EXPORT HUB</h2>
                <p style="color:{sub_text}; margin-bottom: 20px;">Download complete datasets or generate automated research tear sheets for sharing.</p>
            </div>
            """, unsafe_allow_html=True)
            
            c1, col_ex = st.columns(2)
            
            with c1:
                st.markdown(f"<h4 style='color:{text_color};'>1. Download Historical Data (CSV)</h4>", unsafe_allow_html=True)
                st.caption("Complete OHLCV dataset for offline algorithmic backtesting.")
                csv = stock_df.to_csv().encode('utf-8')
                st.download_button(label="⬇️ DOWNLOAD PROPRIETARY CSV", data=csv, file_name=f"{raw_symbol}_data.csv", mime='text/csv', use_container_width=True)
                
            with col_ex:
                st.markdown(f"<h4 style='color:{text_color};'>2. Generate Quant Tear Sheet (TXT)</h4>", unsafe_allow_html=True)
                st.caption("A readable summary of current pricing, RSI, and Risk Metrics for easy sharing.")
                tear_sheet = f"""
                ===========================================
                SENTIME-TRACK PRO: EXECUTIVE TEAR SHEET
                ===========================================
                PREPARED FOR: {st.session_state.current_user['name']}
                ASSET: {full_name} ({ticker})
                DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                -------------------------------------------
                Current Price: {last_price:.2f}
                RSI (14-Day):  {stock_df['RSI'].iloc[-1]:.1f}
                30D Volatility:{stock_df['Close'].pct_change().dropna().tail(30).std() * np.sqrt(252) * 100:.2f}%
                Market Cap:    {details.get('marketCap', 0)/1e9:.2f} Billion
                
                ALGORITHMIC ASSESSMENT:
                Assuming a $100k portfolio, 95% Confidence 
                Daily VaR is approx ${(100000 * abs(stock_df['Close'].pct_change().dropna().quantile(0.05))):,.2f}.
                
                GENERATED VIA SENTIME-TRACK OS
                ===========================================
                """
                st.download_button(label="📄 DOWNLOAD TEAR SHEET", data=tear_sheet.encode('utf-8'), file_name=f"{raw_symbol}_TearSheet.txt", mime='text/plain', use_container_width=True)

        elif nav == "Strategy Simulator":
            s1, s2 = st.columns([1.5, 1])
            with s1:
                st.markdown(f"<h4 style='color:{text_color};'>🎛️ Adjust Market Variables</h4>", unsafe_allow_html=True)
                move = st.slider("Simulated Move (%)", -20, 20, 0)
                shift = st.select_slider("News Shift", options=["Negative", "Neutral", "Positive"], value="Neutral")
                
            target_price = last_price * (1 + move/100)
            if move < -4 and shift == "Positive": rec, color = "BUY (Value Dip)", "#00CC96"
            elif move > 0 and shift == "Positive": rec, color = "BUY (Momentum)", "#00CC96"
            elif move > 5 and shift == "Negative": rec, color = "SELL (Exit)", "#FF4B4B"
            else: rec, color = "HOLD", "#FFD700"
            
            with s2:
                st.markdown(f"""
                <div style="background: {card_bg}; border: 1px solid {color}; padding: 20px; border-radius: 10px; text-align: center;">
                    <p style="color:{sub_text}; margin:0; font-size:12px;">EXECUTION TARGET</p>
                    <h2 style="color:{text_color}; margin: 10px 0;">{target_price:.2f}</h2>
                    <hr style="border-color:{border_col};">
                    <p style="color:{sub_text}; margin:0; font-size:12px;">ALGORITHMIC ACTION</p>
                    <h2 style="color:{color}; margin: 10px 0;">{rec}</h2>
                </div>
                """, unsafe_allow_html=True)

        elif nav == "Quant Health":
            st.subheader(f"📊 {full_name} Beta & Volatility")
            st.latex(r"\beta = \frac{\text{Cov}(r_a, r_m)}{\text{Var}(r_m)}")
            benchmark = "^NSEI" if market_region == "India (NSE)" else "^GSPC"
            bench_df = yf.download(benchmark, period="1y")
            if not bench_df.empty:
                if isinstance(bench_df.columns, pd.MultiIndex): bench_df.columns = bench_df.columns.get_level_values(0)
                stock_ret, bench_ret = stock_df['Close'].pct_change().dropna(), bench_df['Close'].pct_change().dropna()
                stock_ret.index, bench_ret.index = stock_ret.index.tz_localize(None), bench_ret.index.tz_localize(None)
                aligned = pd.concat([stock_ret, bench_ret], axis=1).dropna()
                aligned.columns = ['Stock', 'Bench']
                beta = aligned['Stock'].cov(aligned['Bench']) / aligned['Bench'].var()
                st.metric("Asset Beta", f"{beta:.2f}")
                
                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(x=stock_df.index, y=(stock_df['Close']/stock_df['Close'].iloc[0])*100, name=full_name))
                fig_p.add_trace(go.Scatter(x=bench_df.index, y=(bench_df['Close']/bench_df['Close'].iloc[0])*100, name="Market Index"))
                fig_p.update_layout(template="plotly_dark" if st.session_state.theme == "Dark" else "plotly_white", paper_bgcolor=bg_color, plot_bgcolor=card_bg, font=dict(color=text_color))
                st.plotly_chart(fig_p, use_container_width=True)

        elif nav == "Predictive Forecaster":
            st.subheader(f"🔮 AI Monte Carlo Forecaster")
            try:
                returns = stock_df['Close'].pct_change().dropna()
                mu, sigma = returns.mean(), returns.std()
                sims = np.exp((mu - 0.5 * sigma**2) + sigma * np.random.normal(size=(30, 50))).cumprod(axis=0) * last_price
                fig_mc = go.Figure()
                for i in range(10): fig_mc.add_trace(go.Scatter(y=sims[:,i], mode='lines', line=dict(width=1, color="gray"), opacity=0.3, showlegend=False))
                fig_mc.add_trace(go.Scatter(y=sims.mean(axis=1), mode='lines', line=dict(width=3, color='#00d2ff'), name='AI Median'))
                fig_mc.update_layout(template="plotly_dark" if st.session_state.theme == "Dark" else "plotly_white", title="50 Path Future Cloud")
                st.plotly_chart(fig_mc, use_container_width=True)
            except Exception as e: st.error(f"Predictive Forecaster Error: {e}")

        elif nav == "Global Macro & Black Swan":
            try:
                with st.spinner("Aligning global macroeconomic matrices..."):
                    spy_df = yf.Ticker("^GSPC").history(period="3mo")
                    gold_df = yf.Ticker("GC=F").history(period="3mo")
                    
                    spy_close = spy_df['Close'].copy()
                    spy_close.index = spy_close.index.tz_localize(None).normalize()
                    
                    gold_close = gold_df['Close'].copy()
                    gold_close.index = gold_close.index.tz_localize(None).normalize()
                    
                    stock_close = stock_df['Close'].tail(90).copy()
                    stock_close.index = stock_close.index.tz_localize(None).normalize()
                    
                    aligned_data = pd.concat([stock_close, gold_close, spy_close], axis=1, keys=['Stock', 'Gold', 'S&P500']).dropna()
                    
                    corr_spy = aligned_data['Stock'].corr(aligned_data['S&P500'])
                    corr_gold = aligned_data['Stock'].corr(aligned_data['Gold'])
                    
                    c1, c2, c3 = st.columns(3)
                    with c1: st.markdown(f"<div style='background:{card_bg}; padding: 20px; border-radius:10px; border-top: 3px solid {'#00CC96' if corr_spy > 0 else '#FF4B4B'}; border-left:1px solid {border_col}; border-right:1px solid {border_col}; border-bottom:1px solid {border_col}; text-align:center;'><p style='color:{sub_text}; font-size:12px; margin:0;'>CORRELATION VS S&P 500</p><h2 style='color:{'#00CC96' if corr_spy > 0 else '#FF4B4B'}; margin:10px 0;'>{corr_spy:.2f}</h2></div>", unsafe_allow_html=True)
                    with c2: st.markdown(f"<div style='background:{card_bg}; padding: 20px; border-radius:10px; border-top: 3px solid {'#00CC96' if corr_gold > 0 else '#FF4B4B'}; border-left:1px solid {border_col}; border-right:1px solid {border_col}; border-bottom:1px solid {border_col}; text-align:center;'><p style='color:{sub_text}; font-size:12px; margin:0;'>CORRELATION VS GOLD</p><h2 style='color:{'#00CC96' if corr_gold > 0 else '#FF4B4B'}; margin:10px 0;'>{corr_gold:.2f}</h2></div>", unsafe_allow_html=True)
                    with c3:
                        entropy = max(min(((aligned_data['Stock'].pct_change().std() * 100) * 5) + (corr_spy * 20) - (corr_gold * 20), 100), 0)
                        st.markdown(f"<div style='background:{card_bg}; padding: 20px; border-radius:10px; border-top: 3px solid #FFD700; border-left:1px solid {border_col}; border-right:1px solid {border_col}; border-bottom:1px solid {border_col}; text-align:center;'><p style='color:{sub_text}; font-size:12px; margin:0;'>BLACK SWAN ENTROPY</p><h2 style='color:#FFD700; margin:10px 0;'>{entropy:.1f}/100</h2></div>", unsafe_allow_html=True)
            except Exception as e: st.error(f"Global Macro Error: {e}")

        elif nav == "Algorithmic Risk & Regime":
            try:
                returns = stock_df['Close'].pct_change().dropna()
                var_95 = returns.quantile(0.05)
                st.markdown(f"<div style='background: {card_bg}; border-left: 5px solid #FF4B4B; border-top: 1px solid {border_col}; border-right: 1px solid {border_col}; border-bottom: 1px solid {border_col}; padding: 20px; border-radius: 10px;'><h4 style='color: {sub_text}; margin: 0; font-size: 12px;'>MAX DAILY DRAWDOWN (95% CONFIDENCE)</h4><h1 style='color: #FF4B4B; margin: 0;'>${(100000 * abs(var_95)):,.2f}</h1><p style='color: {sub_text}; margin: 0; font-size: 12px;'>Assuming $100k Portfolio</p></div>", unsafe_allow_html=True)
                
                sma_10 = stock_df['Close'].rolling(window=10).mean().iloc[-1]
                sma_30 = stock_df['Close'].rolling(window=30).mean().iloc[-1]
                if sma_10 > sma_30 and last_price > sma_10: regime, color = "BULLISH TREND 🐂", "#00CC96"
                elif sma_10 < sma_30 and last_price < sma_10: regime, color = "BEARISH TREND 🐻", "#FF4B4B"
                else: regime, color = "RANGE BOUND / CHOPPY ⚖️", "#FFD700"
                st.markdown(f"<div style='background: {card_bg}; border: 1px solid {color}; padding: 35px; border-radius: 12px; text-align: center; margin-top:20px;'><p style='color: {color}; margin: 0; font-weight:bold;'>MARKET REGIME</p><h1 style='color: {text_color};'>{regime}</h1></div>", unsafe_allow_html=True)
            except Exception as e: st.error(f"Algorithmic Risk Error: {e}")

        elif nav == "Intraday Liquidity":
            try:
                avg_vol = stock_df['Volume'].tail(30).mean()
                cur_vol = stock_df['Volume'].iloc[-1]
                liquidity_score = (cur_vol / avg_vol) * 100 if avg_vol > 0 else 0
                slippage = "LOW RISK" if liquidity_score > 100 else "HIGH RISK"
                slip_color = "#00CC96" if slippage == "LOW RISK" else "#FF4B4B"
                st.markdown(f"<div style='background:{card_bg}; padding: 30px; border-radius:10px; border: 1px solid {slip_color}; text-align:center;'><p style='color:{sub_text}; margin:0;'>EXECUTION SLIPPAGE RISK</p><h1 style='color:{slip_color}; font-size: 50px; margin: 10px 0;'>{slippage}</h1><p style='color:{sub_text}; font-size:12px; margin:0;'>Ability to absorb large block orders</p></div>", unsafe_allow_html=True)
            except Exception as e: st.error(f"Intraday Liquidity Error: {e}")

        # --- VOICE TERMINAL ---
        if nav not in ["👤 My Profile"]:
            st.markdown("---")
            st.markdown(f"<h3 style='color:{text_color};'>🎙️ AI Voice Terminal</h3>", unsafe_allow_html=True)
            voice_in = speech_to_text(language='en', start_prompt="🟢 START SESSION", stop_prompt="🛑 END SESSION", key='VOICE_INPUT')
            if voice_in and voice_in != st.session_state.last_voice_query:
                st.session_state.last_voice_query = voice_in
                if ai_model:
                    try:
                        prompt = f"No disclaimers. Asset: {full_name} at {last_price}. User: {voice_in}. 2 sentences."
                        ans = ai_model.generate_content(prompt).text
                        st.info(f"**AI:** {ans}")
                        tts = gTTS(text=ans.replace('*',''), lang='en', tld=tld_map.get(accent_choice, "co.in"))
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                            tts.save(fp.name)
                            st.audio(fp.name, format="audio/mp3", autoplay=True)
                    except Exception: st.warning("⚠️ AI Engine Busy.")
