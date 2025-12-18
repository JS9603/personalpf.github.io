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
    st.toast('🔄 데이터가 최신 시세로 업데이트되었습니다.', icon='casting')

if 'search_info' not in st.session_state:
    st.session_state['search_info'] = None

if 'sim_target_sheet' not in st.session_state:
    st.session_state['sim_target_sheet'] = None

if 'sim_df' not in st.session_state:
    st.session_state['sim_df'] = None

# 상단 헤더
col_title, col_time = st.columns([0.7, 0.3])
with col_title:
    st.title("🏦 포트폴리오 매니저 v5.1")
    st.markdown("Hotfix")
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

# [수정] IAU 및 금 관련 매핑 추가
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
        
        # [수정] 국가/통화 사전 판별 로직 추가 (yfinance 실패 대비)
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
                '유형': 'ETF' if info.get('quoteType') == 'ETF' else '개별주식',
                'currency': currency
            }
        except:
            # [수정] yfinance 정보 실패 시, 사전에 판별한 올바른 국가/통화 사용
            return {
                '종목코드': ticker, '종목명': ticker, '업종': '기타', '현재가': price,
                '국가': country, '유형': '기타', 'currency': currency
            }
    except:
        return None

def classify_asset_type(row):
    name = str(row.get('종목명', '')).upper()
    ticker = str(row.get('종목코드', '')).upper()
    if ticker in ['KRW', 'USD'] or '예수금' in name: return '현금'
    # [참고] IAU는 이미 etf_keywords에 포함되어 있음
    etf_keywords = ['ETF', 'ETN', 'KODEX', 'TIGER', 'ACE', 'SOL', 'SPLG', 'IAU', 'QQQ', 'SPY', 'TLT', 'JEPI', 'SCHD', 'SOXL', 'TQQQ', 'GLD']
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
    krx_map = get_krx_code_map()
    code_to_name = {v: k for k, v in krx_map.items()}

    for index, row in df.iterrows():
        raw_ticker = str(row['종목코드']).strip()
        ticker = raw_ticker.upper()
        
        current_name = str(row.get('종목명', ''))
        clean_code = ticker.split('.')[0]
        if (not current_name or current_name == 'nan') and clean_code in code_to_name:
             df.at[index, '종목명'] = code_to_name[clean_code]

        qty = float(row['수량'])
        avg_price = float(row['매수단가'])
        country = str(row.get('국가', '')).strip()

        if ticker == 'KRW':
            price = 1.0
            eval_val = qty
            buy_val = qty * avg_price
            currency = 'KRW'
        elif ticker == 'USD':
            price = usd_krw
            eval_val = qty * usd_krw
            if avg_price < 50: 
                buy_val = qty * avg_price * usd_krw 
            else:
                buy_val = qty * avg_price
            currency = 'USD'
        else:
            price = get_current_price(ticker)
            # [수정] 미국 주식 판별 로직 강화 (IAU 등 오류 방지)
            is_us_stock = country == '미국' or ticker == 'USD' or (not ticker.endswith('.KS') and not ticker.isdigit() and not ticker.endswith('.KQ'))
            
            if is_us_stock:
                eval_val = price * qty * usd_krw
                buy_val = avg_price * qty * usd_krw
                currency = 'USD'
            else:
                eval_val = price * qty
                buy_val = avg_price * qty
                currency = 'KRW'
        
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
# 3. 엑셀 다운로드
# -----------------------------------------------------------------------------
def get_template_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1 = pd.DataFrame({'종목코드': ['005930', 'KRW'], '종목명': ['삼성전자', '원화예수금'], '업종': ['반도체', '현금'], '국가': ['한국', '한국'], '수량': [10, 1000000], '매수단가': [70000, 1]})
        df1.to_excel(writer, index=False, sheet_name='국내계좌')
        df2 = pd.DataFrame({'종목코드': ['AAPL', 'IAU', 'USD'], '종목명': ['애플', 'iShares Gold', '달러예수금'], '업종': ['IT', '원자재', '현금'], '국가': ['미국', '미국', '미국'], '수량': [5, 10, 1000], '매수단가': [150, 40, 1]})
        df2.to_excel(writer, index=False, sheet_name='미국계좌')
    return output.getvalue()

with st.expander("⬇️ 엑셀 양식 다운로드"):
    st.download_button(label="엑셀 양식 받기 (.xlsx)", data=get_template_excel(), file_name='portfolio_template_v5.xlsx')

# -----------------------------------------------------------------------------
# 4. 메인 로직
# -----------------------------------------------------------------------------
uploaded_file = st.file_uploader("📂 엑셀 파일을 업로드하세요", type=['xlsx'])

