import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import io
import re
import requests
import urllib.parse
from datetime import datetime, timedelta, timezone
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

if 'last_refresh_count' not in st.session_state:
    st.session_state['last_refresh_count'] = 0

if refresh_count != st.session_state['last_refresh_count']:
    st.session_state['last_refresh_count'] = refresh_count
    st.session_state['portfolio_data'] = None
    st.toast('데이터가 최신 시세로 업데이트되었습니다.', icon='🔄')

if 'search_info' not in st.session_state:
    st.session_state['search_info'] = None

if 'sim_target_sheet' not in st.session_state:
    st.session_state['sim_target_sheet'] = None

if 'sim_df' not in st.session_state:
    st.session_state['sim_df'] = None

if 'user_principals' not in st.session_state:
    st.session_state['user_principals'] = {}

if 'raw_excel_data' not in st.session_state:
    st.session_state['raw_excel_data'] = None

if 'uploaded_filename' not in st.session_state:
    st.session_state['uploaded_filename'] = None

# -----------------------------------------------------------------------------
# 상단 타이틀 배너
# -----------------------------------------------------------------------------
col_title, col_time = st.columns([0.75, 0.25])
with col_title:
    st.title("🏦 Portfolio Manager v7.4")
    st.markdown("##### ✨ 깡통 정상화")
with col_time:
    kst_timezone = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst_timezone)
    now_str = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    st.write("") # 간격 맞춤
    st.caption(f"🕒 시스템 갱신 시간 (KST): {now_str}")
    if st.button("🔄 최신 시세로 즉시 갱신", use_container_width=True, type="primary"):
        st.session_state['portfolio_data'] = None
        st.rerun()

st.divider()

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
def get_hist_exchange_rate(target_date):
    try:
        start_str = (target_date - timedelta(days=7)).strftime('%Y-%m-%d')
        end_str = target_date.strftime('%Y-%m-%d')
        df = fdr.DataReader('USD/KRW', start_str, end_str)
        if not df.empty: return float(df['Close'].iloc[-1])
    except: pass
    return 1450.0

@st.cache_data(ttl=3600*24)
def get_hist_price(ticker, target_date, is_kr):
    start_str = (target_date - timedelta(days=10)).strftime('%Y-%m-%d')
    end_str = target_date.strftime('%Y-%m-%d')
    end_yf_str = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        if is_kr:
            clean_code = ticker.split('.')[0]
            try:
                df = fdr.DataReader(clean_code, start_str, end_str)
                if not df.empty: return float(df['Close'].iloc[-1])
            except: pass
            
            try:
                hist = yf.Ticker(f"{clean_code}.KS").history(start=start_str, end=end_yf_str)
                if not hist.empty: return float(hist['Close'].iloc[-1])
            except: pass
            
            try:
                hist = yf.Ticker(f"{clean_code}.KQ").history(start=start_str, end=end_yf_str)
                if not hist.empty: return float(hist['Close'].iloc[-1])
            except: pass
        else:
            hist = yf.Ticker(ticker).history(start=start_str, end=end_yf_str)
            if not hist.empty: return float(hist['Close'].iloc[-1])
    except: pass
    return 0.0

@st.cache_data(ttl=3600*12)
def get_korean_market_map():
    market_data = {}
    def add_to_map(df, default_sector="기타"):
        if df is None or df.empty: return
        code_col = 'Code' if 'Code' in df.columns else ('Symbol' if 'Symbol' in df.columns else None)
        name_col = 'Name'
        sector_col = 'Sector' if 'Sector' in df.columns else None
        if not code_col or not name_col: return
        for _, row in df.iterrows():
            name = str(row[name_col]).strip()
            code = str(row[code_col]).strip()
            sector = str(row[sector_col]).strip() if sector_col and pd.notna(row[sector_col]) else default_sector
            market_data[name] = {'code': code, 'sector': sector}

    try:
        add_to_map(fdr.StockListing('KOSPI'))
        add_to_map(fdr.StockListing('KOSDAQ'))
    except:
        try: add_to_map(fdr.StockListing('KRX'))
        except: pass
    try: add_to_map(fdr.StockListing('ETF/KR'), default_sector="ETF")
    except: pass
    return market_data

