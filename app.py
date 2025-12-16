import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="My Private Portfolio", layout="wide", page_icon="🔒")

# -----------------------------------------------------------------------------
# 2. 로그인 처리 (Secrets에서 비번 가져옴)
# -----------------------------------------------------------------------------
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 포트폴리오 접근")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        password_input = st.text_input("비밀번호를 입력하세요", type="password")
        if st.button("확인"):
            # GitHub 코드에는 비번이 없고, 서버 금고(secrets)에서 가져옵니다.
            if password_input == st.secrets["general"]["password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 메인 대시보드 (로그인 성공 시)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.success("✅ 인증 완료")
    if st.button("로그아웃"):
        st.session_state.authenticated = False
        st.rerun()

st.title("📈 내 자산 현황 (Secret 모드)")

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

# -----------------------------------------------------------------------------
# 4. 데이터 로드 (Secrets에서 데이터 가져옴)
# -----------------------------------------------------------------------------
# GitHub 코드에는 데이터가 없고, 서버 금고(secrets)에서 가져와서 조립합니다.
try:
    my_data = {
        '종목코드': st.secrets["portfolio"]["codes"],
        '종목명': st.secrets["portfolio"]["names"],
        '업종': st.secrets["portfolio"]["sectors"],
        '국가': st.secrets["portfolio"]["countries"],
        '수량': st.secrets["portfolio"]["quantities"],
        '매수단가': st.secrets["portfolio"]["prices"]
    }
    df = pd.DataFrame(my_data)
except Exception as e:
    st.error("데이터를 불러오지 못했습니다. Streamlit Secrets 설정을 확인해주세요.")
    st.stop()

# -----------------------------------------------------------------------------
# 5. 화면 표시
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["📊 대시보드", "📝 데이터 확인"])

with tab1:
    usd_krw = get_exchange_rate()
    st.metric("🇺🇸/🇰🇷 환율", f"{usd_krw:,.2f} 원")
    st.divider()

    if not df.empty:
        progress_bar = st.progress(0, text="자산 가치 계산 중...")
        
        current_prices = []
        eval_values_krw = []
        
        for index, row in df.iterrows():
            price = get_current_price(row['종목코드'])
            current_prices.append(price)
            if row['국가'] == '미국':
                eval_values_krw.append(price * row['수량'] * usd_krw)
            else:
                eval_values_krw.append(price * row['수량'])
            progress_bar.progress((index + 1) / len(df))
        
        progress_bar.empty()

        df['현재가(현지)'] = current_prices
        df['평가금액(KRW)'] = eval_values_krw
        df['수익률(%)'] = df.apply(lambda x: ((x['현재가(현지)'] - x['매수단가']) / x['매수단가'] * 100) if x['매수단가'] > 0 else 0, axis=1)

        total_asset = df['평가금액(KRW)'].sum()
        st.info(f"💰 총 자산: **{total_asset:,.0f} 원**")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.plotly_chart(px.pie(df, values='평가금액(KRW)', names='업종', title="업종별"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df, values='평가금액(KRW)', names='종목명', title="종목별"), use_container_width=True)
        with c3:
            st.plotly_chart(px.pie(df, values='평가금액(KRW)', names='국가', title="국가별", color='국가', color_discrete_map={'한국':'#00498c', '미국':'#bd081c'}), use_container_width=True)

        st.dataframe(df[['종목명', '국가', '수량', '매수단가', '현재가(현지)', '수익률(%)', '평가금액(KRW)']].style.format({'매수단가': "{:,.2f}", '현재가(현지)': "{:,.2f}", '수익률(%)': "{:,.2f}%", '평가금액(KRW)': "{:,.0f}"}), use_container_width=True)

with tab2:
    st.header("🔒 보안 데이터 확인")
    st.write("이 데이터는 GitHub가 아닌 Streamlit Secrets에 안전하게 저장되어 있습니다.")
