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
            "신호": "매수" if score >= 0 else "매도",
            "강도": abs(score),
            "이유": ", ".join(reasons) if reasons else "보통",
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
                
                st.subheader(f"{res['종목명']} ({res['티커']})")
                
                # 1. Plotly Express 사용
                import plotly.express as px
                
                # 차트 생성 (x축은 시간 인덱스, y축은 종가)
                fig = px.line(data, y=data.values, x=data.index, 
                              labels={'x': '시간', 'y': '가격'})

                # 2. 핵심 설정: Y축 범위를 데이터에 맞춰 자동 조절(autorange)
                # 이 설정이 들어가야 0부터 시작하지 않고 주가 근처에서 움직입니다.
                fig.update_yaxes(
                    autorange=True, 
                    fixedrange=False,
                    tickformat=",.2f" # 소수점 둘째자리까지 표시
                )

                # 3. 차트 디자인 살짝 추가 (선 색상 등)
                fig.update_traces(line_color='#0077ff', line_width=2)
                fig.update_layout(
                    margin=dict(l=20, r=20, t=5, b=20), # 여백 줄이기
                    height=400
                )

                # 4. Streamlit에 표시
                st.plotly_chart(fig, use_container_width=True)
                
                st.caption(f"📊 현재 구간 변동: {data.min():.2f} ~ {data.max():.2f}")
    else:
        st.error("분석 결과가 없습니다. 티커를 확인해 주세요.")
