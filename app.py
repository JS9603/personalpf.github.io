import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import io
from datetime import datetime
import FinanceDataReader as fdr
import time
from streamlit_autorefresh import st_autorefresh

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 세션 초기화
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Portfolio Manager", layout="wide", page_icon="🏦")

# 5분(300초)마다 페이지 자동 새로고침
refresh_count = st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")

if 'portfolio_data' not in st.session_state:
    st.session_state['portfolio_data'] = None

# 자동 갱신 감지 로직
if 'last_refresh_count' not in st.session_state:
    st.session_state['last_refresh_count'] = 0

if refresh_count != st.session_state['last_refresh_count']:
    st.session_state['last_refresh_count'] = refresh_count
    st.session_state['portfolio_data'] = None
    # [수정] icon='casting' -> icon='🔄' (유효한 이모지로 변경)
    st.toast('데이터가 최신 시세로 업데이트되었습니다.', icon='🔄')

if 'search_info' not in st.session_state:
    st.session_state['search_info'] = None

if 'sim_target_sheet' not in st.session_state:
    st.session_state['sim_target_sheet'] = None

if 'sim_df' not in st.session_state:
    st.session_state['sim_df'] = None

# 상단 헤더
col_title, col_time = st.columns([0.7, 0.3])
with col_title:
    st.title("🏦 포트폴리오 매니저 v5.2")
    st.markdown("Stable Fix")
with col_time:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.write("") 
    st.caption(f"🕒 최종 갱신: {now_str}")
    if st.button("🔄 즉시 갱신"):
        st.session_state['portfolio_data'] = None
        st.rerun()

# -----------------------------------------------------------------------------
# 2. 데이터 처리 및 검색 함수
# -----------------------------------------------------------------------------

@st.cache_data(ttl=60)
def get_exchange_rate():
    try:
        return fdr.DataReader('USD/KRW')['Close'].iloc[-1]
    except:
        return 1450.0

@st.cache_data(ttl=300)
def get_all_exchange_rates():
    rates = {'USD': 1450.0, 'JPY': 9.5, 'CNY': 200.0}
    try:
        rates['USD'] = fdr.DataReader('USD/KRW')['Close'].iloc[-1]
        rates['JPY'] = fdr.DataReader('JPY/KRW')['Close'].iloc[-1] / 100
        rates['CNY'] = fdr.DataReader('CNY/KRW')['Close'].iloc[-1]
    except: pass
    return rates

@st.cache_data(ttl=3600*24)
def get_krx_code_map():
    try:
        df = fdr.StockListing('KRX')
        name_to_code = dict(zip(df['Name'], df['Code']))
        return name_to_code
    except:
        return {}

US_STOCK_MAP = {
    '애플': 'AAPL', '마이크로소프트': 'MSFT', '테슬라': 'TSLA', '엔비디아': 'NVDA',
    '구글': 'GOOGL', '아마존': 'AMZN', '메타': 'META', '넷플릭스': 'NFLX',
    'AMD': 'AMD', '인텔': 'INTC', '퀄컴': 'QCOM', '브로드컴': 'AVGO',
    'SPY': 'SPY', 'QQQ': 'QQQ', 'SPLG': 'SPLG', 'SCHD': 'SCHD', 
    'JEPI': 'JEPI', 'TLT': 'TLT', 'SOXL': 'SOXL', 'TQQQ': 'TQQQ',
    '리얼티인컴': 'O', '아이온큐': 'IONQ', '팔란티어': 'PLTR',
    'IAU': 'IAU', '금': 'IAU', '골드': 'IAU', 'GLD': 'GLD' 
}

def resolve_ticker(input_str):
    input_str = input_str.strip()
    if input_str in US_STOCK_MAP:
        return US_STOCK_MAP[input_str]
    krx_map = get_krx_code_map()
    if input_str in krx_map:
        return krx_map[input_str]
    return input_str.upper()

def get_current_price(ticker):
    ticker = str(ticker).strip().upper()
    try:
        if (ticker.isdigit() and len(ticker) == 6) or ticker.endswith('.KS') or ticker.endswith('.KQ'):
            code = ticker.split('.')[0]
            df = fdr.DataReader(code)
            if not df.empty:
                return df['Close'].iloc[-1]
            return 0.0
        else:
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                return hist['Close'].iloc[-1]
            return 0.0
    except:
        return 0.0

def get_stock_info_safe(input_str):
    ticker = resolve_ticker(str(input_str))
    try:
        price = get_current_price(ticker)
        if price == 0: return None
        
        is_korean = (ticker.isdigit() and len(ticker) == 6) or ticker.endswith('.KS') or ticker.endswith('.KQ')
        country = '한국' if is_korean else '미국'
        currency = 'KRW' if is_korean else 'USD'

        try:
            info = yf.Ticker(ticker).info
            name = info.get('shortName', ticker)
            sector = info.get('sector', '기타')
            
            return {
                '종목코드': ticker, 
                '종목명': name,
                '업종': sector, 
                '현재가': price,
                '국가': country,
                '유형': 'ETF' if info.get('quoteType') == 'ETF
