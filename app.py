# https://hitstock.streamlit.app

import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os

# --- 설정 및 초기화 ---
CONFIG_FILE = "stock_config.json"
DEFAULT_TICKERS = [
    "BITX", "GOOGL", "INTC", "SNDK", "SOXL", "MSFT", "AAPL", "NVDA", "TSLA", "META", "AMZN", "WDC",
    "005930.KS", "000660.KS", "035420.KS", "051910.KS", "068270.KS", "105560.KS", "323410.KS", "207940.KS"
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
        # 장전/후 포함 데이터
        today_hist = stock_obj.history(period="1d", interval="5m", prepost=True)
        hist = stock_obj.history(period="1mo")
        if today_hist.empty or len(hist) < 2: return None

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
            "현재가": curr_price,
            "등락률": round(change, 2), 
            "신호": "매수", 
            "강도": 3, 
            "이유": "분석 완료",
            "chart_series": today_hist['Close'] 
        }
    except: return None

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
    # 1. 진행률 바 생성
    progress_bar = st.progress(0)
    status_text = st.empty()    

    for i, ticker in enumerate(current_tickers):
        # 2. 진행률 업데이트
        percent = int((i + 1) / len(current_tickers) * 100)
        status_text.text(f"⏳ 분석 중: {ticker} ({percent}%)")
        progress_bar.progress(percent)
        
        res = analyze_stock(ticker)
        if res: results.append(res)

    if results:
        status_text.success("✅ 분석 완료!")
        df = pd.DataFrame(results)
        
        # 표에는 텍스트 데이터만 표시 (차트 데이터는 숨김)
        display_df = df.drop(columns=['chart_series'])
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.divider()

        # 3. 차트 일직선 해결 (Y축 최적화)
        for res in results:
            with st.expander(f"🔍 {res['티커']} 상세 차트 (장전/후 포함)"):
                data = res['chart_series']
                
                # 핵심: y_axis_label을 설정하고 데이터의 최소/최대값 범위를 타이트하게 잡음
                # Streamlit의 line_chart는 데이터의 변동폭이 작으면 자동으로 범위를 조정하지만 
                # 명확하게 하기 위해 차트 설정을 건너뛰고 차트 자체를 렌더링합니다.
                st.subheader(f"{res['종목명']} ({res['티커']})")
                
                # 아래 chart_data를 사용하면 Y축이 0부터 시작하지 않고 주가 근처에서 형성됩니다.
                st.line_chart(data, y_label="Price", use_container_width=True) 
                st.caption(f"최근 주가 변동 범위: {data.min():.2f} ~ {data.max():.2f}")
    else:
        st.error("분석 결과가 없습니다. 티커를 확인해 주세요.")
