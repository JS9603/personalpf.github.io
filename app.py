import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="My Portfolio Dashboard", layout="wide", page_icon="📈")

st.title("📈 내 손안의 포트폴리오 매니저")
st.markdown("반도체, AI, 인프라 등 핵심 자산 현황을 실시간으로 관리하세요.")

# -----------------------------------------------------------------------------
# 2. 데이터 관리 (세션 스테이트)
# -----------------------------------------------------------------------------
if 'portfolio_df' not in st.session_state:
    # 초기 예시 데이터
    initial_data = {
        '종목코드': ['000660.KS', '267250.KS', '373220.KS', 'IAU', 'SPLG'],
        '종목명': ['SK하이닉스', 'HD현대일렉트릭', 'KODEX 골드선물(H)', 'iShares Gold Trust', 'SPDR S&P 500'],
        '업종': ['반도체', '전력인프라', '원자재(금)', '원자재(금)', '지수추종'],
        '국가': ['한국', '한국', '한국', '미국', '미국'],
        '수량': [2, 7, 50, 20, 15],
        '매수단가': [180000, 300000, 24000, 50.0, 65.0]
    }
    st.session_state.portfolio_df = pd.DataFrame(initial_data)

# -----------------------------------------------------------------------------
# 3. 데이터 수집 함수
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def get_market_data():
    try:
        exchange_rate = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
    except:
        exchange_rate = 1450.0 
    return exchange_rate

def get_current_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.history(period="1d")['Close'].iloc[-1]
        return price
    except:
        return 0.0

# -----------------------------------------------------------------------------
# 4. 탭 구성
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["📊 요약 (Dashboard)", "📝 포트폴리오 입력 (Input)"])

# =============================================================================
# [Tab 1] 요약 대시보드
# =============================================================================
with tab1:
    # A. 실시간 환율 표시
    usd_krw = get_market_data()
    st.metric(label="🇺🇸/🇰🇷 실시간 원/달러 환율", value=f"{usd_krw:,.2f} 원")
    st.divider()

    # B. 포트폴리오 계산 로직
    if not st.session_state.portfolio_df.empty:
        df = st.session_state.portfolio_df.copy()
        
        # 로딩바 표시
        progress_text = "최신 주가 정보를 불러오는 중입니다..."
        my_bar = st.progress(0, text=progress_text)
        
        current_prices = []
        current_values_krw = []
        
        for index, row in df.iterrows():
            ticker = row['종목코드']
            price = get_current_price(ticker)
            current_prices.append(price)
            
            # 평가금액 계산
            if row['국가'] == '미국':
                val_krw = price * row['수량'] * usd_krw
            else:
                val_krw = price * row['수량']
            current_values_krw.append(val_krw)
            
            # 진행률 업데이트
            my_bar.progress((index + 1) / len(df), text=progress_text)
            
        my_bar.empty() # 로딩바 제거
        
        df['현재가'] = current_prices
        df['평가금액(KRW)'] = current_values_krw
        
        # 0으로 나누기 방지
        df['수익률(%)'] = df.apply(lambda x: ((x['현재가'] - x['매수단가']) / x['매수단가'] * 100) if x['매수단가'] > 0 else 0, axis=1)
        
        # 총 자산 표시
        total_asset = df['평가금액(KRW)'].sum()
        st.info(f"💰 **총 자산 평가액:** {total_asset:,.0f} 원")

        # C. 차트 영역
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("1. 업종별 비중")
            fig1 = px.pie(df, values='평가금액(KRW)', names='업종', hole=0.4)
            fig1.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            st.subheader("2. 종목별 비중")
            fig2 = px.pie(df, values='평가금액(KRW)', names='종목명', hole=0.4)
            fig2.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig2, use_container_width=True)

        with col3:
            st.subheader("3. 국가별 비중")
            fig3 = px.pie(df, values='평가금액(KRW)', names='국가', hole=0.4, 
                          color='국가', color_discrete_map={'한국':'#00498c', '미국':'#bd081c'})
            fig3.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig3, use_container_width=True)

        # D. 상세 테이블
        st.markdown("### 📋 상세 보유 현황")
        st.dataframe(
            df[['종목명', '국가', '수량', '매수단가', '현재가', '수익률(%)', '평가금액(KRW)']].style.format({
                '매수단가': "{:,.0f}",
                '현재가': "{:,.2f}",
                '수익률(%)': "{:,.2f}%",
                '평가금액(KRW)': "{:,.0f}"
            }),
            use_container_width=True
        )

    else:
        st.warning("데이터가 없습니다. 입력 탭에서 포트폴리오를 추가해주세요.")

# =============================================================================
# [Tab 2] 포트폴리오 입력
# =============================================================================
with tab2:
    st.header("📝 포트폴리오 수정 및 입력")
    st.markdown("아래 표를 더블 클릭하여 내용을 직접 수정하세요.")

    edited_df = st.data_editor(
        st.session_state.portfolio_df,
        num_rows="dynamic",
        column_config={
            "종목코드": st.column_config.TextColumn("종목코드", required=True),
            "종목명": st.column_config.TextColumn("종목명", required=True),
            "업종": st.column_config.SelectboxColumn("업종", options=["반도체", "전력인프라", "AI/SW", "원자재(금)", "방산", "지수추종", "헬스케어", "현금", "기타"], required=True),
            "국가": st.column_config.SelectboxColumn("국가", options=["한국", "미국"], required=True),
            "수량": st.column_config.NumberColumn("수량", min_value=0, step=1),
            "매수단가": st.column_config.NumberColumn("매수단가 (현지통화)", min_value=0, format="%.2f"),
        },
        use_container_width=True
    )

    if st.button("💾 저장하고 요약 탭에서 확인하기", type="primary"):
        st.session_state.portfolio_df = edited_df
        st.rerun()
