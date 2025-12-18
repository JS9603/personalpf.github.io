import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import io

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 세션 상태 초기화
# -----------------------------------------------------------------------------
st.set_page_config(page_title="My Portfolio Simulator", layout="wide", page_icon="📈")

if 'sim_data' not in st.session_state:
    st.session_state['sim_data'] = None

st.title("📈 포트폴리오 시뮬레이터 v3.0")
st.markdown("시뮬레이션 개선, 비교분석 기능추가.")

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
    """티커로 종목 정보 가져오기 (종목 추가용)"""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        history = t.history(period='1d')
        
        if history.empty:
            return None
            
        current_price = history['Close'].iloc[-1]
        name = info.get('shortName', ticker)
        sector = info.get('sector', '기타')
        
        # 국가 추정
        if ticker.endswith('.KS') or ticker.endswith('.KQ'):
            country = '한국'
            currency = 'KRW'
        else:
            country = '미국' # 편의상 미국으로 가정
            currency = 'USD'
            
        # 자산 유형 추정
        etype = '개별주식'
        if info.get('quoteType') == 'ETF':
            etype = 'ETF'
            
        return {
            '종목코드': ticker,
            '종목명': name,
            '업종': sector,
            '국가': country,
            '유형': etype,
            '현재가': current_price,
            'currency': currency
        }
    except:
        return None

def classify_asset_type_initial(row):
    """엑셀 로드 시 초기 분류"""
    name = str(row['종목명']).upper()
    ticker = str(row['종목코드']).upper()
    
    if ticker in ['KRW', 'USD'] or '예수금' in name:
        return '현금'
    
    etf_keywords = ['ETF', 'ETN', 'KODEX', 'TIGER', 'ACE', 'SOL', 'KBSTAR', 'HANARO', 
                    'ISHARES', 'SPDR', 'VANGUARD', 'QQQ', 'SPY', 'SPLG', 'IAU', 'GLD', 'TLT', 'SHV', 'JEPI', 'SCHD']
    
    if any(k in name for k in etf_keywords) or any(k in ticker for k in etf_keywords):
        return 'ETF'
    return '개별주식'

def create_pie(data, names, title):
    # 색상 팔레트 개선 (Plotly Qualitative Colors)
    fig = px.pie(data, values='평가금액', names=names, title=title, hole=0.4, 
                 color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), showlegend=False)
    return fig

# -----------------------------------------------------------------------------
# 3. 엑셀 양식 다운로드
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
    st.download_button(label="엑셀 양식 받기 (.xlsx)", data=get_template_excel(), file_name='portfolio_template.xlsx')

# -----------------------------------------------------------------------------
# 4. 메인 로직
# -----------------------------------------------------------------------------
uploaded_file = st.file_uploader("📂 엑셀 파일을 업로드하세요 (초기화하려면 새로고침)", type=['xlsx'])