CUSTOM_STOCK_MAP = {
    '애플': 'AAPL', '마이크로소프트': 'MSFT', '테슬라': 'TSLA', '엔비디아': 'NVDA',
    '구글': 'GOOGL', '아마존': 'AMZN', '메타': 'META', '넷플릭스': 'NFLX',
    'AMD': 'AMD', '인텔': 'INTC', '퀄컴': 'QCOM', '브로드컴': 'AVGO',
    'SPY': 'SPY', 'QQQ': 'QQQ', 'SPLG': 'SPLG', 'SCHD': 'SCHD', 
    'JEPI': 'JEPI', 'TLT': 'TLT', 'SOXL': 'SOXL', 'TQQQ': 'TQQQ',
    '리얼티인컴': 'O', '아이온큐': 'IONQ', '팔란티어': 'PLTR',
    'IAU': 'IAU', '금': 'IAU', '골드': 'IAU', 'GLD': 'GLD',
    'TIGER KRX금현물': '0072R0', '금현물': '0072R0', 'KRX금': '0072R0'
}
TICKER_TO_KOREAN = {v: k for k, v in CUSTOM_STOCK_MAP.items()}

def resolve_ticker(input_str):
    input_str = str(input_str).strip()
    for k, v in CUSTOM_STOCK_MAP.items():
        if input_str.upper() == k.upper(): return v
    krx_map = get_korean_market_map()
    if input_str in krx_map: return krx_map[input_str]['code']
    return input_str.upper()

def is_korean_stock(ticker):
    ticker = str(ticker).strip().upper()
    if ticker.endswith('.KS') or ticker.endswith('.KQ'): return True
    if len(ticker) == 6 and ticker[0].isdigit(): return True
    return False

def resolve_ticker_naver(input_str):
    input_str = str(input_str).strip()
    if input_str.upper() in CUSTOM_STOCK_MAP: return CUSTOM_STOCK_MAP[input_str.upper()]
    for k, v in CUSTOM_STOCK_MAP.items():
        if input_str.upper() == k.upper(): return v
    if len(input_str) == 6 and input_str[0].isdigit(): return input_str
        
    try:
        query = urllib.parse.quote(input_str.encode('euc-kr'))
        url = f"https://ac.finance.naver.com/ac?q={query}&q_enc=euc-kr&st=111&r_format=json&t_koreng=1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=3)
        items = res.json().get('items', [[]])[0]
        if items: return items[0][1]
    except: pass
    return input_str.upper()

@st.cache_data(ttl=60)
def get_naver_stock_info(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        text = res.text
        
        name = code
        name_match = re.search(r'<div class="wrap_company">\s*<h2>.*?<a[^>]*>(.*?)</a>', text, re.IGNORECASE | re.DOTALL)
        if name_match: name = name_match.group(1).strip()
            
        price = 0
        price_match = re.search(r'<dd>현재가\s+([\d,]+)', text)
        if price_match: price = int(price_match.group(1).replace(',', ''))
        else:
            p_match = re.search(r'<p class="no_today">.*?<span class="blind">([\d,]+)</span>', text, re.IGNORECASE | re.DOTALL)
            if p_match: price = int(p_match.group(1).replace(',', ''))
                
        sector = '기타'
        sector_match = re.search(r'<dt><span class="blind">업종</span></dt>\s*<dd>(.*?)</dd>', text, re.IGNORECASE | re.DOTALL)
        if sector_match: sector = re.sub(r'<[^>]+>', '', sector_match.group(1)).strip()
            
        if price > 0: return {"name": name, "price": price, "sector": sector}
    except: pass
    return None

def get_current_price(ticker):
    ticker = str(ticker).strip().upper()
    try:
        if is_korean_stock(ticker):
            clean_code = ticker.split('.')[0]
            try:
                df = fdr.DataReader(clean_code)
                if not df.empty: return float(df['Close'].iloc[-1])
            except: pass
            try:
                hist = yf.Ticker(f"{clean_code}.KS").history(period="1d")
                if not hist.empty: return float(hist['Close'].iloc[-1])
            except: pass
            try:
                hist = yf.Ticker(f"{clean_code}.KQ").history(period="1d")
                if not hist.empty: return float(hist['Close'].iloc[-1])
            except: pass
            return 0.0
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period="1d")
        if not hist.empty: return float(hist['Close'].iloc[-1])
        return 0.0
    except: return 0.0

