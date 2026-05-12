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
    "BITX", "GOOGL", "INTC", "SNDK", "SOXL", "MSFT", "AAPL", "NVDA", "TSLA", "META", "AMZN", "WDC",
    "005930.KS", "000660.KS", "035420.KS", "051910.KS", "068270.KS", "105560.KS", "323410.KS", "207940.KS"
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
        # 1. 일단 데이터 가져오기
        today_hist = stock_obj.history(period="1d", interval="5m", prepost=True)
        hist = stock_obj.history(period="5d") # 검증용은 5일치면 충분

        # 2. 데이터가 완전히 없는 경우만 리턴 (조건 완화)
        if hist.empty: 
            return None

        # 3. 실시간 데이터가 비어있다면(장외 시간 등), 최근 5일 데이터에서 마지막 값을 가져옴
        if today_hist.empty:
            curr_price = hist['Close'].iloc[-1]
            change = 0.0 # 장 닫힘 상태
            chart_data = hist['Close'] # 차트도 주간 차트로 대체
        else:
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
    
# 1. 세션 상태 초기화
if 'selected_ticker' not in st.session_state:
    st.session_state['selected_ticker'] = None


# 2. 다이얼로그 함수 내부 수정
## --- 3. 팝업창(Dialog) 정의 ---
@st.dialog("📈 상세 차트 분석", width="large")
def show_details(res):
    st.subheader(f"{res['종목명']} ({res['티커']})")
    
    # 1. 데이터 복사 및 타임존 변환
    data = res['chart_series'].copy()
    data.index = data.index.tz_convert('Asia/Seoul')
    
    # 2. 최근 2시간 데이터만 필터링 (핵심 로직 추가)
    # 현재 서울 시각 기준으로 2시간 전 시점을 계산합니다.
    now_seoul_dt = datetime.now(pytz.timezone('Asia/Seoul'))
    two_hours_ago = now_seoul_dt - pd.Timedelta(hours=2)
    
    # 계산된 시점 이후의 데이터만 추출합니다.
    filtered_data = data[data.index >= two_hours_ago]
    
    # 만약 최근 2시간 데이터가 너무 적다면 최소 20개는 보여주도록 예외처리할 수 있습니다.
    if len(filtered_data) < 20:
        filtered_data = data.tail(30) # 데이터가 부족하면 그냥 마지막 30개를 보여줌

    # 3. 차트 생성 (필터링된 데이터 사용)
    fig = px.line(x=filtered_data.index, y=filtered_data.values, title="실시간 가격 추이 (최근 2시간)")
    
    fig.update_xaxes(
        tickformat="%H:%M",       # 시:분 형식
        dtick=600000,             # 눈금 간격 10분(600,000ms) - 1분은 너무 촘촘하여 10분 권장
        title="시간"
    )
    
    fig.update_yaxes(autorange=True, fixedrange=False, title="가격")
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
    
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"**현재 분석 상태:** {res['이유']}")
    # if st.button("닫기", use_container_width=True):
    #     st.session_state['selected_ticker'] = None # 선택 상태 초기화
    #     st.rerun()

# --- 4. 메인 UI 구성 ---
st.title("📊 AI 주식 분석 시스템")
st.write(f"🔄 **데이터 최근 갱신 (서울):** {now_seoul}")

# 사이드바 설정
st.sidebar.header("⚙️ 종목 설정")
saved_tickers = load_settings()
# saved_tickers = DEFAULT_TICKERS

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
        else:
            # 원인 파악을 위한 출력
            st.error(f"❌ {ticker}: 데이터를 가져오는 데 실패했거나 조건(데이터량 등) 미달입니다.")
    return results

# 새로고침마다 데이터를 강제로 새로 가져옴
results = run_analysis()
if not results:
    st.warning("분석 결과가 없습니다. 아래 사항을 확인하세요:")
    st.write("- 티커 이름이 정확한가요? (예: NVDA, 005930.KS)")
    st.write("- 현재 시장이 열려 있거나 최근 거래 기록이 있나요?")
    st.write("- 인터넷 연결 상태나 API 차단 여부를 확인하세요.")
else:
    st.session_state['analysis_results'] = results

# 결과 출력
if results:
    df = pd.DataFrame(results)
    display_df = df.drop(columns=['chart_series'])

    st.info("💡 종목 행을 클릭하면 상세 차트가 팝업됩니다.")

    # 표 출력 (모바일 틀 고정 및 가독성 설정)
    selection = st.dataframe(
        display_df,
        on_select="rerun",
        key="stock_df", # 고유 키 부여
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
        # 이전 선택과 다를 때만 업데이트하거나 팝업을 유지
        current_res = results[selected_idx]
        show_details(results[selected_idx])
else:
    st.warning("분석할 수 있는 데이터가 없습니다. 티커를 확인해 주세요.")