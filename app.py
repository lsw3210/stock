# https://hitstock.streamlit.app

import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import plotly.express as px

# --- 설정 및 초기화 ---
CONFIG_FILE = "stock_config.json"
DEFAULT_TICKERS = [
    "BITX", "GOOGL", "INTC", "SNDK", "SOXL", "MSFT", "AAPL", "NVDA", "TSLA", "META", "AMZN", "WDC",
    "005930.KS", "000660.KS", "035420.KS", "051910.KS", "068270.KS", "105560.KS", "323410.KS", "207940.KS"
]

st.set_page_config(page_title="AI 주식 분석 시스템", layout="wide")

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return DEFAULT_TICKERS

def save_settings(tickers):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(tickers, f, ensure_ascii=False, indent=4)

# --- 2. 분석 로직 (방어적 설계) ---
def analyze_stock(ticker):
    try:
        stock_obj = yf.Ticker(ticker)
        # 장전/후 포함 5분 단위 데이터 (오늘)
        today_hist = stock_obj.history(period="1d", interval="5m", prepost=True)
        # 기술적 지표용 1개월 데이터
        hist = stock_obj.history(period="1mo")
        
        if today_hist.empty or len(hist) < 20: return None

        info = stock_obj.info
        name = info.get('longName') or info.get('shortName') or ticker


        # --- 현재가 결정 (장전/후 포함 최신가) ---
        curr_price = today_hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change = ((curr_price - prev_close) / prev_close) * 100

        # --- 기술적 지표 계산 ---
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        last_gain = gain.iloc[-1]
        last_loss = loss.iloc[-1]
        rs = last_gain / last_loss if last_loss != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        
        ma5 = hist['Close'].rolling(5).mean().iloc[-1]
        ma20 = hist['Close'].rolling(20).mean().iloc[-1]

        # --- 스코어링 시스템 (방식 1 채택) ---
        score = 0
        reasons = []
        
        if rsi < 30: score += 3; reasons.append("RSI 과매도")
        elif rsi > 70: score -= 2; reasons.append("RSI 과매수") # 과매수는 주의
        
        if curr_price > ma5: score += 1; reasons.append("5일선 위")
        if ma5 > ma20: score += 1; reasons.append("정배열")

        price_fmt = f"{int(curr_price):,}원" if ".KS" in ticker else f"${curr_price:,.2f}"
        
        return {
            "티커": ticker,
            "종목명": name,
            "현재가": price_fmt,
            "등락률": round(change, 2),
            "신호": "매수" if score >= 2 else "매도",
            "강도": max(0, min(score, 5)),
            "이유": ", ".join(reasons) if reasons else "관망",
            "chart_series": today_hist['Close'] 
        }
    except:
        return None

# --- 3. 팝업창(Dialog) 정의 ---
@st.dialog("📈 종목 상세 분석", width="large")
def show_details(res):
    st.subheader(f"{res['종목명']} ({res['티커']})")
    
    # 데이터 인덱스 정리 (시간대 제거)
    data = res['chart_series'].copy()
    data.index = data.index.tz_localize(None)
    
    # Plotly 차트 생성 (Y축 자동 스케일링 핵심)
    fig = px.line(x=data.index, y=data.values, title=f"실시간 추이 (장전/후 포함)")
    fig.update_yaxes(autorange=True, fixedrange=False, title="Price")
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=400)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 지표 요약
    c1, c2, c3 = st.columns(3)
    c1.metric("현재가", res['현재가'])
    c2.metric("등락률", f"{res['등락률']}%")
    c3.metric("분석강도", f"{res['강도']}/5")
    
    st.write(f"**💡 분석 결과:** {res['이유']}")
    # if st.button("닫기", use_container_width=True):
    #     st.rerun()

# --- 4. 메인 UI 구성 ---
st.title("📊 AI 주식 분석 시스템")

# 사이드바
st.sidebar.header("⚙️ 종목 설정")
saved_tickers = load_settings()
tickers_input = st.sidebar.text_area("분석 티커 목록", value="\n".join(saved_tickers), height=300)
current_tickers = [t.strip().upper() for t in tickers_input.replace(",", "\n").split("\n") if t.strip()]

if st.sidebar.button("💾 설정 저장"):
    save_settings(current_tickers)
    st.sidebar.success("설정 저장 완료!")

# 분석 실행 버튼
if st.button("🚀 실시간 분석 및 데이터 로드", use_container_width=True):
    results = []
    prog_bar = st.progress(0)
    status_msg = st.empty()

    for i, ticker in enumerate(current_tickers):
        pct = int((i + 1) / len(current_tickers) * 100)
        status_msg.text(f"⏳ 분석 중: {ticker} ({pct}%)")
        prog_bar.progress(pct)
        
        res = analyze_stock(ticker)
        if res: results.append(res)
    
    # 세션에 결과 저장 (클릭 이벤트 대응용)
    st.session_state['analysis_results'] = results
    status_msg.success(f"✅ 총 {len(results)}개 종목 분석 완료!")

# 결과 출력
if 'analysis_results' in st.session_state and st.session_state['analysis_results']:
    results = st.session_state['analysis_results']
    df = pd.DataFrame(results)
    display_df = df.drop(columns=['chart_series'])

    st.info("💡 종목 왼쪽 체크를 클릭하면 상세 차트가 팝업됩니다.")

    # 표 출력 및 선택 이벤트 감지
    selection = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        # --- 핵심: 열 고정 및 너비 설정 ---
        column_config={
            "티커": st.column_config.TextColumn("티커", pinned=True), # 왼쪽 고정
            "종목명": st.column_config.TextColumn("종목명", width="medium"), 
            "등락률": st.column_config.NumberColumn("등락률(%)", format="%.2f%%"),
            "강도": st.column_config.ProgressColumn("강도", min_value=0, max_value=5),
        }
    )

    # 행 선택 시 팝업 띄우기
    if selection.selection.rows:
        selected_row_idx = selection.selection.rows[0]
        show_details(results[selected_row_idx])
else:
    st.write("분석 버튼을 눌러주세요.")
    # else:
    #     st.error("분석 결과가 없습니다. 티커를 확인해 주세요.")