def get_stock_info_safe(input_str):
    ticker = resolve_ticker_naver(str(input_str))
    try:
        price = get_current_price(ticker)
        if price == 0: return None
        is_korean = is_korean_stock(ticker)
        country = '한국' if is_korean else '미국'
        currency = 'KRW' if is_korean else 'USD'
        name, sector, asset_type = ticker, '기타', '기타'
        clean_code = ticker.split('.')[0]

        if is_korean:
            naver_info = get_naver_stock_info(clean_code)
            if naver_info:
                name, price, sector = naver_info['name'], naver_info['price'], naver_info['sector']
                etf_kw = ['ETF', 'ETN', 'KODEX', 'TIGER', 'ACE', 'SOL', 'ARIRANG', 'KBSTAR', 'HANARO', 'KOSEF', '금현물', 'RISE']
                asset_type = 'ETF' if any(k in name.upper() for k in etf_kw) else '개별주식'
                return {'종목코드': clean_code, '종목명': name, '업종': sector, '현재가': price, '국가': country, '유형': asset_type, 'currency': currency}
            return None
        else:
            ticker_obj = yf.Ticker(ticker)
            hist = ticker_obj.history(period="1d")
            if hist.empty: return None
            price = float(hist['Close'].iloc[-1])
            info = ticker_obj.info
            name = info.get('shortName', ticker)
            if ticker in TICKER_TO_KOREAN: name = TICKER_TO_KOREAN[ticker]
            sector = info.get('sector', '기타')
            asset_type = 'ETF' if info.get('quoteType') == 'ETF' else '개별주식'
            return {'종목코드': ticker, '종목명': name, '업종': sector, '현재가': price, '국가': country, '유형': asset_type, 'currency': currency}
    except: return None

def classify_asset_type(row):
    name = str(row.get('종목명', '')).upper()
    ticker = str(row.get('종목코드', '')).upper()
    if ticker in ['KRW', 'USD'] or '예수금' in name: return '현금'
    etf_keywords = ['ETF', 'ETN', 'KODEX', 'TIGER', 'ACE', 'SOL', 'SPLG', 'IAU', 'QQQ', 'SPY', 'TLT', 'JEPI', 'SCHD', 'SOXL', 'TQQQ', 'GLD', '금현물', 'RISE']
    if any(k in name for k in etf_keywords) or any(k in ticker for k in etf_keywords): return 'ETF'
    return '개별주식'

def create_pie(data, names, title, value_col='평가금액'):
    if data.empty or value_col not in data.columns: return None
    fig = px.pie(data, values=value_col, names=names, title=title, hole=0.4)
    fig.update_traces(textposition='inside', textinfo='percent')
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.05),
        margin=dict(t=40, b=20, l=10, r=0)
    )
    return fig

def color_profit(val):
    if val > 0: return 'color: #ff2b2b'
    elif val < 0: return 'color: #00498c'
    return 'color: black'

def calculate_portfolio(df, usd_krw):
    current_prices, eval_values, buy_values, currencies = [], [], [], []
    krx_map = get_korean_market_map()
    code_to_name = {v['code']: k for k, v in krx_map.items()}

    for index, row in df.iterrows():
        raw_ticker = str(row['종목코드']).strip()
        ticker = raw_ticker.upper()
        current_name = str(row.get('종목명', ''))
        clean_code = ticker.split('.')[0]
        
        if not current_name or current_name == 'nan':
            if clean_code in code_to_name: df.at[index, '종목명'] = code_to_name[clean_code]
            else:
                for k, v in CUSTOM_STOCK_MAP.items():
                    if v == ticker: df.at[index, '종목명'] = k

        qty = float(row['수량'])
        avg_price = float(row['매수단가'])
        country = str(row.get('국가', '')).strip()

        is_kr_stock = (country == '한국') or is_korean_stock(ticker)
        price = 0.0

        if ticker == 'KRW':
            price, eval_val, buy_val, currency = 1.0, qty, qty * avg_price, 'KRW'
        elif ticker == 'USD':
            price = usd_krw
            eval_val = qty * usd_krw
            buy_val = (qty * avg_price * usd_krw) if avg_price < 50 else (qty * avg_price)
            currency = 'USD'
        elif is_kr_stock:
            n_info = get_naver_stock_info(clean_code)
            if n_info:
                price = float(n_info['price'])
                if not current_name or current_name == 'nan' or current_name.isdigit(): df.at[index, '종목명'] = n_info['name']
                if '업종' not in df.columns or df.at[index, '업종'] == '기타': df.at[index, '업종'] = n_info['sector']
            eval_val, buy_val, currency = price * qty, avg_price * qty, 'KRW'
        else:
            hist = yf.Ticker(ticker).history(period="1d")
            if not hist.empty: price = float(hist['Close'].iloc[-1])
            if not current_name or current_name == 'nan' or current_name == ticker: df.at[index, '종목명'] = TICKER_TO_KOREAN.get(ticker, ticker)
            eval_val, buy_val, currency = price * qty * usd_krw, avg_price * qty * usd_krw, 'USD'
        
        current_prices.append(price)
        eval_values.append(eval_val)
        buy_values.append(buy_val)
        currencies.append(currency)

    df['현재가'] = current_prices
    df['매수금액'] = buy_values
    df['평가금액'] = eval_values
    df['수익률'] = df.apply(lambda x: ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100) if x['매수금액'] > 0 else 0, axis=1)
    df['유형'] = df.apply(classify_asset_type, axis=1)
    df['통화'] = currencies
    if '업종' not in df.columns: df['업종'] = '기타'
    df['업종'] = df['업종'].fillna('기타')
    if '시뮬레이션 수량' not in df.columns: df['시뮬레이션 수량'] = df['수량']
    return df

