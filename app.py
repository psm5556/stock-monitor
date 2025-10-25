import streamlit as st
import pandas as pd
import yfinance as yf
import datetime as dt

st.set_page_config(page_title="📈 이동평균선 교차 모니터링", layout="wide")
st.title("📈 이동평균선 교차 모니터링 대시보드 (Daily & Weekly)")

# 미리 지정된 모니터링 대상
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOG"]
PERIODS = [200, 240, 365]


@st.cache_data(ttl=3600)
def get_data(ticker, interval="1d"):
    """안정적인 Yahoo Finance 데이터 수집"""
    try:
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(period="10y", interval=interval, auto_adjust=True)

        # ✅ MultiIndex 컬럼 방지
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # ✅ 필수 컬럼 확인
        if "Close" not in df.columns:
            raise ValueError(f"{ticker} 데이터에 'Close' 컬럼이 없습니다.")

        # ✅ 이동평균선 직접 계산
        for p in PERIODS:
            df[f"MA{p}"] = df["Close"].rolling(p).mean()

        # ✅ 결측치 제거
        df = df.dropna(subset=["Close"])

        return df

    except Exception as e:
        st.warning(f"{ticker} 데이터 수집 실패: {e}")
        return pd.DataFrame()


def detect_cross(data):
    """이동평균 교차 감지"""
    cross = []
    if len(data) < 2:
        return cross
    for p in PERIODS:
        col = f"MA{p}"
        if col not in data.columns:
            continue
        if data["Close"].iloc[-2] < data[col].iloc[-2] and data["Close"].iloc[-1] >= data[col].iloc[-1]:
            cross.append((p, "상향"))
        elif data["Close"].iloc[-2] > data[col].iloc[-2] and data["Close"].iloc[-1] <= data[col].iloc[-1]:
            cross.append((p, "하향"))
    return cross


col1, col2 = st.columns([1, 3])
with col1:
    selected = st.selectbox("📊 종목 선택", TICKERS)
    st.write("모니터링 대상은 app.py 내부 TICKERS 리스트에서 수정 가능")
with col2:
    st.write("최근 주가 및 이동평균선 (일/주 단위)")

# ✅ 일간 데이터
daily = get_data(selected, "1d")
if not daily.empty:
    st.subheader("📅 일 단위 (Daily) 차트")
    available_cols = [c for c in ["Close", "MA200", "MA240", "MA365"] if c in daily.columns]
    st.line_chart(daily[available_cols])

# ✅ 주간 데이터
weekly = get_data(selected, "1wk")
if not weekly.empty:
    st.subheader("🗓️ 주 단위 (Weekly) 차트")
    available_cols = [c for c in ["Close", "MA200", "MA240", "MA365"] if c in weekly.columns]
    st.line_chart(weekly[available_cols])

# ✅ 교차 감지
daily_cross = detect_cross(daily)
weekly_cross = detect_cross(weekly)

if daily_cross or weekly_cross:
    msg_lines = []
    if daily_cross:
        msg_lines.append("일 단위: " + ", ".join([f"{p}일선({d})" for p, d in daily_cross]))
    if weekly_cross:
        msg_lines.append("주 단위: " + ", ".join([f"{p}주선({d})" for p, d in weekly_cross]))
    st.error("🚨 교차 발생 — " + " / ".join(msg_lines))
else:
    st.success("✅ 최근 교차 없음")

st.caption(f"마지막 업데이트: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
