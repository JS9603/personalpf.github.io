import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import io

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="My Excel Portfolio", layout="wide", page_icon="📊")

st.title("📊 엑셀 포트폴리오 뷰어")
st.markdown("PC나 스마트폰에 있는 **엑셀 파일(.xlsx)**을 업로드하면 대시보드로 만들어줍니다.")

# -----------------------------------------------------------------------------
# 2. 엑셀 양식 다운로드 기능
# -----------------------------------------------------------------------------
def get_template_excel():
    data = {
        '종목코드': ['000660.KS', 'IAU', 'SPLG'],
        '종목명': ['SK하이닉스', 'iShares Gold', 'S&P 500'],
        '업종': ['반도체', '원자재', '지수추종'],
        '국가': ['한국', '미국', '미국'],
        '수량': [10, 20, 15],
        '매수단가': [180000, 53.50, 68.20]
    }
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='포트폴리오')
    return output.getvalue()

with st.expander("⬇️ 엑셀 양식 다운로드 (처음이라면 먼저 받으세요)"):
    st.write("아래 버튼을 눌러 양식을 받은 뒤, 내 주식 정보를 입력하고 저장하세요.")
    st.download_button(
        label="엑셀 양식 받기 (.xlsx)",
        data=get_template_excel(),
        file_name='my_portfolio_template.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# -----------------------------------------------------------------------------
# 3. 파일 업로드 섹션
# -----------------------------------------------------------------------------
st.divider()
uploaded_file = st.file_uploader("📂 엑셀 파일을 여기에 드래그하거나 선택하세요", type=['xlsx'])

# -----------------------------------------------------------------------------
# 4. 대시보드 출력
# -----------------------------------------------------------------------------
if uploaded_file is not None:
    try:
        # 엑셀 읽기
        df = pd.read_excel(uploaded_file)
        
        # 필수 컬럼 확인
        required_cols = ['종목코드', '종목명', '업종', '국가', '수량', '매수단가']
        if not all(col in df.columns for col in required_cols):
            st.error(f"엑셀 파일 양식이 맞지 않습니다. 필수 컬럼이 모두 있는지 확인해주세요: {required_cols}")
            st.stop()

        # 데이터 수집 함수
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

        # 대시보드 탭 구성
        tab1, tab2 = st.tabs(["📊 대시보드", "📝 원본 데이터"])

        with tab1:
            usd_krw = get_exchange_rate()
            st.caption(f"기준 환율: 1 USD = {usd_krw:,.2f} KRW")

            # 로딩바
            progress_bar = st.progress(0, text="자산 가치를 계산 중입니다...")
            
            current_prices = []
            eval_values_krw = []
            buying_values_krw = []
            
            for index, row in df.iterrows():
                price = get_current_price(row['종목코드'])
                current_prices.append(price)
                
                # 국가별 계산 (환율 적용)
                if row['국가'] == '미국':
                    # 미국 주식: 달러 * 환율
                    eval_val = price * row['수량'] * usd_krw
                    buy_val = row['매수단가'] * row['수량'] * usd_krw
                else:
                    # 한국 주식: 원화 그대로
                    eval_val = price * row['수량']
                    buy_val = row['매수단가'] * row['수량']

                eval_values_krw.append(eval_val)
                buying_values_krw.append(buy_val)
                
                progress_bar.progress((index + 1) / len(df))
            
            progress_bar.empty()

            # 데이터프레임에 계산 결과 추가
            df['현재가(현지)'] = current_prices
            df['매수금액(KRW)'] = buying_values_krw
            df['평가금액(KRW)'] = eval_values_krw
            
            # 개별 수익률 계산 (매수단가가 0인 경우 방어)
            df['수익률(%)'] = df.apply(lambda x: ((x['현재가(현지)'] - x['매수단가']) / x['매수단가'] * 100) if x['매수단가'] > 0 else 0, axis=1)

            # 전체 포트폴리오 요약 지표 계산
            total_buy_amt = df['매수금액(KRW)'].sum()
            total_eval_amt = df['평가금액(KRW)'].sum()
            total_profit = total_eval_amt - total_buy_amt
            total_yield = (total_profit / total_buy_amt * 100) if total_buy_amt != 0 else 0

            # 3단 컬럼으로 지표 표시
            st.divider()
            m1, m2, m3 = st.columns(3)
            
            with m1:
                st.metric(label="총 매수금액", value=f"{total_buy_amt:,.0f} 원")
            
            with m2:
                st.metric(label="총 평가금액", value=f"{total_eval_amt:,.0f} 원", delta=f"{total_profit:+,.0f} 원")
            
            with m3:
                st.metric(label="총 수익률", value=f"{total_yield:,.2f} %", delta=f"{total_yield:,.2f} %")
            
            st.divider()

            # 차트 영역
            c1, c2, c3 = st.columns(3)
            with c1:
                st.plotly_chart(px.pie(df, values='평가금액(KRW)', names='업종', title="업종별 비중", hole=0.3), use_container_width=True)
            with c2:
                st.plotly_chart(px.pie(df, values='평가금액(KRW)', names='종목명', title="종목별 비중", hole=0.3), use_container_width=True)
            with c3:
                st.plotly_chart(px.pie(df, values='평가금액(KRW)', names='국가', title="국가별 비중", color='국가', hole=0.3, color_discrete_map={'한국':'#00498c', '미국':'#bd081c'}), use_container_width=True)

            # 상세 표 (오류 원인이었던 background_gradient 제거함)
            st.subheader("📋 보유 종목 상세")
            st.dataframe(
                df[['종목명', '국가', '수량', '매수단가', '현재가(현지)', '수익률(%)', '평가금액(KRW)']].style.format({
                    '매수단가': "{:,.2f}", 
                    '현재가(현지)': "{:,.2f}", 
                    '수익률(%)': "{:,.2f}%", 
                    '평가금액(KRW)': "{:,.0f}"
                }),
                use_container_width=True
            )

        with tab2:
            st.write("업로드한 엑셀 파일의 내용입니다.")
            st.dataframe(df)

    except Exception as e:
        st.error(f"오류가 발생했습니다. 내용을 확인해주세요: {e}")
else:
    st.info("👆 위에서 엑셀 파일을 업로드하면 분석 결과가 여기에 나타납니다.")