if uploaded_file is not None:
    # 1) 최초 로드 시에만 데이터 처리 및 세션 저장
    if st.session_state['sim_data'] is None:
        try:
            df = pd.read_excel(uploaded_file)
            usd_krw = get_exchange_rate()
            
            # 초기 데이터 계산
            current_prices = []
            eval_values = []
            buy_values = []
            currencies = []

            with st.spinner('초기 데이터 분석 중...'):
                for index, row in df.iterrows():
                    ticker = str(row['종목코드']).upper().strip()
                    currency = 'KRW'
                    
                    if ticker == 'KRW':
                        price = 1.0
                        eval_val = row['수량']
                        buy_val = row['수량'] * row['매수단가']
                    elif ticker == 'USD':
                        price = usd_krw
                        eval_val = row['수량'] * usd_krw
                        buy_val = (row['매수단가'] * row['수량'] * usd_krw) if row['매수단가'] < 50 else (row['매수단가'] * row['수량'])
                        currency = 'USD'
                    else:
                        price = get_current_price(ticker)
                        if row['국가'] == '미국':
                            eval_val = price * row['수량'] * usd_krw
                            buy_val = row['매수단가'] * row['수량'] * usd_krw
                            currency = 'USD'
                        else:
                            eval_val = price * row['수량']
                            buy_val = row['매수단가'] * row['수량']
                    
                    current_prices.append(price)
                    eval_values.append(eval_val)
                    buy_values.append(buy_val)
                    currencies.append(currency)

            df['현재가'] = current_prices
            df['매수금액'] = buy_values
            df['평가금액'] = eval_values
            df['수익률'] = df.apply(lambda x: ((x['평가금액'] - x['매수금액']) / x['매수금액']) if x['매수금액'] > 0 else 0, axis=1)
            df['유형'] = df.apply(classify_asset_type_initial, axis=1)
            df['통화'] = currencies
            
            # 시뮬레이션용 컬럼 추가 (초기값 = 현재 수량)
            df['시뮬레이션 수량'] = df['수량']
            
            st.session_state['sim_data'] = df
            st.session_state['usd_krw'] = usd_krw # 환율 고정
            
        except Exception as e:
            st.error(f"파일 읽기 오류: {e}")
            st.stop()

    # 세션에서 데이터 가져오기
    df = st.session_state['sim_data']
    usd_krw = st.session_state['usd_krw']

    # ---------------------------------------------------------------------
    # 5. 탭 구성
    # ---------------------------------------------------------------------
    tab1, tab2 = st.tabs(["📊 현재 포트폴리오", "🎛️ 리밸런싱 시뮬레이터"])

    # --- [TAB 1] 대시보드 ---
    with tab1:
        total_eval = df['평가금액'].sum()
        total_buy = df['매수금액'].sum()
        profit = total_eval - total_buy
        yield_rate = (profit / total_buy * 100) if total_buy > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("총 매수금액", f"{total_buy:,.0f} 원")
        m2.metric("총 평가금액", f"{total_eval:,.0f} 원", f"{profit:+,.0f} 원")
        m3.metric("총 수익률", f"{yield_rate:.2f} %", f"{yield_rate:.2f} %")
        
        st.divider()
        st.subheader("📈 포트폴리오 구성 (4 View)")
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        
        with r1c1: st.plotly_chart(create_pie(df, '종목명', "1. 종목별 비중"), use_container_width=True, key='d1')
        with r1c2: st.plotly_chart(create_pie(df, '업종', "2. 업종별 비중"), use_container_width=True, key='d2')
        with r2c1: st.plotly_chart(create_pie(df, '국가', "3. 국가별 비중"), use_container_width=True, key='d3')
        with r2c2: st.plotly_chart(create_pie(df, '유형', "4. 유형별 비중"), use_container_width=True, key='d4')

    # --- [TAB 2] 시뮬레이터 ---
    with tab2:
        st.header("🛠️ 포트폴리오 리모델링")
        
        # [기능 1] 종목 추가
        with st.expander("➕ 새로운 종목 추가하기 (Ticker 검색)", expanded=False):
            c_add1, c_add2 = st.columns([3, 1])
            new_ticker = c_add1.text_input("티커 입력 (예: TSLA, AAPL, 005930.KS)", placeholder="미국주식 티커 or 한국주식 코드(.KS)")
            if c_add2.button("검색 및 추가"):
                if new_ticker:
                    with st.spinner("정보 가져오는 중..."):
                        info = get_stock_info(new_ticker.strip().upper())
                        if info:
                            # 기존 데이터프레임에 추가 (수량 0으로 시작)
                            new_row = {
                                '종목코드': info['종목코드'], '종목명': info['종목명'], '업종': info['업종'],
                                '국가': info['국가'], '유형': info['유형'], '수량': 0, '매수단가': 0,
                                '현재가': info['현재가'], '매수금액': 0, '평가금액': 0, '수익률': 0,
                                '통화': info['currency'], '시뮬레이션 수량': 0 # 초기 0
                            }
                            st.session_state['sim_data'] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                            st.rerun() # 새로고침해서 표에 반영
                        else:
                            st.error("종목을 찾을 수 없습니다. 티커를 확인해주세요.")

        st.divider()

        # 데이터 에디터 (시뮬레이션 수량 수정)
        # 편집 가능한 컬럼만 추려서 보여줌
        sim_view = st.session_state['sim_data'][['종목명', '현재가', '통화', '수량', '시뮬레이션 수량']].copy()
        
        edited_sim_view = st.data_editor(
            sim_view,
            column_config={
                "현재가": st.column_config.NumberColumn("현재가", format="%d", disabled=True),
                "통화": st.column_config.TextColumn("통화", width="small", disabled=True),
                "수량": st.column_config.NumberColumn("현재 수량", format="%.2f", disabled=True),
                "시뮬레이션 수량": st.column_config.NumberColumn("목표 수량 (수정)", format="%.2f", min_value=0, step=1)
            },
            use_container_width=True,
            hide_index=True,
            key='editor'
        )

        # 수정된 수량을 원본 세션 데이터에 반영 및 재계산
        # (주의: data_editor는 인덱스 순서대로 값을 뱉으므로 원본과 인덱스 매칭 필요)
        updated_df = st.session_state['sim_data'].copy()
        updated_df['시뮬레이션 수량'] = edited_sim_view['시뮬레이션 수량']
        
        # 환율 적용하여 예상 평가금액 계산
        def calc_sim_eval(row):
            price = row['현재가']
            qty = row['시뮬레이션 수량']
            if row['통화'] == 'USD' or row['종목코드'] == 'USD':
                return price * qty * usd_krw
            return price * qty

        updated_df['예상 평가금액'] = updated_df.apply(calc_sim_eval, axis=1)

        # [기능 3] 예산 부족 계산
        current_total_asset = total_eval # 현재 총 평가 자산 (내 돈의 한계)
        sim_total_asset = updated_df['예상 평가금액'].sum() # 내가 사고 싶은 것들의 총합
        
        diff = current_total_asset - sim_total_asset
        
        st.divider()
        
        # 예산 상태 표시
        col_res1, col_res2 = st.columns([1, 2])
        
        with col_res1:
            st.markdown("### 💰 예산 현황")
            st.write(f"현재 총 자산: **{current_total_asset:,.0f} 원**")
            st.write(f"시뮬레이션 총액: **{sim_total_asset:,.0f} 원**")
            
            if diff >= 0:
                st.success(f"✅ **{diff:,.0f} 원** 남음 (현금 확보 가능)")
            else:
                st.error(f"🚨 **{abs(diff):,.0f} 원** 부족합니다!")
                st.caption("보유 현금(KRW/USD) 수량을 줄이거나, 매수 목표를 낮추세요.")

        # [기능 2 & 4] 시뮬레이션 결과 4분할 차트 (색상 개선됨)
        with col_res2:
            st.markdown("### 🔮 리밸런싱 후 예상 포트폴리오")
            t1, t2 = st.tabs(["구성 차트", "상세 데이터"])
            
            with t1:
                sr1, sr2 = st.columns(2)
                sr3, sr4 = st.columns(2)
                # 시뮬레이션 데이터로 4개 차트 그리기
                with sr1: st.plotly_chart(create_pie(updated_df, '종목명', "1. 종목"), use_container_width=True, key='s1')
                with sr2: st.plotly_chart(create_pie(updated_df, '업종', "2. 업종"), use_container_width=True, key='s2')
                with sr3: st.plotly_chart(create_pie(updated_df, '국가', "3. 국가"), use_container_width=True, key='s3')
                with sr4: st.plotly_chart(create_pie(updated_df, '유형', "4. 유형"), use_container_width=True, key='s4')
            
            with t2:
                # 상세 데이터 표 (Compact)
                st.dataframe(
                    updated_df[['종목명', '시뮬레이션 수량', '예상 평가금액', '유형']],
                    column_config={
                        "예상 평가금액": st.column_config.NumberColumn(format="%d 원")
                    },
                    use_container_width=True,
                    hide_index=True
                )

else:
    st.info("👆 엑셀 파일을 업로드하면 시작됩니다.")
