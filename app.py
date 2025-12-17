import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import io

# -----------------------------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="My Excel Portfolio", layout="wide", page_icon="📊")

st.title("📊 엑셀 포트폴리오 뷰어 v2.0")
st.markdown("엑셀 파일을 업로드하고, **시뮬레이션 탭**에서 리밸런싱 결과를 미리 확인해보세요.")

# -----------------------------------------------------------------------------
# 2. 엑셀 양식 다운로드
# -----------------------------------------------------------------------------
def get_template_excel():
    data = {
        '종목코드': ['000660.KS', 'IAU', 'SPLG', 'KRW', 'USD'],
        '종목명': ['SK하이닉스', 'iShares Gold', 'S&P 500', '원화예수금', '달러예수금'],
        '업종': ['반도체', '원자재', '지수추종', '현금', '현금'],
        '국가': ['한국', '미국', '미국', '한국', '미국'],
        '수량': [10, 20, 15, 1000000, 500],
        '매수단가': [180000, 53.50, 68.20, 1, 1]
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
# 3. 데이터 처리 함수
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

# -----------------------------------------------------------------------------
# 4. 메인 로직
# -----------------------------------------------------------------------------
uploaded_file = st.file_uploader("📂 엑셀 파일을 업로드하세요", type=['xlsx'])

if uploaded_file is not None:
    try:
        # 1) 데이터 로드 및 계산
        df = pd.read_excel(uploaded_file)
        usd_krw = get_exchange_rate()
        
        # 계산 로직
        current_prices = []
        eval_values = []
        buy_values = []
        
        # 로딩바 (짧게 표시)
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

        # 데이터프레임 업데이트
        df['현재가'] = current_prices
        df['매수금액'] = buy_values
        df['평가금액'] = eval_values
        df['수익률(%)'] = df.apply(lambda x: ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100) if x['매수금액'] > 0 else 0, axis=1)

        # ---------------------------------------------------------------------
        # 5. 탭 구성
        # ---------------------------------------------------------------------
        tab1, tab2, tab3 = st.tabs(["📊 대시보드", "🎛️ 시뮬레이션 (비중 조절)", "📝 원본 데이터"])

        # --- [TAB 1] 대시보드 ---
        with tab1:
            # 상단 요약
            total_eval = df['평가금액'].sum()
            total_buy = df['매수금액'].sum()
            total_profit = total_eval - total_buy
            total_yield = (total_profit / total_buy * 100) if total_buy > 0 else 0
            
            st.caption(f"기준 환율: 1 USD = {usd_krw:,.2f} KRW")
            c1, c2, c3 = st.columns(3)
            c1.metric("총 매수금액", f"{total_buy:,.0f} 원")
            c2.metric("총 평가금액", f"{total_eval:,.0f} 원", f"{total_profit:+,.0f} 원")
            c3.metric("총 수익률", f"{total_yield:,.2f} %", f"{total_yield:,.2f} %")
            
            st.divider()

            # 차트 (컴팩트하게 2열 배치)
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.plotly_chart(px.pie(df, values='평가금액', names='종목명', title="자산별 비중", hole=0.4), use_container_width=True)
            with col_chart2:
                # 국가별 비중은 간단한 Bar 차트로 변경 고려했으나 Pie 유지
                st.plotly_chart(px.pie(df, values='평가금액', names='국가', title="국가별 비중", hole=0.4, color='국가', color_discrete_map={'한국':'#00498c', '미국':'#bd081c'}), use_container_width=True)

            # 상세 테이블 (디자인 개선 핵심)
            st.subheader("📋 자산 상세 (Compact View)")
            
            # 보여줄 컬럼만 선택 및 정렬
            display_df = df[['종목명', '수량', '매수단가', '현재가', '수익률(%)', '평가금액']].copy()
            
            # 스타일링 함수 (수익률 색상: 이익=빨강, 손실=파랑)
            def color_profit(val):
                color = '#ff2b2b' if val > 0 else '#00498c' if val < 0 else 'black'
                return f'color: {color}'

            # Pandas Styler 적용
            styled_df = display_df.style.format({
                '수량': '{:,.2f}',         # 소수점 2자리
                '매수단가': '{:,.0f}',
                '현재가': '{:,.0f}',
                '수익률(%)': '{:,.2f}%',
                '평가금액': '{:,.0f}'
            }).map(color_profit, subset=['수익률(%)']) # 수익률 컬럼에만 색상 적용

            # Streamlit 데이터프레임으로 출력 (높이 조절 아규먼트 등 활용 가능)
            st.dataframe(
                styled_df, 
                use_container_width=True, 
                hide_index=True,
                height=(len(df) + 1) * 35 + 3  # 행 개수에 맞춰 높이 자동 조절
            )

        # --- [TAB 2] 시뮬레이션 ---
        with tab2:
            st.header("🎛️ 포트폴리오 리밸런싱 시뮬레이터")
            st.info("아래 표에서 **'시뮬레이션 수량'**을 수정하면, 예상 비중 변화를 미리 볼 수 있습니다. (엔터 키를 눌러 적용)")

            # 시뮬레이션용 데이터 준비
            sim_df = df[['종목명', '종목코드', '현재가', '수량', '평가금액']].copy()
            sim_df.rename(columns={'수량': '현재 수량'}, inplace=True)
            
            # 데이터 에디터 (수정 가능)
            # key를 주어 상태 유지
            edited_df = st.data_editor(
                sim_df,
                column_config={
                    "현재가": st.column_config.NumberColumn("현재가 (단가)", format="%d 원", disabled=True),
                    "현재 수량": st.column_config.NumberColumn("보유 수량", format="%.2f", disabled=True),
                    "평가금액": st.column_config.NumberColumn("현재 평가액", format="%d 원", disabled=True),
                    "시뮬레이션 수량": st.column_config.NumberColumn("목표 수량 (수정가능)", format="%.2f", min_value=0, step=1),
                },
                disabled=["종목명", "종목코드", "현재가", "현재 수량", "평가금액"], # 수량 빼고 잠금
                num_rows="dynamic", # 행 추가 가능 (새 종목 추가 기능은 복잡해서 일단 기존 종목 조절 위주)
                use_container_width=True,
                hide_index=True
            )

            # 시뮬레이션 수량 컬럼이 없으면(처음 로드 시) 현재 수량 복사해서 생성
            if '시뮬레이션 수량' not in edited_df.columns:
                 edited_df['시뮬레이션 수량'] = edited_df['현재 수량']

            # 재계산
            # 사용자가 입력한 수량 * 고정된 현재가 = 예상 평가금액
            edited_df['예상 평가금액'] = edited_df['시뮬레이션 수량'] * edited_df['현재가']
            
            new_total = edited_df['예상 평가금액'].sum()
            
            st.divider()
            
            # 비교 차트 (Before vs After)
            st.subheader("⚖️ 비중 변화 비교")
            
            sc1, sc2 = st.columns(2)
            
            with sc1:
                st.markdown("**현재 포트폴리오**")
                fig_before = px.pie(sim_df, values='평가금액', names='종목명', hole=0.4)
                fig_before.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_before, use_container_width=True)
                
            with sc2:
                st.markdown("**시뮬레이션 후**")
                fig_after = px.pie(edited_df, values='예상 평가금액', names='종목명', hole=0.4)
                fig_after.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_after, use_container_width=True)

            # 변화된 금액 요약
            diff = new_total - total_eval
            st.success(f"💰 시뮬레이션 결과 총 자산: **{new_total:,.0f} 원** (현재 대비 {diff:+,.0f} 원 변동)")
            st.caption("* 현금을 주식으로 바꾸거나 하는 경우 총 자산은 변동이 없어야 하지만, 여기서는 단순 수량 증감에 따른 총액 변화를 보여줍니다.")

        # --- [TAB 3] 원본 데이터 ---
        with tab3:
            st.dataframe(df)

    except Exception as e:
        st.error(f"오류 발생: {e}")
