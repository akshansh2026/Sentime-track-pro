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
import random # Injected for jitter logic

# --- SECURE API KEY LOADING ---
load_dotenv() 

# SOLUTION INJECTED: Secrets Bridge for Cloud Deployment
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
    # Solution Injected: Verified number for cloud testing
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

    # --- DATA ENGINES (INJECTED SOLUTION: RATE LIMIT RETRY) ---
    @st.cache_data(ttl=3600) 
    def get_asset_info(ticker):
        for i in range(3): # Attempt 3 retries for cloud stability
            try:
                time.sleep(random.uniform(0.5, 1.5)) # Solution: Jitter delay
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
                time.sleep(2) # Wait before retrying

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
        st.warning(f"⚠️ Market Data Throttled. Please wait 30 seconds and refresh.")
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
        # MODULE: MY PROFILE (FIXED HTML)
        # -------------------------------------------------------------
        if nav == "👤 My Profile":
            user_initial = st.session_state.current_user['name'][0].upper()
            
            st.markdown(f"""
<div style="background: linear-gradient(135deg, {grad_1} 0%, {card_bg} 100%); padding: 40px; border-radius: 12px; border: 1px solid {border_col}; margin-bottom: 25px;">
    <div style="display: flex; align-items: center; gap: 20px;">
        <div style="width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%); display: flex; justify-content: center; align-items: center; color: white; font-size: 36px; font-weight: bold;">
            {user_initial}
        </div>
        <div>
            <h1 style="color:{text_color}; margin:0;">{st.session_state.current_user['name']}</h1>
            <p style="color:#00CC96; font-size: 14px; margin-top:5px; font-weight: 600;">🟢 PRO SUBSCRIPTION ACTIVE</p>
        </div>
    </div>
</div>
<div style="background:{card_bg}; padding: 25px; border-radius: 10px; border: 1px solid {border_col}; margin-bottom: 20px;">
    <h5 style="color:{sub_text}; margin-bottom: 20px; font-size: 13px; text-transform: uppercase;">Registered Credentials</h5>
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

        # [ALL OTHER PREVIOUS MODULES: Backtester, simulator, etc. remain unchanged]
