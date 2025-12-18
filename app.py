import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import io

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 세션 초기화
# -----------------------------------------------------------------------------
st.set_page_config(page_title="My Portfolio Simulator", layout="wide", page_icon="📈")

if 'sim_data' not in st.session_state:
    st.session_state['sim_data'] = None

st.title("📈 포트폴리오 시뮬레이터 v3.5")
st.markdown("시뮬레이션 기능추가, 검색기능 추가.")

# -----------------------------------------------------------------------------
# 2. 유틸리티 함수
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def get_exchange_rate():
    try:
        return yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 1450.0

def get_current_price(ticker):
    try:
        return yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except:
        return 0.0

def get_stock_info(ticker):
    try:
        t = yf.Ticker(ticker)
        history = t.history(period='1d')
        if history.empty: return None
        info = t.info
        return {
            '종목코드': ticker,
            '종목명': info.get('shortName', ticker),
            '업종': info.get('sector', '기타'),
            '국가': '한국' if ticker.endswith('.KS') or ticker.endswith('.KQ') else '미국',
            '유형': 'ETF' if info.get('quoteType') == 'ETF' else '개별주식',
            '현재가': history['Close'].iloc[-1],
            'currency': 'KRW' if ticker.endswith('.KS') or ticker.endswith('.KQ') else 'USD'
        }
    except:
        return None

def classify_asset_type_initial(row):
    name = str(row.get('종목명', '')).upper()
    ticker = str(row.get('종목코드', '')).upper()
    if ticker in ['KRW', 'USD'] or '예수금' in name: return '현금'
    etf_keywords = ['ETF', 'ETN', 'KODEX', 'TIGER', 'ACE', 'SOL', 'SPLG', 'IAU', 'QQQ', 'SPY', 'TLT', 'JEPI', 'SCHD']
    if any(k in name for k in etf_keywords) or any(k in ticker for k in etf_keywords): return 'ETF'
    return '개별주식'

def create_pie(data, names, title):
    if data.empty: return None
    fig = px.pie(data, values='평가금액', names=names, title=title, hole=0.4)
    fig.update_layout(margin=dict(t=30, b=0, l=0, r=0))
    return fig

def color_profit(val):
    if val > 0: return 'color: #ff2b2b'
    elif val < 0: return 'color: #00498c'
    return 'color: black'

# -----------------------------------------------------------------------------
# 3. 엑셀 다운로드
# -----------------------------------------------------------------------------
def get_template_excel():
    data = {
        '종목코드': ['000660.KS', 'IAU', 'SPLG', 'KRW', 'USD', '267260.KS'],
        '종목명': ['SK하이닉스', 'iShares Gold', 'S&P 500', '원화예수금', '달러예수금', 'HD현대일렉트릭'],
        '업종': ['반도체', '원자재', '지수추종', '현금', '현금', '전력설비'],
        '국가': ['한국', '미국', '미국', '한국', '미국', '한국'],
        '수량': [10, 20, 15, 1000000, 500, 7],
        '매수단가': [180000, 53.50, 68.20, 1, 1, 860000]
    }
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='포트폴리오')
    return output.getvalue()

with st.expander("⬇️ 엑셀 양식 다운로드"):
    st.download_button(label="엑셀 양식 받기 (.xlsx)", data=get_template_excel(), file_name='portfolio.xlsx')

# -----------------------------------------------------------------------------
# 4. 메인 로직
# -----------------------------------------------------------------------------
uploaded_file = st.file_uploader("📂 엑셀 파일을 업로드하세요 (초기화하려면 새로고침)", type=['xlsx'])