# -----------------------------------------------------------------------------
# 3. 엑셀 다운로드 및 PDF 로드 기능
# -----------------------------------------------------------------------------
def get_template_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame({'종목코드': ['005930', 'KRW'], '종목명': ['삼성전자', '원화예수금'], '업종': ['반도체', '현금'], '국가': ['한국', '한국'], '수량': [10, 1000000], '매수단가': [70000, 1], '납입원금': [2000000, 0]}).to_excel(writer, index=False, sheet_name='국내계좌')
        pd.DataFrame({'종목코드': ['AAPL', 'IAU', 'USD'], '종목명': ['애플', 'iShares Gold', '달러예수금'], '업종': ['IT', '원자재', '현금'], '국가': ['미국', '미국', '미국'], '수량': [5, 10, 1000], '매수단가': [150, 40, 1], '납입원금': [3000, 0, 0]}).to_excel(writer, index=False, sheet_name='미국계좌')
        pd.DataFrame({'종목코드': ['005930', '0072R0'], '종목명': ['삼성전자', 'TIGER KRX금현물'], '업종': ['반도체', '원자재'], '국가': ['한국', '한국'], '수량': [100, 50], '매수단가': [60000, 12000], '납입원금': [6000000, 0]}).to_excel(writer, index=False, sheet_name='퇴직연금(IRP)')
    return output.getvalue()

def get_guide_pdf():
    try:
        with open("포트폴리오 매니저_엑셀작성가이드.pdf", "rb") as f:
            return f.read()
    except FileNotFoundError:
        # [오류수정] 한글 문자가 포함된 경우 바이트 리터럴 b"" 대신 encode() 사용
        return "PDF 파일이 깃허브 저장소에 없습니다. 파일명(포트폴리오 매니저_엑셀작성가이드.pdf)을 확인해주세요.".encode('utf-8')

# -----------------------------------------------------------------------------
# 4. 파일 업로드 및 데이터 로딩 UI
# -----------------------------------------------------------------------------
uploaded_file = None

if st.session_state['portfolio_data'] is None and st.session_state['raw_excel_data'] is None:
    st.markdown("### 🚀 자산 포트폴리오 관리 시작하기")
    
    col_dl, col_up = st.columns([1, 1.5])
    with col_dl:
        st.info("💡 **Step 1.** 처음이신가요?\n\n엑셀 양식과 작성 가이드를 다운로드하여 보유 자산을 입력하세요.")
        st.download_button(
            label="📄 표준 엑셀 양식 다운로드", 
            data=get_template_excel(), 
            file_name='portfolio_template_v7.4.xlsx', 
            use_container_width=True
        )
        st.download_button(
            label="📥 엑셀 작성 가이드 (PDF)", 
            data=get_guide_pdf(), 
            file_name='포트폴리오 매니저_엑셀작성가이드.pdf', 
            mime='application/pdf',
            use_container_width=True
        )
    with col_up:
        st.success("💡 **Step 2.** 데이터 업로드\n\n작성하신 엑셀 파일을 아래에 드래그하여 업로드하세요.")
        uploaded_file = st.file_uploader("엑셀 파일 업로드", type=['xlsx'], label_visibility="collapsed")
    
    if uploaded_file is None:
        st.stop()
else:
    with st.expander("📁 데이터 파일 재업로드 및 양식/가이드 다운로드"):
        col_dl, col_up = st.columns([1, 1.5])
        with col_dl:
            st.markdown("**양식 및 가이드 다운로드**")
            st.download_button("📄 표준 엑셀 양식 받기", data=get_template_excel(), file_name='portfolio_template_v7.4.xlsx', use_container_width=True)
            st.download_button("📥 엑셀 작성 가이드 (PDF)", data=get_guide_pdf(), file_name='포트폴리오 매니저_엑셀작성가이드.pdf', mime='application/pdf', use_container_width=True)
        with col_up:
            st.markdown("**데이터 재업로드**")
            uploaded_file = st.file_uploader("새로운 엑셀 파일 업로드", type=['xlsx'], label_visibility="collapsed")

