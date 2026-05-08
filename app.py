import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os

# --- 설정 및 초기화 ---
CONFIG_FILE = "stock_config.json"
DEFAULT_TICKERS = [
    "BITX",
    "GOOGL",
    "INTC",
    "SNDK",
    "SOXL",
    "MSFT",
    "AAPL",
    "NVDA",
    "TSLA",
    "META",
    "AMZN",
    "WDC",
    "005930.KS",
    "000660.KS",
    "035420.KS",
    "051910.KS",
    "068270.KS",
    "105560.KS",
    "323410.KS",
    "207940.KS"
]

st.set_page_config(page_title="AI 주식 분석 시스템", layout="wide")

def load_settings():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_TICKERS

def save_settings(tickers):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(tickers, f, ensure_ascii=False, indent=4)

# --- 분석 로직 ---
def analyze_stock(ticker):
    try:
        stock_obj = yf.Ticker(ticker)
        hist = stock_obj.history(period="1mo")
        today_hist = stock_obj.history(period="1d", interval="5m")
        
        if hist.empty: return None

        info = stock_obj.info
        name = info.get('longName') or info.get('shortName') or ticker
        curr_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change = ((curr_price - prev_close) / prev_close) * 100
        
        # 기술적 지표
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        ma5 = hist['Close'].rolling(5).mean().iloc[-1]
        ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]

        score = 0
        reasons = []
        if rsi < 30: score += 3; reasons.append("RSI 과매도")
        elif rsi > 70: score -= 3; reasons.append("RSI 과매수")
        if curr_price > ma5: score += 1; reasons.append("5일선 위")
        if ma5 > ma20: score += 1; reasons.append("정배열")

        # 포맷팅
        price_fmt = f"{int(curr_price):,}원" if ".KS" in ticker else f"${curr_price:,.2f}"
        
        return {
            "티커": ticker,
            "종목명": name,
            "현재가": price_fmt,
            "등락률": round(change, 2),
            "신호": "매수" if score >= 0 else "매도",
            "강도": abs(score),
            "이유": ", ".join(reasons) if reasons else "보통",
            "chart_data": today_hist['Close']
        }
    except:
        return None

# --- UI 구성 ---
st.title("📊 AI 주식 분석 시스템")

# 사이드바 설정
st.sidebar.header("⚙️ 종목 설정")
saved_tickers = load_settings()
tickers_input = st.sidebar.text_area("분석 티커 목록 (쉼표 또는 줄바꿈 구분)", 
                                    value="\n".join(saved_tickers), height=400)
current_tickers = [t.strip().upper() for t in tickers_input.replace(",", "\n").split("\n") if t.strip()]

if st.sidebar.button("💾 설정 저장"):
    save_settings(current_tickers)
    st.sidebar.success("설정이 저장되었습니다!")

# 메인 화면
if st.button("🚀 실시간 분석 및 차트 로드", use_container_width=True):
    results = []
    for ticker in current_tickers:
        res = analyze_stock(ticker) # 기존 분석 함수 호출
        if res:
            # 표에 넣기 좋게 데이터를 가공합니다.
            results.append({
                "티커": res["티커"],
                "종목명": res["종목명"],
                "현재가": res["현재가"],
                "등락률(%)": res["등락률"],
                "신호": res["신호"],
                "강도": res["강도"],
                "이유(Reason)": res["이유"]
            })

    if results:
        df = pd.DataFrame(results)
        
        # 1. 오른쪽 앱처럼 깔끔한 표로 보여주기
        # st.dataframe을 쓰면 열 너비 조절과 정렬이 가능합니다.
        st.dataframe(
            df,
            column_config={
                "등락률(%)": st.column_config.NumberColumn(format="%.2f%%"),
                "강도": st.column_config.ProgressColumn(min_value=0, max_value=5),
            },
            hide_index=True,
            use_container_width=True
        )

        # 2. 차트는 표 아래에 별도로 한 번에 보여주거나, 상세 보기로 유지
        st.subheader("📈 당일 추이 (1D)")
        cols = st.columns(3) # 한 줄에 3개씩 차트 배치
        for i, res in enumerate(results):
            with cols[i % 3]:
                # 실제 차트 데이터는 analyze_stock에서 받은 데이터를 사용
                # res["chart_data"]가 담긴 별도 리스트가 필요할 수 있습니다.
                st.line_chart(analyze_stock(res["티커"])["chart_data"], height=150)
                st.caption(f"{res['티커']} 추이")
    else:
        st.error("분석 결과가 없습니다. 티커를 확인해 주세요.")
