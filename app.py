import streamlit as st
import pandas as pd
import yfinance as yf
import datetime as dt

st.set_page_config(page_title="📈 이동평균선 교차 모니터링", layout="wide")
st.title("📈 이동평균선 교차 모니터링 대시보드 (Daily & Weekly)")

# 미리 지정된 모니터링 대상 (필요시 여기를 수정하세요)
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOG"]
PERIODS = [200, 240, 365]

@st.cache_data(ttl=3600)
def get_data(ticker, interval="1d"):
    # period=2y를 사용하여 충분한 이동평균 계산 범위를 확보합니다.
    data = yf.download(ticker, period="2y", interval=interval, progress=False)
    for p in PERIODS:
        data[f"MA{p}"] = data["Close"].rolling(p).mean()
    return data

col1, col2 = st.columns([1, 3])
with col1:
    selected = st.selectbox("📊 종목 선택", TICKERS)
    st.write("모니터링 대상 티커는 app.py 내부의 TICKERS 리스트를 수정하여 변경할 수 있습니다.")
with col2:
    st.write("최근 주가 및 이동평균선 (일/주 단위)")

# 일간 데이터
daily = get_data(selected, "1d")
st.subheader("📅 일 단위 (Daily) 차트")
st.line_chart(daily[["Close", "MA200", "MA240", "MA365"]].dropna())

# 주간 데이터
weekly = get_data(selected, "1wk")
st.subheader("🗓️ 주 단위 (Weekly) 차트")
st.line_chart(weekly[["Close", "MA200", "MA240", "MA365"]].dropna())

# 교차 감지 함수
def detect_cross(data):
    cross = []
    # 최근 2개 캔들(바)을 비교하여 교차(상향/하향)를 판단합니다.
    if len(data) < 2:
        return cross
    for p in PERIODS:
        col = f"MA{p}"
        if col not in data.columns:
            continue
        if data['Close'].iloc[-2] < data[col].iloc[-2] and data['Close'].iloc[-1] >= data[col].iloc[-1]:
            cross.append((p, '상향'))
        elif data['Close'].iloc[-2] > data[col].iloc[-2] and data['Close'].iloc[-1] <= data[col].iloc[-1]:
            cross.append((p, '하향'))
    return cross

daily_cross = detect_cross(daily)
weekly_cross = detect_cross(weekly)

if daily_cross or weekly_cross:
    msg_lines = []
    if daily_cross:
        msg_lines.append("일 단위: " + ", ".join([f"{p}일선({dir})" for p,dir in daily_cross]))
    if weekly_cross:
        msg_lines.append("주 단위: " + ", ".join([f"{p}주선({dir})" for p,dir in weekly_cross]))
    st.error("🚨 교차 발생 — " + " / ".join(msg_lines))
else:
    st.success("✅ 최근 교차 없음")

st.caption(f"마지막 업데이트: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