if uploaded_file is not None:
    # 1) 최초 데이터 로드
    if st.session_state['sim_data'] is None:
        try:
            df = pd.read_excel(uploaded_file)
            usd_krw = get_exchange_rate()
            
            # 초기 계산
            current_prices, eval_values, buy_values, currencies = [], [], [], []
            with st.spinner('데이터 분석 중...'):
                for index, row in df.iterrows():
                    ticker = str(row['종목코드']).upper().strip()
                    currency = 'KRW'
                    # 가격 로직
                    if ticker == 'KRW':
                        price, eval_val, buy_val = 1.0, row['수량'], row['수량'] * row['매수단가']
                    elif ticker == 'USD':
                        price, currency = usd_krw, 'USD'
                        eval_val = row['수량'] * usd_krw
                        buy_val = (row['매수단가'] * row['수량'] * usd_krw) if row['매수단가'] < 50 else (row['매수단가'] * row['수량'])
                    else:
                        price = get_current_price(ticker)
                        if row['국가'] == '미국':
                            eval_val, buy_val, currency = price * row['수량'] * usd_krw, row['매수단가'] * row['수량'] * usd_krw, 'USD'
                        else:
                            eval_val, buy_val = price * row['수량'], row['매수단가'] * row['수량']
                    
                    current_prices.append(price)
                    eval_values.append(eval_val)
                    buy_values.append(buy_val)
                    currencies.append(currency)

            df['현재가'] = current_prices
            df['매수금액'] = buy_values
            df['평가금액'] = eval_values
            df['수익률'] = df.apply(lambda x: ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100) if x['매수금액'] > 0 else 0, axis=1)
            df['유형'] = df.apply(classify_asset_type_initial, axis=1)
            df['통화'] = currencies
            df['시뮬레이션 수량'] = df['수량']
            
            st.session_state['sim_data'] = df
            st.session_state['usd_krw'] = usd_krw
            
        except Exception as e:
            st.error(f"오류: {e}")
            st.stop()

    # 세션 데이터 가져오기
    df_dashboard = st.session_state['sim_data']
    usd_krw = st.session_state['usd_krw']

    tab1, tab2, tab3 = st.tabs(["📊 대시보드", "🎛️ 시뮬레이션 (자유편집)", "📝 원본 데이터"])

    # --- [TAB 1] 대시보드 ---
    with tab1:
        total_eval = df_dashboard['평가금액'].sum()
        total_buy = df_dashboard['매수금액'].sum()
        profit = total_eval - total_buy
        yield_rate = (profit / total_buy * 100) if total_buy > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("총 매수금액", f"{total_buy:,.0f} 원")
        m2.metric("총 평가금액", f"{total_eval:,.0f} 원", f"{profit:+,.0f} 원")
        m3.metric("총 수익률", f"{yield_rate:.2f} %", f"{yield_rate:.2f} %")
        
        st.divider()
        st.subheader("📈 포트폴리오 구성")
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        with r1c1: st.plotly_chart(create_pie(df_dashboard, '종목명', "1. 종목별"), use_container_width=True, key='d1')
        with r1c2: st.plotly_chart(create_pie(df_dashboard, '업종', "2. 업종별"), use_container_width=True, key='d2')
        with r2c1: st.plotly_chart(create_pie(df_dashboard, '국가', "3. 국가별"), use_container_width=True, key='d3')
        with r2c2: st.plotly_chart(create_pie(df_dashboard, '유형', "4. 유형별"), use_container_width=True, key='d4')

        st.divider()
        st.subheader("📋 자산 상세")
        display_df = df_dashboard[['종목명', '유형', '수량', '매수단가', '현재가', '수익률', '평가금액']].copy()
        styled_df = display_df.style.format({
            '수량': '{:,.2f}', '매수단가': '{:,.0f}', '현재가': '{:,.0f}', '수익률': '{:+.2f}%', '평가금액': '{:,.0f}'
        }).map(color_profit, subset=['수익률'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True, column_config={"평가금액": st.column_config.NumberColumn("평가금액 (KRW)")})

    # --- [TAB 2] 시뮬레이터 (자유 편집) ---
    with tab2:
        st.header("🛠️ 리밸런싱 워크스페이스")
        st.info("💡 **행 삭제:** 표에서 행을 선택(체크)하고 `Delete` 키를 누르거나 휴지통 아이콘을 클릭하세요.\n💡 **행 수정:** 수량, 가격 등 모든 셀을 자유롭게 더블클릭하여 수정할 수 있습니다.")

        with st.expander("➕ 종목 검색해서 추가하기", expanded=False):
            c_add1, c_add2 = st.columns([3, 1])
            new_ticker = c_add1.text_input("티커 (예: TSLA, 005930.KS)", key='add_input')
            if c_add2.button("추가"):
                if new_ticker:
                    info = get_stock_info(new_ticker.strip().upper())
                    if info:
                        new_row = {
                            '종목코드': info['종목코드'], '종목명': info['종목명'], '업종': info['업종'],
                            '국가': info['국가'], '유형': info['유형'], '수량': 0, '매수단가': 0,
                            '현재가': info['현재가'], '매수금액': 0, '평가금액': 0, '수익률': 0,
                            '통화': info['currency'], '시뮬레이션 수량': 0
                        }
                        st.session_state['sim_data'] = pd.concat([st.session_state['sim_data'], pd.DataFrame([new_row])], ignore_index=True)
                        st.rerun()
                    else: st.error("종목 정보를 찾을 수 없습니다.")

        st.divider()

        # Data Editor
        sim_data_source = st.session_state['sim_data'].copy()
        sim_view_cols = ['종목코드', '종목명', '유형', '통화', '현재가', '시뮬레이션 수량']
        
        edited_df = st.data_editor(
            sim_data_source[sim_view_cols],
            column_config={
                "종목코드": st.column_config.TextColumn("코드", disabled=True),
                "종목명": st.column_config.TextColumn("종목명 (수정가능)"),
                "현재가": st.column_config.NumberColumn("예상 단가 (수정가능)", format="%d"),
                "시뮬레이션 수량": st.column_config.NumberColumn("목표 수량", format="%.2f", min_value=0, step=1),
                "통화": st.column_config.SelectboxColumn("통화", options=['KRW', 'USD'], width='small')
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key='editor'
        )

        # ---------------------------------------------------------------------
        # [수정됨] 재계산 로직: 달러 현금 중복 계산 방지
        # ---------------------------------------------------------------------
        sim_result_df = edited_df.copy()

        def calc_sim_eval(row):
            price = float(row.get('현재가', 0))
            qty = float(row.get('시뮬레이션 수량', 0))
            code = str(row.get('종목코드', '')).upper()
            currency = row.get('통화', 'KRW')
            
            # [버그 수정] 종목코드가 USD(달러현금)인 경우, 이미 price가 환율이므로 또 환율을 곱하면 안됨
            if code == 'USD':
                return price * qty
            
            # 일반 미국 주식인 경우 환율 곱하기
            if currency == 'USD':
                return price * qty * usd_krw
            
            return price * qty

        sim_result_df['예상 평가금액'] = sim_result_df.apply(calc_sim_eval, axis=1)

        # 메타데이터 복원
        meta_lookup = st.session_state['sim_data'].set_index('종목코드')[['업종', '국가']].to_dict('index')
        
        def get_meta(row, col):
            code = row.get('종목코드')
            if code in meta_lookup:
                return meta_lookup[code].get(col, '기타')
            return '기타'

        sim_result_df['업종'] = sim_result_df.apply(lambda x: get_meta(x, '업종'), axis=1)
        sim_result_df['국가'] = sim_result_df.apply(lambda x: get_meta(x, '국가'), axis=1)
        
        if '유형' not in sim_result_df.columns:
             sim_result_df['유형'] = sim_result_df.apply(classify_asset_type_initial, axis=1)

        sim_total = sim_result_df['예상 평가금액'].sum()
        diff = total_eval - sim_total
        
        st.divider()
        c_budget, c_chart = st.columns([1, 2])
        
        with c_budget:
            st.markdown("### 💰 예산 체크")
            st.metric("현재 총 자산 (한도)", f"{total_eval:,.0f} 원")
            st.metric("시뮬레이션 총액", f"{sim_total:,.0f} 원")
            if diff >= 0: st.success(f"✅ {diff:,.0f} 원 남음")
            else: st.error(f"🚨 {abs(diff):,.0f} 원 부족")

        with c_chart:
            st.markdown("### 🔮 리밸런싱 결과")
            if not sim_result_df.empty:
                t1, t2 = st.tabs(["차트 보기", "데이터 보기"])
                with t1:
                    sc1, sc2 = st.columns(2)
                    sc3, sc4 = st.columns(2)
                    with sc1: st.plotly_chart(create_pie(sim_result_df, '종목명', "1. 종목"), use_container_width=True, key='s1')
                    with sc2: st.plotly_chart(create_pie(sim_result_df, '업종', "2. 업종"), use_container_width=True, key='s2')
                    with sc3: st.plotly_chart(create_pie(sim_result_df, '국가', "3. 국가"), use_container_width=True, key='s3')
                    with sc4: st.plotly_chart(create_pie(sim_result_df, '유형', "4. 유형"), use_container_width=True, key='s4')
                with t2:
                    st.dataframe(
                        sim_result_df[['종목명', '시뮬레이션 수량', '예상 평가금액']].style.format({
                            '시뮬레이션 수량': '{:,.2f}',
                            '예상 평가금액': '{:,.0f}'
                        }), 
                        use_container_width=True, 
                        hide_index=True
                    )
            else:
                st.warning("데이터가 없습니다. 종목을 추가해주세요.")

    # --- [TAB 3] 원본 데이터 ---
    with tab3:
        st.dataframe(df_dashboard)

else:
    st.info("👆 엑셀 파일을 업로드하면 시작됩니다.")