# -----------------------------------------------------------------------------
# 파일 업로드 감지 로직
# -----------------------------------------------------------------------------
if uploaded_file is not None:
    if st.session_state['uploaded_filename'] != uploaded_file.name:
        st.session_state['raw_excel_data'] = pd.read_excel(uploaded_file, sheet_name=None)
        st.session_state['uploaded_filename'] = uploaded_file.name
        st.session_state['portfolio_data'] = None 
        st.rerun()

if st.session_state['raw_excel_data'] is not None:
    if st.session_state['portfolio_data'] is None:
        try:
            usd_krw = get_exchange_rate()
            xls = st.session_state['raw_excel_data']
            
            processed_data = {}
            excel_principals = {}

            with st.spinner(f'데이터 계산 및 최신 주가 연동 중... (환율: {usd_krw:,.2f}원)'):
                for sheet_name, df_sheet in xls.items():
                    required = ['종목코드', '종목명', '수량', '매수단가']
                    if not all(col in df_sheet.columns for col in required): continue
                    
                    if '납입원금' in df_sheet.columns:
                        first_val = df_sheet['납입원금'].iloc[0]
                        if pd.notna(first_val): excel_principals[sheet_name] = float(first_val)

                    processed_df = calculate_portfolio(df_sheet.copy(), usd_krw)
                    processed_df['계좌명'] = sheet_name
                    processed_data[sheet_name] = processed_df
            
            if not processed_data: st.error("데이터를 읽을 수 없습니다."); st.stop()
            st.session_state['portfolio_data'] = processed_data
            st.session_state['usd_krw'] = usd_krw
            if excel_principals:
                for k, v in excel_principals.items(): st.session_state['user_principals'][k] = v
        except Exception as e:
            st.error(f"오류: {e}"); st.stop()

    portfolio_dict = st.session_state['portfolio_data']
    usd_krw = st.session_state['usd_krw']

    # ==========================================
    # 사이드바: 수익률 비교 기준 설정 (3개 옵션)
    # ==========================================
    with st.sidebar:
        st.header("📈 수익률 비교 기준")
        compare_mode = st.radio("기준 선택", ["💰 납입원금 기준", "📊 매입원가 기준", "📅 특정기준일 기준"], index=0)
        
        target_date = None
        if compare_mode == "📅 특정기준일 기준":
            target_date = st.date_input("기준일 선택", value=datetime.today() - timedelta(days=1), max_value=datetime.today())
            st.caption(f"선택한 날짜({target_date.strftime('%y.%m.%d')}) 종가로 수익률 재계산")
            
        st.divider()
        
        st.header("💰 계좌별 납입원금 설정")
        if compare_mode != "💰 납입원금 기준":
            st.warning("💡 '납입원금 기준'을 선택해야 총 수익률 계산에 아래 금액이 반영됩니다.")
        else:
            st.caption("엑셀에 '납입원금' 열을 추가하면 자동 입력됩니다.")
            
        updated_principals = {}
        for sheet_name, df in portfolio_dict.items():
            default_val = df['매수금액'].sum()
            current_val = st.session_state['user_principals'].get(sheet_name, default_val)
            val = st.number_input(f"{sheet_name}", min_value=0.0, value=float(current_val), step=10000.0, format="%.0f", key=f"input_{sheet_name}")
            updated_principals[sheet_name] = val
        st.session_state['user_principals'] = updated_principals

    # ==========================================
    # 모드별 데이터 재가공 로직
    # ==========================================
    display_dict = {}
    account_base_vals = {}
    price_col_name = "기준일종가" if compare_mode == "📅 특정기준일 기준" else "매수단가"

    with st.spinner("비교 데이터를 처리하는 중입니다..."):
        hist_ex_rate = get_hist_exchange_rate(target_date) if compare_mode == "📅 특정기준일 기준" else 1450.0
        
        for sheet, df in portfolio_dict.items():
            new_df = df.copy()
            if compare_mode == "📅 특정기준일 기준":
                hist_prices = []
                hist_bases = []
                for _, row in new_df.iterrows():
                    t = row['종목코드']
                    qty = row['수량']
                    is_kr = (row['국가'] == '한국') or is_korean_stock(t)
                    
                    if t == 'KRW': hp, hb = 1.0, qty
                    elif t == 'USD': hp, hb = hist_ex_rate, qty * hist_ex_rate
                    else:
                        hp = get_hist_price(t, target_date, is_kr)
                        hb = hp * qty if is_kr else hp * qty * hist_ex_rate
                        
                    hist_prices.append(hp)
                    hist_bases.append(hb)
                    
                new_df[price_col_name] = hist_prices
                new_df['비교금액'] = hist_bases
                new_df['수익률'] = new_df.apply(lambda x: ((x['평가금액'] - x['비교금액']) / x['비교금액'] * 100) if x['비교금액'] > 0 else 0, axis=1)
                account_base_vals[sheet] = sum(hist_bases)
                
            elif compare_mode == "📊 매입원가 기준":
                new_df[price_col_name] = new_df['매수단가']
                new_df['비교금액'] = new_df['매수금액']
                account_base_vals[sheet] = new_df['매수금액'].sum()
                
            else: # "💰 납입원금 기준"
                new_df[price_col_name] = new_df['매수단가']
                new_df['비교금액'] = new_df['매수금액']
                account_base_vals[sheet] = st.session_state['user_principals'].get(sheet, new_df['매수금액'].sum())
                
            display_dict[sheet] = new_df

    # --- 퇴직연금/IRP/DC 제외 로직 ---
    HIDDEN_KEYWORDS = ['퇴직연금', 'IRP', 'DC']
    dashboard_dfs = []
    dashboard_total_base = 0
    
    for name, df in display_dict.items():
        if not any(k in name for k in HIDDEN_KEYWORDS):
            dashboard_dfs.append(df)
            dashboard_total_base += account_base_vals[name]

    all_df_dashboard = pd.concat(dashboard_dfs, ignore_index=True) if dashboard_dfs else pd.DataFrame() 
    all_df_raw = pd.concat(portfolio_dict.values(), ignore_index=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📊 통합 대시보드", "📂 계좌별 상세", "🎛️ 시뮬레이션", "📝 원본 데이터"])

    # --- [TAB 1] 통합 대시보드 ---
    with tab1:
        st.subheader("🌐 전체 자산 현황 (퇴직연금 제외)")
        if not all_df_dashboard.empty:
            total_eval = all_df_dashboard['평가금액'].sum()
            total_base = dashboard_total_base
            profit = total_eval - total_base
            yield_rate = (profit / total_base * 100) if total_base > 0 else 0
            
            if compare_mode == "💰 납입원금 기준": base_label = "총 납입원금"
            elif compare_mode == "📊 매입원가 기준": base_label = "총 매입원가"
            else: base_label = f"기준 평가액 ({target_date.strftime('%m/%d')})"
            
            m1, m2, m3 = st.columns(3)
            m1.metric(base_label, f"{total_base:,.0f} 원")
            m2.metric("총 평가금액", f"{total_eval:,.0f} 원", f"{profit:+,.0f} 원")
            m3.metric("총 수익률", f"{yield_rate:.2f} %", f"{yield_rate:.2f} %")
            st.divider()
            
            r1_c1, r1_c2 = st.columns(2)
            with r1_c1: st.plotly_chart(create_pie(all_df_dashboard, '종목명', "1. 종목별 비중"), use_container_width=True, key='t1_c1')
            with r1_c2: st.plotly_chart(create_pie(all_df_dashboard, '업종', "2. 업종(섹터)별 비중"), use_container_width=True, key='t1_c2')
            r2_c1, r2_c2 = st.columns(2)
            with r2_c1: st.plotly_chart(create_pie(all_df_dashboard, '국가', "3. 국가별 비중"), use_container_width=True, key='t1_c3')
            with r2_c2: st.plotly_chart(create_pie(all_df_dashboard, '유형', "4. 자산 유형별 비중"), use_container_width=True, key='t1_c4')

            st.divider()
            st.subheader("📋 전체 자산 상세")
            summary_cols = ['계좌명', '종목명', '업종', '국가', '수량', price_col_name, '현재가', '수익률', '평가금액']
            
            fmt_dict = {'수량': '{:,.2f}', price_col_name: '{:,.0f}', '현재가': '{:,.0f}', '수익률': '{:+.2f}%', '평가금액': '{:,.0f}'}
            st.dataframe(
                all_df_dashboard[summary_cols].style.format(fmt_dict).map(color_profit, subset=['수익률']),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("통합 대시보드에 표시할 계좌가 없습니다.")

    # --- [TAB 2] 계좌별 상세 ---
    with tab2:
        sheet_names = list(display_dict.keys())
        selected_sheet = st.selectbox("계좌 선택:", sheet_names)
        target_df = display_dict[selected_sheet]
        
        sheet_base = account_base_vals[selected_sheet]
        t_eval = target_df['평가금액'].sum()
        t_profit = t_eval - sheet_base
        t_yield = (t_profit / sheet_base * 100) if sheet_base > 0 else 0
        
        if compare_mode == "💰 납입원금 기준": base_label = "계좌 납입원금"
        elif compare_mode == "📊 매입원가 기준": base_label = "계좌 매입원가"
        else: base_label = f"기준 평가액 ({target_date.strftime('%m/%d')})"
        
        m1, m2, m3 = st.columns(3)
        m1.metric(base_label, f"{sheet_base:,.0f} 원")
        m2.metric("계좌 평가금액", f"{t_eval:,.0f} 원", f"{t_profit:+,.0f} 원")
        m3.metric("계좌 수익률", f"{t_yield:.2f} %", f"{t_yield:.2f} %")
        st.divider()
        
        c1, c2, c3 = st.columns(3)
        with c1: st.plotly_chart(create_pie(target_df, '종목명', "1. 종목 비중"), use_container_width=True, key='t2_c1')
        with c2: st.plotly_chart(create_pie(target_df, '업종', "2. 업종(섹터) 비중"), use_container_width=True, key='t2_c2_new')
        with c3: st.plotly_chart(create_pie(target_df, '유형', "3. 유형 비중"), use_container_width=True, key='t2_c3')
        
        st.caption(f"📋 {selected_sheet} 보유 종목")
        
        fmt_dict_tab2 = {'수량': '{:,.2f}', price_col_name: '{:,.0f}', '현재가': '{:,.0f}', '수익률': '{:+.2f}%', '평가금액': '{:,.0f}'}
        st.dataframe(
            target_df[['종목명', '업종', '수량', price_col_name, '현재가', '수익률', '평가금액']].style.format(fmt_dict_tab2).map(color_profit, subset=['수익률']),
            use_container_width=True, hide_index=True
        )

    # --- [TAB 3] 시뮬레이션 ---
    with tab3:
        st.header("🎛️ 리밸런싱 시뮬레이션")
        sim_sheets = list(portfolio_dict.keys())
        sel_sim_sheet = st.selectbox("시뮬레이션 대상 계좌:", sim_sheets, key='sim_sel')
        
        if st.session_state['sim_target_sheet'] != sel_sim_sheet:
            st.session_state['sim_target_sheet'] = sel_sim_sheet
            st.session_state['sim_df'] = portfolio_dict[sel_sim_sheet].copy()
            st.rerun()
            
        sim_df = st.session_state['sim_df']
        cur_total = portfolio_dict[sel_sim_sheet]['평가금액'].sum()

        # [원상복구] 시뮬레이션 종목 검색창
        with st.expander("➕ 종목 추가하기 (검색 및 자동완성)"):
            krx_map = get_korean_market_map()
            search_options = [f"{k} ({v})" for k, v in CUSTOM_STOCK_MAP.items()]
            for k, v in krx_map.items():
                opt = f"{k} ({v['code']})"
                if opt not in search_options: search_options.append(opt)
            
            search_mode_ui = st.radio("검색 방식 선택", ["📝 리스트에서 검색 (국내 종목/ETF 자동완성)", "⌨️ 직접 입력 (해외 종목/코드 입력)"], horizontal=True)
            ac1, ac2 = st.columns([3, 1])
            
            if "리스트" in search_mode_ui:
                input_val = ac1.selectbox("종목을 선택하세요 (타이핑하여 검색 가능)", [""] + search_options, index=0)
            else:
                input_val = ac1.text_input("종목명 또는 티커(코드) 직접 입력", placeholder="예: TSLA, AAPL, 005930")
                
            if ac2.button("검색", use_container_width=True):
                if not input_val: st.error("종목을 선택하거나 입력해주세요.")
                else:
                    search_target = input_val
                    if "리스트" in search_mode_ui:
                        match = re.search(r'\((.*?)\)$', input_val)
                        if match: search_target = match.group(1)
                            
                    info = get_stock_info_safe(search_target)
                    if info: st.session_state['search_info'] = info
                    else: st.error("종목을 찾을 수 없습니다. 이름이나 코드를 다시 확인해주세요.")
            
        if st.session_state['search_info']:
            inf = st.session_state['search_info']
            search_res_df = pd.DataFrame([{'종목코드': inf['종목코드'], '종목명': inf['종목명'], '현재가': inf['현재가']}])
            st.dataframe(search_res_df.style.format({'현재가': '{:,.0f} 원'}), hide_index=True, use_container_width=True)
            
            if st.button("리스트에 추가"):
                new_row = {
                    '종목코드': inf['종목코드'], '종목명': inf['종목명'], '업종': inf['업종'],
                    '국가': inf['국가'], '유형': inf['유형'], '수량': 0, '매수단가': 0,
                    '현재가': inf['현재가'], '매수금액': 0, '평가금액': 0, '수익률': 0,
                    '통화': inf['currency'], '시뮬레이션 수량': 0, '계좌명': sel_sim_sheet
                }
                st.session_state['sim_df'] = pd.concat([sim_df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state['search_info'] = None
                st.rerun()

        edited = st.data_editor(
            sim_df[['종목명', '종목코드', '현재가', '시뮬레이션 수량']],
            column_config={
                "종목명": st.column_config.TextColumn("종목명", disabled=True),
                "종목코드": st.column_config.TextColumn("코드", disabled=True),
                "현재가": st.column_config.NumberColumn("현재가", format="%d 원", disabled=True),
                "시뮬레이션 수량": st.column_config.NumberColumn("목표 수량", min_value=0, step=1, format="%.2f")
            },
            use_container_width=True, num_rows="dynamic", key="sim_editor"
        )
        
        valid_indices = edited.index.intersection(sim_df.index)
        sim_df = sim_df.loc[valid_indices].copy()
        sim_df['시뮬레이션 수량'] = edited.loc[valid_indices, '시뮬레이션 수량']
        st.session_state['sim_df'] = sim_df
        
        def calc_sim_total(row):
            p, q = row['현재가'], row['시뮬레이션 수량']
            return p * q * usd_krw if row['통화'] == 'USD' or row['국가'] == '미국' else p * q
        
        sim_df['예상 평가금액'] = sim_df.apply(calc_sim_total, axis=1)
        sim_df['수량변동'] = sim_df['시뮬레이션 수량'] - sim_df['수량']
        
        def calc_diff_amt(row):
            p, q_diff = row['현재가'], row['수량변동']
            return p * q_diff * usd_krw if row['통화'] == 'USD' or row['국가'] == '미국' else p * q_diff

        sim_df['매매금액'] = sim_df.apply(calc_diff_amt, axis=1)
        sim_total = sim_df['예상 평가금액'].sum()
        diff = cur_total - sim_total
        
        st.divider()
        c_res1, c_res2 = st.columns([1, 2])
        with c_res1:
            st.metric("현재 자산", f"{cur_total:,.0f} 원")
            st.metric("시뮬레이션 후", f"{sim_total:,.0f} 원")
            if diff >= 0: st.success(f"잔액: {diff:,.0f} 원")
            else: st.error(f"부족: {abs(diff):,.0f} 원")
        
        st.markdown("##### 📝 리밸런싱 매매 계획표")
        plan_df = sim_df[sim_df['수량변동'] != 0].copy()
        
        if not plan_df.empty:
            plan_df['구분'] = plan_df['수량변동'].apply(lambda x: '매수 (BUY)' if x > 0 else '매도 (SELL)')
            plan_display = plan_df[['종목명', '종목코드', '현재가', '구분', '수량', '시뮬레이션 수량', '수량변동', '매매금액']].copy()
            plan_display.columns = ['종목명', '코드', '현재가', '구분', '현재수량', '목표수량', '변동수량', '예상 소요금액']
            
            st.dataframe(
                plan_display.style.format({
                    '현재가': '{:,.0f}', '현재수량': '{:,.2f}', '목표수량': '{:,.2f}', '변동수량': '{:+,.2f}', '예상 소요금액': '{:+,.0f} 원'
                }).map(lambda x: 'color: #ff2b2b' if x > 0 else 'color: #00498c', subset=['변동수량', '예상 소요금액']),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("💡 수량 변동 사항이 없습니다.")

        st.divider()
        c1, c2, c3 = st.columns(3)
        valid_sim = sim_df[sim_df['예상 평가금액'] > 0]
        with c1: st.plotly_chart(create_pie(valid_sim, '종목명', "1. 종목 비중"), use_container_width=True, key='t3_c1')
        with c2: st.plotly_chart(create_pie(valid_sim, '업종', "2. 업종 비중"), use_container_width=True, key='t3_c2')
        with c3: st.plotly_chart(create_pie(valid_sim, '유형', "3. 유형 비중"), use_container_width=True, key='t3_c3')

    # --- [TAB 4] 원본 데이터 ---
    with tab4:
        st.dataframe(all_df_raw)
