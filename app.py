import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import io

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 세션 초기화
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Multi-Account Portfolio", layout="wide", page_icon="🏦")

if 'portfolio_data' not in st.session_state:
    st.session_state['portfolio_data'] = None

if 'search_info' not in st.session_state:
    st.session_state['search_info'] = None

if 'sim_target_sheet' not in st.session_state:
    st.session_state['sim_target_sheet'] = None

if 'sim_df' not in st.session_state:
    st.session_state['sim_df'] = None

st.title("개인 포트폴리오 관리 프로그램 v4.2")
st.markdown("멀티 어카운트 기능추가, 포트폴리오 시뮬레이션 기능추가")

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
        
        current_price = history['Close'].iloc[-1]
        try: info = t.info
        except: info = {}
        
        is_korea = ticker.endswith('.KS') or ticker.endswith('.KQ')
        return {
            '종목코드': ticker,
            '종목명': info.get('shortName', ticker), 
            '업종': info.get('sector', '기타'),
            '국가': '한국' if is_korea else '미국',
            '유형': 'ETF' if info.get('quoteType') == 'ETF' else '개별주식',
            '현재가': current_price,
            'currency': 'KRW' if is_korea else 'USD'
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

def create_pie(data, names, title, value_col='평가금액'):
    if data.empty or value_col not in data.columns: return None
    fig = px.pie(data, values=value_col, names=names, title=title, hole=0.4)
    fig.update_layout(margin=dict(t=30, b=0, l=0, r=0))
    return fig

def color_profit(val):
    if val > 0: return 'color: #ff2b2b'
    elif val < 0: return 'color: #00498c'
    return 'color: black'

def calculate_portfolio(df, usd_krw):
    current_prices, eval_values, buy_values, currencies = [], [], [], []
    
    for index, row in df.iterrows():
        ticker = str(row['종목코드']).upper().strip()
        currency = 'KRW'
        
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
    if '시뮬레이션 수량' not in df.columns:
        df['시뮬레이션 수량'] = df['수량']
    return df

# -----------------------------------------------------------------------------
# 3. 엑셀 다운로드
# -----------------------------------------------------------------------------
def get_template_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1 = pd.DataFrame({'종목코드': ['000660.KS', 'KRW'], '종목명': ['SK하이닉스', '원화예수금'], '업종': ['반도체', '현금'], '국가': ['한국', '한국'], '수량': [10, 1000000], '매수단가': [180000, 1]})
        df1.to_excel(writer, index=False, sheet_name='국내계좌')
        df2 = pd.DataFrame({'종목코드': ['SPLG', 'USD'], '종목명': ['S&P 500', '달러예수금'], '업종': ['지수추종', '현금'], '국가': ['미국', '미국'], '수량': [15, 500], '매수단가': [68.20, 1]})
        df2.to_excel(writer, index=False, sheet_name='미국계좌')
    return output.getvalue()

with st.expander("⬇️ 엑셀 양식 다운로드"):
    st.download_button(label="엑셀 양식 받기 (.xlsx)", data=get_template_excel(), file_name='multi_portfolio.xlsx')

# -----------------------------------------------------------------------------
# 4. 메인 로직
# -----------------------------------------------------------------------------
uploaded_file = st.file_uploader("📂 엑셀 파일을 업로드하세요 (초기화하려면 새로고침)", type=['xlsx'])

if uploaded_file is not None:
    if st.session_state['portfolio_data'] is None:
        try:
            usd_krw = get_exchange_rate()
            xls = pd.read_excel(uploaded_file, sheet_name=None)
            
            processed_data = {}
            with st.spinner('계좌 분석 중...'):
                for sheet_name, df_sheet in xls.items():
                    required = ['종목코드', '종목명', '수량', '매수단가']
                    if not all(col in df_sheet.columns for col in required): continue
                    processed_df = calculate_portfolio(df_sheet.copy(), usd_krw)
                    processed_df['계좌명'] = sheet_name
                    processed_data[sheet_name] = processed_df
            
            if not processed_data:
                st.error("유효한 데이터 시트가 없습니다.")
                st.stop()
            
            st.session_state['portfolio_data'] = processed_data
            st.session_state['usd_krw'] = usd_krw
            
        except Exception as e:
            st.error(f"오류: {e}")
            st.stop()

    portfolio_dict = st.session_state['portfolio_data']
    usd_krw = st.session_state['usd_krw']
    all_df = pd.concat(portfolio_dict.values(), ignore_index=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📊 통합 요약", "📂 계좌별 현황", "🎛️ 시뮬레이션", "📝 원본 데이터"])

    # --- [TAB 1] 통합 요약 ---
    with tab1:
        st.subheader("🌐 전체 자산 통합 리포트")
        
        total_eval = all_df['평가금액'].sum()
        total_buy = all_df['매수금액'].sum()
        profit = total_eval - total_buy
        yield_rate = (profit / total_buy * 100) if total_buy > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("총 매수금액", f"{total_buy:,.0f} 원")
        m2.metric("총 평가금액", f"{total_eval:,.0f} 원", f"{profit:+,.0f} 원")
        m3.metric("총 수익률", f"{yield_rate:.2f} %", f"{yield_rate:.2f} %")
        
        st.divider()
        
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        with r1c1: st.plotly_chart(create_pie(all_df, '계좌명', "1. 계좌별 비중"), use_container_width=True, key='all_c1')
        with r1c2: st.plotly_chart(create_pie(all_df, '종목명', "2. 종목별 비중"), use_container_width=True, key='all_c2')
        with r2c1: st.plotly_chart(create_pie(all_df, '국가', "3. 국가별 비중"), use_container_width=True, key='all_c3')
        with r2c2: st.plotly_chart(create_pie(all_df, '유형', "4. 유형별 비중"), use_container_width=True, key='all_c4')

        st.divider()
        st.subheader("📋 통합 자산 상세")
        summary_cols = ['계좌명', '종목명', '유형', '수량', '매수단가', '현재가', '수익률', '평가금액']
        summary_display = all_df[summary_cols].copy()
        
        st.dataframe(
            summary_display.style.format({
                '수량': '{:,.2f}', '매수단가': '{:,.0f}', '현재가': '{:,.0f}', '수익률': '{:+.2f}%', '평가금액': '{:,.0f}'
            }).map(color_profit, subset=['수익률']),
            use_container_width=True, hide_index=True
        )

    # --- [TAB 2] 계좌별 현황 ---
    with tab2:
        st.subheader("📂 개별 계좌 상세 조회")
        
        sheet_names = list(portfolio_dict.keys())
        selected_sheet = st.selectbox("확인할 계좌:", sheet_names, key='view_sheet')
        target_df = portfolio_dict[selected_sheet]
        
        t_eval = target_df['평가금액'].sum()
        t_buy = target_df['매수금액'].sum()
        t_profit = t_eval - t_buy
        t_yield = (t_profit / t_buy * 100) if t_buy > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric(f"매수금액", f"{t_buy:,.0f} 원")
        c2.metric(f"평가금액", f"{t_eval:,.0f} 원", f"{t_profit:+,.0f} 원")
        c3.metric(f"수익률", f"{t_yield:.2f} %", f"{t_yield:.2f} %")
        
        st.divider()
        sc1, sc2 = st.columns(2)
        with sc1: st.plotly_chart(create_pie(target_df, '종목명', "종목 비중"), use_container_width=True, key=f'v1_{selected_sheet}')
        with sc2: st.plotly_chart(create_pie(target_df, '업종', "업종 비중"), use_container_width=True, key=f'v2_{selected_sheet}')
        
        st.caption(f"📋 {selected_sheet} 보유 종목")
        view_display = target_df[['종목명', '유형', '수량', '매수단가', '현재가', '수익률', '평가금액']].copy()
        st.dataframe(
            view_display.style.format({
                '수량': '{:,.2f}', '매수단가': '{:,.0f}', '현재가': '{:,.0f}', '수익률': '{:+.2f}%', '평가금액': '{:,.0f}'
            }).map(color_profit, subset=['수익률']),
            use_container_width=True, hide_index=True
        )

    # --- [TAB 3] 시뮬레이션 ---
    with tab3:
        st.header("🎛️ 계좌별 리밸런싱 시뮬레이터")
        
        sim_sheets = list(portfolio_dict.keys())
        selected_sim_sheet = st.selectbox("시뮬레이션할 계좌:", sim_sheets, key='sim_sheet')
        
        if st.session_state['sim_target_sheet'] != selected_sim_sheet:
            st.session_state['sim_target_sheet'] = selected_sim_sheet
            st.session_state['sim_df'] = portfolio_dict[selected_sim_sheet].copy()
            st.rerun()
            
        sim_df = st.session_state['sim_df']
        current_total = portfolio_dict[selected_sim_sheet]['평가금액'].sum()

        with st.expander(f"➕ '{selected_sim_sheet}'에 종목 추가", expanded=False):
            c_add1, c_add2 = st.columns([3, 1])
            new_ticker = c_add1.text_input("티커 (예: TSLA)", key='sim_add')
            if c_add2.button("검색"):
                if new_ticker:
                    info = get_stock_info(new_ticker.strip().upper())
                    if info: st.session_state['search_info'] = info
                    else: st.error("종목 없음")
            
            # [수정] 검색 결과 표 형식 출력
            if st.session_state['search_info']:
                info = st.session_state['search_info']
                
                # 표 데이터 생성
                preview_df = pd.DataFrame([{
                    '코드': info['종목코드'],
                    '종목명': info['종목명'],
                    '업종': info['업종'],
                    '현재가': info['현재가']
                }])
                
                st.markdown("##### 🔎 검색 결과")
                st.dataframe(
                    preview_df.style.format({'현재가': '{:,.0f}'}),
                    hide_index=True,
                    use_container_width=True
                )
                
                if st.button("적용", type="primary"):
                    new_row = {
                        '종목코드': info['종목코드'], '종목명': info['종목명'], '업종': info['업종'],
                        '국가': info['국가'], '유형': info['유형'], '수량': 0, '매수단가': 0,
                        '현재가': info['현재가'], '매수금액': 0, '평가금액': 0, '수익률': 0,
                        '통화': info['currency'], '시뮬레이션 수량': 0, '계좌명': selected_sim_sheet
                    }
                    st.session_state['sim_df'] = pd.concat([sim_df, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state['search_info'] = None
                    st.rerun()

        st.divider()

        sim_view_cols = ['종목코드', '종목명', '유형', '통화', '현재가', '시뮬레이션 수량']
        edited_df = st.data_editor(
            sim_df[sim_view_cols],
            column_config={
                "종목코드": st.column_config.TextColumn("코드", disabled=True),
                "종목명": st.column_config.TextColumn("종목명 (수정가능)"),
                "현재가": st.column_config.NumberColumn("단가", format="%d"),
                "시뮬레이션 수량": st.column_config.NumberColumn("목표수량", format="%.2f", min_value=0, step=1)
            },
            num_rows="dynamic", use_container_width=True, hide_index=True, key=f'editor_{selected_sim_sheet}'
        )

        sim_result_df = edited_df.copy()
        
        def calc_sim_eval(row):
            try:
                price, qty = float(row.get('현재가', 0)), float(row.get('시뮬레이션 수량', 0))
                code, curr = str(row.get('종목코드', '')).upper(), row.get('통화', 'KRW')
                if code == 'USD': return price * qty
                if curr == 'USD': return price * qty * usd_krw
                return price * qty
            except: return 0

        sim_result_df['예상 평가금액'] = sim_result_df.apply(calc_sim_eval, axis=1)
        
        meta_lookup = sim_df.set_index('종목코드')[['업종', '국가']].to_dict('index')
        sim_result_df['업종'] = sim_result_df.apply(lambda x: meta_lookup.get(x.get('종목코드'), {}).get('업종', '기타'), axis=1)
        sim_result_df['국가'] = sim_result_df.apply(lambda x: meta_lookup.get(x.get('종목코드'), {}).get('국가', '기타'), axis=1)
        if '유형' not in sim_result_df.columns:
             sim_result_df['유형'] = sim_result_df.apply(classify_asset_type_initial, axis=1)

        sim_total = sim_result_df['예상 평가금액'].sum()
        diff = current_total - sim_total
        
        st.divider()
        c_budget, c_chart = st.columns([1, 2])
        
        with c_budget:
            st.markdown(f"### 💰 {selected_sim_sheet} 예산")
            st.metric("현재 총 자산", f"{current_total:,.0f} 원")
            st.metric("시뮬레이션 총액", f"{sim_total:,.0f} 원")
            if diff >= 0: st.success(f"✅ {diff:,.0f} 원 남음")
            else: st.error(f"🚨 {abs(diff):,.0f} 원 부족")

        with c_chart:
            if not sim_result_df.empty:
                t1, t2 = st.tabs(["차트", "데이터"])
                with t1:
                    c1, c2 = st.columns(2)
                    c3, c4 = st.columns(2)
                    with c1: st.plotly_chart(create_pie(sim_result_df, '종목명', "종목", '예상 평가금액'), use_container_width=True, key='s1')
                    with c2: st.plotly_chart(create_pie(sim_result_df, '업종', "업종", '예상 평가금액'), use_container_width=True, key='s2')
                    with c3: st.plotly_chart(create_pie(sim_result_df, '국가', "국가", '예상 평가금액'), use_container_width=True, key='s3')
                    with c4: st.plotly_chart(create_pie(sim_result_df, '유형', "유형", '예상 평가금액'), use_container_width=True, key='s4')
                with t2:
                    st.dataframe(sim_result_df[['종목명', '시뮬레이션 수량', '예상 평가금액']].style.format({'시뮬레이션 수량': '{:,.2f}', '예상 평가금액': '{:,.0f}'}), use_container_width=True, hide_index=True)

    # --- [TAB 4] 원본 데이터 ---
    with tab4:
        st.dataframe(all_df)

else:
    st.info("👆 엑셀 파일을 업로드해주세요.")
