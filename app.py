import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="My Portfolio Dashboard", layout="wide", page_icon="📈")

st.title("📈 내 손안의 포트폴리오 매니저")
st.markdown("미국 주식은 달러($)로 입력하면 실시간 환율을 적용해 원화로 계산합니다.")

# -----------------------------------------------------------------------------
# 2. 데이터 관리 (세션 스테이트)
# -----------------------------------------------------------------------------

# 2-1. 업종 목록 관리 (사용자가 추가 가능하도록)
if 'industry_options' not in st.session_state:
    st.session_state.industry_options = [
        "반도체", "전력인프라", "AI/SW", "원자재(금)", 
        "방산", "지수추종", "헬스케어", "현금", "기타"
    ]

# 2-2. 포트폴리오 데이터 관리
if 'portfolio_df' not in st.session_state:
    initial_data = {
        '종목코드': ['000660.KS', '267250.KS', '373220.KS', 'IAU', 'SPLG'],
        '종목명': ['SK하이닉스', 'HD현대일렉트릭', 'KODEX 골드선물(H)', 'iShares Gold Trust', 'SPDR S&P 500'],
        '업종': ['반도체', '전력인프라', '원자재(금)', '원자재(금)', '지수추종'],
        '국가': ['한국', '한국', '한국', '미국', '미국'],
        '수량': [2, 7, 50, 20, 15],
        '매수단가': [180000, 300000, 24000, 53.50, 68.20]
    }
    st.session_state.portfolio_df = pd.DataFrame(initial_data)

# -----------------------------------------------------------------------------
# 3. 데이터 수집 함수
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def get_exchange_rate():
    try:
        rate = yf.Ticker("KRW=X").history(period="1d")['Close'].iloc[-1]
        return rate
    except:
        return 1450.0

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
    usd_krw = get_exchange_rate()
    st.metric(label="🇺🇸/🇰🇷 실시간 원/달러 환율", value=f"{usd_krw:,.2f} 원")
    st.divider()

    if not st.session_state.portfolio_df.empty:
        df = st.session_state.portfolio_df.copy()
        
        progress_text = "최신 주가 및 환율 적용 중..."
        my_bar = st.progress(0, text=progress_text)
        
        current_prices = []
        eval_values_krw = []
        purchase_values_krw = []
        
        for index, row in df.iterrows():
            ticker = row['종목코드']
            price = get_current_price(ticker)
            current_prices.append(price)
            
            if row['국가'] == '미국':
                val_krw = price * row['수량'] * usd_krw
                cost_krw = row['매수단가'] * row['수량'] * usd_krw 
            else:
                val_krw = price * row['수량']
                cost_krw = row['매수단가'] * row['수량']
            
            eval_values_krw.append(val_krw)
            purchase_values_krw.append(cost_krw)
            my_bar.progress((index + 1) / len(df), text=progress_text)
            
        my_bar.empty()
        
        df['현재가(현지)'] = current_prices
        df['평가금액(KRW)'] = eval_values_krw
        df['수익률(%)'] = df.apply(
            lambda x: ((x['현재가(현지)'] - x['매수단가']) / x['매수단가'] * 100) if x['매수단가'] > 0 else 0, 
            axis=1
        )
        
        total_asset = df['평가금액(KRW)'].sum()
        total_invest = sum(purchase_values_krw)
        total_profit = total_asset - total_invest
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("💰 총 자산 (원화)", f"{total_asset:,.0f} 원")
        col_m2.metric("📈 총 평가 손익", f"{total_profit:,.0f} 원", delta_color="normal")
        col_m3.metric("📊 평균 수익률", f"{(total_profit/total_invest*100):.2f} %")
        
        st.divider()

        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader("업종별 비중")
            fig1 = px.pie(df, values='평가금액(KRW)', names='업종', hole=0.4)
            fig1.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            st.subheader("종목별 비중")
            fig2 = px.pie(df, values='평가금액(KRW)', names='종목명', hole=0.4)
            fig2.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig2, use_container_width=True)
        with c3:
            st.subheader("국가별 비중")
            fig3 = px.pie(df, values='평가금액(KRW)', names='국가', hole=0.4, 
                          color='국가', color_discrete_map={'한국':'#00498c', '미국':'#bd081c'})
            fig3.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig3, use_container_width=True)

        st.markdown("### 📋 상세 보유 현황 (환율 자동 적용)")
        st.dataframe(
            df[['종목명', '국가', '수량', '매수단가', '현재가(현지)', '수익률(%)', '평가금액(KRW)']].style.format({
                '매수단가': "{:,.2f}",
                '현재가(현지)': "{:,.2f}",
                '수익률(%)': "{:,.2f}%",
                '평가금액(KRW)': "{:,.0f} 원"
            }),
            use_container_width=True
        )

    else:
        st.warning("데이터가 없습니다. 입력 탭에서 포트폴리오를 추가해주세요.")

# =============================================================================
# [Tab 2] 포트폴리오 입력
# =============================================================================
with tab2:
    st.header("📝 포트폴리오 입력")

    # [기능 추가] 업종 추가하기 섹션
    with st.expander("➕ 업종 목록 추가/관리 (클릭해서 열기)"):
        c_add1, c_add2 = st.columns([3, 1])
        with c_add1:
            new_industry = st.text_input("새로운 업종 이름 입력 (예: 자동차, 바이오)")
        with c_add2:
            if st.button("목록에 추가"):
                if new_industry and new_industry not in st.session_state.industry_options:
                    st.session_state.industry_options.append(new_industry)
                    st.success(f"'{new_industry}' 업종이 추가되었습니다!")
                    st.rerun() # 화면 새로고침해서 반영
                elif new_industry in st.session_state.industry_options:
                    st.warning("이미 존재하는 업종입니다.")

    st.info("💡 팁: 미국 주식의 '매수단가'는 **달러($)** 기준으로 입력하세요. 요약 탭에서 자동으로 원화로 변환됩니다.")

    edited_df = st.data_editor(
        st.session_state.portfolio_df,
        num_rows="dynamic",
        column_config={
            "종목코드": st.column_config.TextColumn("종목코드 (예: IAU)", required=True),
            "종목명": st.column_config.TextColumn("종목명", required=True),
            # [수정] options에 session_state에 있는 동적 리스트 연결
            "업종": st.column_config.SelectboxColumn("업종", options=st.session_state.industry_options, required=True),
            "국가": st.column_config.SelectboxColumn("국가", options=["한국", "미국"], required=True),
            "수량": st.column_config.NumberColumn("수량", min_value=0, step=1),
            "매수단가": st.column_config.NumberColumn("매수단가 (한국=원, 미국=달러)", min_value=0.0, format="%.2f"),
        },
        use_container_width=True
    )

    if st.button("💾 저장 및 적용", type="primary"):
        st.session_state.portfolio_df = edited_df
        st.rerun()
