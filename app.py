import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import io

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="My Excel Portfolio", layout="wide", page_icon="📊")

st.title("📊 엑셀 포트폴리오 뷰어 v2.4 (Final)")
st.markdown("수익률 컬러 적용, 상세표 너비 꽉 채움, 차트 에러 수정 완료 버전입니다.")

# -----------------------------------------------------------------------------
# 2. 엑셀 양식 다운로드
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
    st.download_button(
        label="엑셀 양식 받기 (.xlsx)",
        data=get_template_excel(),
        file_name='my_portfolio_template.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# -----------------------------------------------------------------------------
# 3. 데이터 처리 및 유틸리티 함수
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

def classify_asset_type(row):
    name = str(row['종목명']).upper()
    ticker = str(row['종목코드']).upper()
    
    if ticker in ['KRW', 'USD'] or '예수금' in name:
        return '현금'
    
    etf_keywords = [
        'ETF', 'ETN', 'KODEX', 'TIGER', 'ACE', 'SOL', 'KBSTAR', 'HANARO', 'KOSEF', 'ARIRANG',
        'ISHARES', 'SPDR', 'VANGUARD', 'INVESCO', 'PROSHARES',
        'QQQ', 'SPY', 'SPLG', 'IAU', 'GLD', 'TLT', 'SHV', 'SOXL', 'TQQQ', 'JEPI', 'SCHD'
    ]
    
    if any(keyword in name for keyword in etf_keywords) or any(keyword in ticker for keyword in etf_keywords):
        return 'ETF'
    return '개별주식'

def create_pie(data, names, title):
    fig = px.pie(data, values='평가금액', names=names, title=title, hole=0.4)
    fig.update_layout(margin=dict(t=30, b=0, l=0, r=0))
    return fig

# [수익률 색상 함수]
def color_profit(val):
    if val > 0:
        return 'color: #ff2b2b' # 빨강 (이익)
    elif val < 0:
        return 'color: #00498c' # 파랑 (손실)
    return 'color: black'

# -----------------------------------------------------------------------------
# 4. 메인 로직
# -----------------------------------------------------------------------------
uploaded_file = st.file_uploader("📂 엑셀 파일을 업로드하세요", type=['xlsx'])

if uploaded_file is not None:
    try:
        # 1) 데이터 로드 및 계산
        df = pd.read_excel(uploaded_file)
        usd_krw = get_exchange_rate()
        
        current_prices = []
        eval_values = []
        buy_values = []
        
        with st.spinner('자산 가치 평가 중...'):
            for index, row in df.iterrows():
                ticker = str(row['종목코드']).upper().strip()
                
                if ticker == 'KRW':
                    price = 1.0
                    eval_val = row['수량']
                    buy_val = row['수량'] * row['매수단가']
                elif ticker == 'USD':
                    price = usd_krw
                    eval_val = row['수량'] * usd_krw
                    buy_val = (row['매수단가'] * row['수량'] * usd_krw) if row['매수단가'] < 50 else (row['매수단가'] * row['수량'])
                else:
                    price = get_current_price(ticker)
                    if row['국가'] == '미국':
                        eval_val = price * row['수량'] * usd_krw
                        buy_val = row['매수단가'] * row['수량'] * usd_krw
                    else:
                        eval_val = price * row['수량']
                        buy_val = row['매수단가'] * row['수량']
                
                current_prices.append(price)
                eval_values.append(eval_val)
                buy_values.append(buy_val)

        df['현재가'] = current_prices
        df['매수금액'] = buy_values
        df['평가금액'] = eval_values
        df['수익률'] = df.apply(lambda x: ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100) if x['매수금액'] > 0 else 0, axis=1)
        df['유형'] = df.apply(classify_asset_type, axis=1)

        # ---------------------------------------------------------------------
        # 5. 탭 구성
        # ---------------------------------------------------------------------
        tab1, tab2, tab3 = st.tabs(["📊 대시보드", "🎛️ 시뮬레이션", "📝 원본 데이터"])

        # --- [TAB 1] 대시보드 ---
        with tab1:
            total_eval = df['평가금액'].sum()
            total_buy = df['매수금액'].sum()
            total_profit = total_eval - total_buy
            total_yield = (total_profit / total_buy * 100) if total_buy > 0 else 0
            
            st.caption(f"기준 환율: 1 USD = {usd_krw:,.2f} KRW")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("총 매수금액", f"{total_buy:,.0f} 원")
            m2.metric("총 평가금액", f"{total_eval:,.0f} 원", f"{total_profit:+,.0f} 원")
            m3.metric("총 수익률", f"{total_yield:,.2f} %", f"{total_yield:,.2f} %")
            
            st.divider()

            st.subheader("📈 포트폴리오 구성 (4 View)")
            row1_col1, row1_col2 = st.columns(2)
            row2_col1, row2_col2 = st.columns(2)
            
            with row1_col1:
                st.plotly_chart(create_pie(df, '종목명', "1. 종목별 비중"), use_container_width=True, key="chart_item")
            with row1_col2:
                st.plotly_chart(create_pie(df, '업종', "2. 업종별 비중"), use_container_width=True, key="chart_sector")
            with row2_col1:
                st.plotly_chart(create_pie(df, '국가', "3. 국가별 비중"), use_container_width=True, key="chart_country")
            with row2_col2:
                st.plotly_chart(create_pie(df, '유형', "4. 자산유형 비중"), use_container_width=True, key="chart_type")

            st.divider()

            st.subheader("📋 자산 상세")
            display_df = df[['종목명', '유형', '수량', '매수단가', '현재가', '수익률', '평가금액']].copy()

            # [스타일링 적용] 색상 + 포맷팅
            styled_df = display_df.style\
                .format({
                    '수량': '{:,.2f}', 
                    '매수단가': '{:,.0f}',
                    '현재가': '{:,.0f}',
                    '수익률': '{:+.2f}%',  # + 부호 추가
                    '평가금액': '{:,.0f}'
                })\
                .map(color_profit, subset=['수익률']) # 수익률 컬럼에 색상 적용

            # [화면 꽉 채움] use_container_width=True 유지
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "평가금액": st.column_config.NumberColumn("평가금액 (KRW)"), # 헤더 이름만 변경
                }
            )

        # --- [TAB 2] 시뮬레이션 ---
        with tab2:
            st.header("🎛️ 리밸런싱 시뮬레이터")
            
            sim_df = df[['종목명', '유형', '현재가', '수량', '평가금액']].copy()
            sim_df.rename(columns={'수량': '현재 수량'}, inplace=True)
            
            # 시뮬레이터도 화면 꽉 채움
            edited_df = st.data_editor(
                sim_df,
                column_config={
                    "현재가": st.column_config.NumberColumn("현재가", format="%d 원", disabled=True),
                    "현재 수량": st.column_config.NumberColumn("보유 수량", format="%.2f", disabled=True),
                    "평가금액": st.column_config.NumberColumn("현재 평가액", format="%d 원", disabled=True),
                    "시뮬레이션 수량": st.column_config.NumberColumn("목표 수량 (수정)", format="%.2f", min_value=0, step=1),
                },
                disabled=["종목명", "유형", "현재가", "현재 수량", "평가금액"],
                use_container_width=True,
                hide_index=True
            )

            if '시뮬레이션 수량' not in edited_df.columns:
                 edited_df['시뮬레이션 수량'] = edited_df['현재 수량']

            edited_df['예상 평가금액'] = edited_df['시뮬레이션 수량'] * edited_df['현재가']
            new_total = edited_df['예상 평가금액'].sum()
            
            st.divider()
            
            col_sim1, col_sim2 = st.columns(2)
            with col_sim1:
                st.markdown("**📉 현재 유형별 비중**")
                st.plotly_chart(create_pie(sim_df, '유형', ''), use_container_width=True, key="sim_before")
            with col_sim2:
                st.markdown("**📈 시뮬레이션 후 유형별 비중**")
                st.plotly_chart(create_pie(edited_df, '유형', ''), use_container_width=True, key="sim_after")
            
            st.success(f"💰 시뮬레이션 총 자산: **{new_total:,.0f} 원**")

        with tab3:
            st.dataframe(df)

    except Exception as e:
        st.error(f"오류 발생: {e}")
