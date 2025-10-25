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
    try:
        ticker_obj = yf.Ticker(ticker)
        data = ticker_obj.history(period="2y", interval=interval)
        
        # ✅ MultiIndex 방어
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        # ✅ NaN 및 컬럼 확인
        if data.empty or "Close" not in data.columns:
            st.warning(f"{ticker} 데이터 없음")
            return pd.DataFrame()

        # ✅ 이동평균선 직접 계산
        for p in [200, 240, 365]:
            data[f"MA{p}"] = data["Close"].rolling(p).mean()
        
        return data.dropna()
    except Exception as e:
        st.error(f"{ticker} 데이터 수집 실패: {e}")
        return pd.DataFrame()

col1, col2 = st.columns([1, 3])
with col1:
    selected = st.selectbox("📊 종목 선택", TICKERS)
    st.write("모니터링 대상 티커는 app.py 내부의 TICKERS 리스트를 수정하여 변경할 수 있습니다.")
with col2:
    st.write("최근 주가 및 이동평균선 (일/주 단위)")

# 안전한 차트 렌더링 함수
def safe_line_chart(df, label):
    if df is None or df.empty:
        st.warning(f"{label}: 데이터가 없습니다.")
        return
    cols = [c for c in ["Close", "MA200", "MA240", "MA365"] if c in df.columns]
    if len(cols) < 2:
        st.info(f"{label}: 표시할 유효 컬럼이 부족합니다.")
        return
    st.subheader(label)
    st.line_chart(df[cols].dropna())

# 일간 데이터
daily = get_data(selected, "1d")
safe_line_chart(daily, "📅 일 단위 (Daily) 차트")

# 주간 데이터
weekly = get_data(selected, "1wk")
safe_line_chart(weekly, "🗓️ 주 단위 (Weekly) 차트")

# 교차 감지 함수
def detect_cross(data):
    cross = []
    # 최근 2개 캔들(바)을 비교하여 교차(상향/하향)를 판단합니다.
    if data is None or data.empty or len(data) < 2:
        return cross
    for p in PERIODS:
        col = f"MA{p}"
        if col not in data.columns:
            continue
        prev_close = data['Close'].iloc[-2]
        last_close = data['Close'].iloc[-1]
        prev_ma = data[col].iloc[-2]
        last_ma = data[col].iloc[-1]
        # NaN 방어
        if pd.isna(prev_ma) or pd.isna(last_ma):
            continue
        if prev_close < prev_ma and last_close >= last_ma:
            cross.append((p, '상향'))
        elif prev_close > prev_ma and last_close <= last_ma:
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
