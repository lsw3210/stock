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

# --- 분석 로직 ---
def analyze_stock(ticker):
    try:
        stock_obj = yf.Ticker(ticker)
        today_hist = stock_obj.history(period="1d", interval="5m", prepost=True)
        hist = stock_obj.history(period="1mo")
        
        # 조건 완화: 데이터가 하나라도 있으면 일단 분석하도록 수정
        if today_hist.empty or len(hist) < 2: 
            return None

        info = stock_obj.info
        name = info.get('longName') or info.get('shortName') or ticker
        
        # 데이터가 20개가 안 될 경우를 대비한 안전한 인덱싱
        curr_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else curr_price
        change = ((curr_price - prev_close) / prev_close) * 100 if prev_close != 0 else 0
        
        # 지표 계산 시 데이터 개수 체크
        ma5 = hist['Close'].rolling(5).mean().iloc[-1] if len(hist) >= 5 else curr_price
        ma20 = hist['Close'].rolling(20).mean().iloc[-1] if len(hist) >= 20 else curr_price
        
        score = 1
        reasons = []
        if curr_price > ma5: score += 1; reasons.append("5일선 위")
        if ma5 > ma20: score += 1; reasons.append("단기 이평 정배열")

        price_fmt = f"{int(curr_price):,}원" if ".KS" in ticker else f"${curr_price:,.2f}"
        
        return {
            "티커": ticker,
            "종목명": name,
            "현재가": price_fmt,
            "등락률": round(change, 2),
            "신호": "매수" if score >= 2 else "매도",
            "강도": score,
            "이유": ", ".join(reasons) if reasons else "데이터 부족/보통",
            "chart_series": today_hist['Close'] 
        }
    except Exception as e:
        # 로그에 에러를 찍어서 관리자 모드에서 볼 수 있게 함
        print(f"Error analyzing {ticker}: {e}")
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
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, ticker in enumerate(current_tickers):
        percent = int((i + 1) / len(current_tickers) * 100)
        status_text.text(f"⏳ 분석 중: {ticker} ({percent}%)")
        progress_bar.progress(percent)
        
        res = analyze_stock(ticker)
        if res:
            results.append(res)

    if results:
        status_text.success(f"✅ 총 {len(results)}개 종목 분석 완료!")
        
        # 표 출력을 위해 차트 데이터 제외한 데이터프레임 생성
        df = pd.DataFrame(results)
        display_df = df.drop(columns=['chart_series'])
        
        # 1. 상단 요약 표 (오른쪽 앱 스타일)
        st.dataframe(
            display_df,
            column_config={
                "등락률": st.column_config.NumberColumn("등락률(%)", format="%.2f%%"),
                "강도": st.column_config.ProgressColumn("강도", min_value=0, max_value=5),
            },
            hide_index=True,
            use_container_width=True
        )

        st.markdown("---")

        # 2. 하단 상세 차트 (Plotly로 Y축 최적화)
        for res in results:
            with st.expander(f"🔍 {res['티커']} ({res['종목명']}) 상세 분석 및 차트"):
                # 인덱스에서 시간대 제거 (Plotly 호환성)
                data = res['chart_series'].copy()
                data.index = data.index.tz_localize(None) 
                
                # 차트 생성 시 x, y 명시적 지정
                fig = px.line(x=data.index, y=data.values, title=f"{res['티커']} 실시간 추이")
                
                fig.update_yaxes(autorange=True, fixedrange=False, title="Price")
                fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=350)
                
                st.plotly_chart(fig, use_container_width=True)
                st.write(f"**현재가:** {res['현재가']} | **신호:** {res['신호']} | **이유:** {res['이유']}")
    else:
        st.error("분석 결과가 없습니다. 티커를 확인해 주세요.")