if uploaded_file is not None:
    if st.session_state['portfolio_data'] is None:
        try:
            usd_krw = get_exchange_rate()
            xls = pd.read_excel(uploaded_file, sheet_name=None)
            
            processed_data = {}
            with st.spinner(f'데이터 갱신 중... (환율: {usd_krw:,.2f}원)'):
                for sheet_name, df_sheet in xls.items():
                    required = ['종목코드', '종목명', '수량', '매수단가']
                    if not all(col in df_sheet.columns for col in required): continue
                    
                    processed_df = calculate_portfolio(df_sheet.copy(), usd_krw)
                    processed_df['계좌명'] = sheet_name
                    processed_data[sheet_name] = processed_df
            
            if not processed_data:
                st.error("데이터를 읽을 수 없습니다.")
                st.stop()
            
            st.session_state['portfolio_data'] = processed_data
            st.session_state['usd_krw'] = usd_krw
            
        except Exception as e:
            st.error(f"오류: {e}")
            st.stop()

    portfolio_dict = st.session_state['portfolio_data']
    usd_krw = st.session_state['usd_krw']
    all_df = pd.concat(portfolio_dict.values(), ignore_index=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📊 통합 대시보드", "📂 계좌별 상세", "🎛️ 시뮬레이션", "📝 원본 데이터"])

    # --- [TAB 1] 통합 대시보드 ---
    with tab1:
        st.subheader("🌐 전체 자산 현황")
        total_eval = all_df['평가금액'].sum()
        total_buy = all_df['매수금액'].sum()
        profit = total_eval - total_buy
        yield_rate = (profit / total_buy * 100) if total_buy > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("총 매수금액", f"{total_buy:,.0f} 원")
        m2.metric("총 평가금액", f"{total_eval:,.0f} 원", f"{profit:+,.0f} 원")
        m3.metric("총 수익률", f"{yield_rate:.2f} %", f"{yield_rate:.2f} %")
        st.divider()
        
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1: st.plotly_chart(create_pie(all_df, '종목명', "1. 종목별 비중"), use_container_width=True, key='t1_c1')
        with r1_c2: st.plotly_chart(create_pie(all_df, '업종', "2. 업종(섹터)별 비중"), use_container_width=True, key='t1_c2')
        r2_c1, r2_c2 = st.columns(2)
        with r2_c1: st.plotly_chart(create_pie(all_df, '국가', "3. 국가별 비중"), use_container_width=True, key='t1_c3')
        with r2_c2: st.plotly_chart(create_pie(all_df, '유형', "4. 자산 유형별 비중"), use_container_width=True, key='t1_c4')

        st.divider()
        st.subheader("📋 전체 자산 상세")
        summary_cols = ['계좌명', '종목명', '업종', '국가', '수량', '매수단가', '현재가', '수익률', '평가금액']
        st.dataframe(
            all_df[summary_cols].style.format({
                '수량': '{:,.2f}', '매수단가': '{:,.0f}', '현재가': '{:,.0f}', '수익률': '{:+.2f}%', '평가금액': '{:,.0f}'
            }).map(color_profit, subset=['수익률']),
            use_container_width=True, hide_index=True
        )

    # --- [TAB 2] 계좌별 상세 ---
    with tab2:
        sheet_names = list(portfolio_dict.keys())
        selected_sheet = st.selectbox("계좌 선택:", sheet_names)
        target_df = portfolio_dict[selected_sheet]
        
        t_eval = target_df['평가금액'].sum()
        t_profit = t_eval - target_df['매수금액'].sum()
        
        m1, m2 = st.columns(2)
        m1.metric("계좌 평가금액", f"{t_eval:,.0f} 원", f"{t_profit:+,.0f} 원")
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(create_pie(target_df, '종목명', "1. 종목 비중"), use_container_width=True, key='t2_c1')
        with c2: st.plotly_chart(create_pie(target_df, '유형', "2. 유형 비중"), use_container_width=True, key='t2_c2')
        
        st.caption(f"📋 {selected_sheet} 보유 종목")
        st.dataframe(
            target_df[['종목명', '업종', '수량', '매수단가', '현재가', '수익률', '평가금액']].style.format({
                '수량': '{:,.2f}', '매수단가': '{:,.0f}', '현재가': '{:,.0f}', '수익률': '{:+.2f}%', '평가금액': '{:,.0f}'
            }).map(color_profit, subset=['수익률']),
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

        with st.expander("➕ 종목 추가하기 (이름으로 검색 가능)"):
            ac1, ac2 = st.columns([3, 1])
            input_val = ac1.text_input("종목명 또는 코드 입력 (예: 삼성전자, TSLA, 금)")
            if ac2.button("검색"):
                info = get_stock_info_safe(input_val)
                if info: st.session_state['search_info'] = info
                else: st.error("종목을 찾을 수 없습니다.")
            
            if st.session_state['search_info']:
                inf = st.session_state['search_info']
                st.success(f"검색 성공: **{inf['종목명']}** ({inf['종목코드']})")
                st.write(f"현재가: {inf['현재가']:,.0f}원")
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
        
        sim_df.update(edited)
        
        def calc_sim_total(row):
            p, q = row['현재가'], row['시뮬레이션 수량']
            if row['통화'] == 'USD' or row['국가'] == '미국':
                return p * q * usd_krw
            return p * q
        
        sim_df['예상 평가금액'] = sim_df.apply(calc_sim_total, axis=1)
        sim_df['수량변동'] = sim_df['시뮬레이션 수량'] - sim_df['수량']
        def calc_diff_amt(row):
            p = row['현재가']
            q_diff = row['수량변동']
            if row['통화'] == 'USD' or row['국가'] == '미국':
                return p * q_diff * usd_krw
            return p * q_diff

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
        st.dataframe(all_df)

else:
    st.info("👆 엑셀 파일을 업로드해주세요.")
