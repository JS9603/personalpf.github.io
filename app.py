Python 3.12.3 (tags/v3.12.3:f6650f9, Apr  9 2024, 14:05:25) [MSC v.1938 64 bit (AMD64)] on win32
Type "help", "copyright", "credits" or "license()" for more information.
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
# 사용자가 입력한 데이터를 브라우저에 임시 저장하기 위한 초기 설정입니다.
if 'portfolio_df' not in st.session_state:
    # 초기 예시 데이터 (고객님의 현재 상황 반영)
    initial_data = {
        '종목코드': ['000660.KS', '267250.KS', '373220.KS', 'IAU', 'SPLG'],
        '종목명': ['SK하이닉스', 'HD현대일렉트릭', 'KODEX 골드선물(H)', 'iShares Gold Trust', 'SPDR S&P 500'],
        '업종': ['반도체', '전력인프라', '원자재(금)', '원자재(금)', '지수추종'],
        '국가': ['한국', '한국', '한국', '미국', '미국'],
        '수량': [2, 7, 50, 20, 15],
        '매수단가': [180000, 300000, 24000, 50.0, 65.0] # 한국은 원, 미국은 달러 기준
    }
    st.session_state.portfolio_df = pd.DataFrame(initial_data)

# -----------------------------------------------------------------------------
# 3. 데이터 수집 함수 (Yahoo Finance API)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60) # 60초마다 데이터 갱신 (API 호출 제한 방지)
def get_market_data():
    # 환율 정보 가져오기
    try:
        exchange_rate = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
    except:
        exchange_rate = 1450.0 # 에러 발생 시 기본값

    return exchange_rate

def get_current_price(ticker):
    try:
        # 야후 파이낸스에서 현재가 가져오기
        stock = yf.Ticker(ticker)
        price = stock.history(period="1d")['Close'].iloc[-1]
        return price
    except:
        return 0.0

# -----------------------------------------------------------------------------
# 4. 탭 구성 (요약 vs 입력)
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
        
        # 실시간 가격 및 평가금액 계산
        current_prices = []
        current_values_krw = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for index, row in df.iterrows():
            status_text.text(f"⏳ 가격 조회 중: {row['종목명']}...")
            ticker = row['종목코드']
            price = get_current_price(ticker)
            current_prices.append(price)
            
            # 평가금액 계산 (미국 주식은 환율 적용)
            if row['국가'] == '미국':
                val_krw = price * row['수량'] * usd_krw
            else:
                val_krw = price * row['수량']
            current_values_krw.append(val_krw)
            progress_bar.progress((index + 1) / len(df))
            
        status_text.empty()
        progress_bar.empty()
        
        df['현재가'] = current_prices
        df['평가금액(KRW)'] = current_values_krw
        df['수익률(%)'] = ((df['현재가'] - df['매수단가']) / df['매수단가']) * 100
        
        # 총 자산 표시
        total_asset = df['평가금액(KRW)'].sum()
        st.info(f"💰 **총 자산 평가액:** {total_asset:,.0f} 원")

        # C. 3분할 원형 그래프
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

        # 상세 테이블
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
... # [Tab 2] 포트폴리오 입력
... # =============================================================================
... with tab2:
...     st.header("📝 포트폴리오 수정 및 입력")
...     st.markdown("""
...     > **💡 입력 가이드**
...     > * **종목코드**: 한국 주식은 끝에 `.KS`(코스피) 또는 `.KQ`(코스닥)를 붙여주세요. (예: `000660.KS`)
...     > * **미국 주식**: 티커 그대로 입력하세요. (예: `NVDA`, `IAU`)
...     > * **매수단가**: 한국 주식은 '원', 미국 주식은 '달러($)' 기준으로 입력하세요.
...     """)
... 
...     # 데이터 에디터 (엑셀처럼 편집 가능)
...     edited_df = st.data_editor(
...         st.session_state.portfolio_df,
...         num_rows="dynamic", # 행 추가/삭제 가능
...         column_config={
...             "종목코드": st.column_config.TextColumn("종목코드 (필수)", required=True),
...             "종목명": st.column_config.TextColumn("종목명", required=True),
...             "업종": st.column_config.SelectboxColumn(
...                 "업종",
...                 options=["반도체", "전력인프라", "AI/SW", "원자재(금)", "방산", "지수추종", "헬스케어", "현금", "기타"],
...                 required=True
...             ),
...             "국가": st.column_config.SelectboxColumn("국가", options=["한국", "미국"], required=True),
...             "수량": st.column_config.NumberColumn("수량", min_value=0, step=1),
...             "매수단가": st.column_config.NumberColumn("매수단가 (현지통화)", min_value=0, format="%.2f"),
...         },
...         use_container_width=True
...     )
... 
...     if st.button("💾 저장하고 요약 탭에서 확인하기", type="primary"):
...         st.session_state.portfolio_df = edited_df
...         st.toast("포트폴리오가 성공적으로 업데이트되었습니다!", icon="✅")
