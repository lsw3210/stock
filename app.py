import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import json
import os
from datetime import datetime
import pytz
from streamlit_autorefresh import st_autorefresh

# --- 1. 설정 및 초기화 ---
CONFIG_FILE = "stock_config.json"
DEFAULT_TICKERS = [
    "BITX", "BTC-USD", "NVDA", "TSLA", "AAPL", "SOXL", "GOOGL", "MSFT",
    "005930.KS", "000660.KS", "035420.KS", "051910.KS"
]

st.set_page_config(page_title="AI 주식 분석 시스템", layout="wide")

# 자동 새로고침 설정 (60초 = 60000ms)
st_autorefresh(interval=60000, key="fscounter")

# 서울 시간 설정
seoul_tz = pytz.timezone('Asia/Seoul')
now_seoul = datetime.now(seoul_tz).strftime("%m월 %d일 %H:%M")

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

# --- 2. 분석 로직 (실시간 데이터 중심) ---
def analyze_stock(ticker):
    try:
        stock_obj = yf.Ticker(ticker)
        # 실시간성 확보를 위해 prepost=True 사용
        today_hist = stock_obj.history(period="1d", interval="5m", prepost=True)
        hist = stock_obj.history(period="1mo")
        
        if today_hist.empty or len(hist) < 20: return None

        # 실시간 현재가 (가장 최신 데이터 행)
        curr_price = today_hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change = ((curr_price - prev_close) / prev_close) * 100
        
        # 기술적 지표 (RSI, MA)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        
        ma5 = hist['Close'].rolling(5).mean().iloc[-1]
        ma20 = hist['Close'].rolling(20).mean().iloc[-1]

        score = 0
        reasons = []
        if rsi < 30: score += 3; reasons.append("RSI 과매도")
        elif rsi > 70: score -= 2; reasons.append("RSI 과매수")
        if curr_price > ma5: score += 1; reasons.append("5일선 위")
        if ma5 > ma20: score += 1; reasons.append("정배열")

        name = stock_obj.info.get('shortName') or ticker
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
@st.dialog("📈 상세 차트 분석", width="large")
def show_details(res):
    st.subheader(f"{res['종목명']} ({res['티커']})")
    
    data = res['chart_series'].copy()
    data.index = data.index.tz_convert('Asia/Seoul') # 한국 시간으로 변환
    
    fig = px.line(x=data.index, y=data.values, title="실시간 가격 추이 (한국 시간)")
    fig.update_yaxes(autorange=True, fixedrange=False, title="Price")
    fig.update_xaxes(tickformat="%H:%M", title="시간")
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
    
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"**현재 분석 상태:** {res['이유']}")
    if st.button("닫기", use_container_width=True):
        st.rerun()

# --- 4. 메인 UI 구성 ---
st.title("📊 AI 주식 분석 시스템")
st.write(f"🔄 **데이터 최근 갱신 (서울):** {now_seoul}")

# 사이드바 설정
st.sidebar.header("⚙️ 종목 설정")
saved_tickers = load_settings()
tickers_input = st.sidebar.text_area("분석 티커 목록", value="\n".join(saved_tickers), height=300)
current_tickers = [t.strip().upper() for t in tickers_input.replace(",", "\n").split("\n") if t.strip()]

if st.sidebar.button("💾 설정 저장"):
    save_settings(current_tickers)
    st.sidebar.success("설정이 저장되었습니다.")

# 데이터 분석 실행 (자동/수동 공통)
def run_analysis():
    results = []
    for ticker in current_tickers:
        res = analyze_stock(ticker)
        if res: results.append(res)
    return results

# 새로고침마다 데이터를 강제로 새로 가져옴
results = run_analysis()
st.session_state['analysis_results'] = results

# 결과 출력
if results:
    df = pd.DataFrame(results)
    display_df = df.drop(columns=['chart_series'])

    st.info("💡 종목 행을 클릭하면 상세 차트가 팝업됩니다.")

    # 표 출력 (모바일 틀 고정 및 가독성 설정)
    selection = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "티커": st.column_config.TextColumn("티커", pinned=True), # 왼쪽 고정
            "종목명": st.column_config.TextColumn("종목명", width="medium"),
            "등락률": st.column_config.NumberColumn("등락률(%)", format="%.2f%%"),
            "강도": st.column_config.ProgressColumn("강도", min_value=0, max_value=5),
        }
    )

    # 행 선택 시 팝업 띄우기
    if selection.selection.rows:
        selected_idx = selection.selection.rows[0]
        show_details(results[selected_idx])
else:
    st.warning("분석할 수 있는 데이터가 없습니다. 티커를 확인해 주세요.")