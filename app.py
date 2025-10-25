import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import requests

# -------------------
# 📱 텔레그램 설정
# -------------------
TELEGRAM_TOKEN = "여기에_봇_토큰_입력"
TELEGRAM_CHAT_ID = "여기에_chat_id_입력"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.get(url, params=params)
    except Exception as e:
        st.error(f"텔레그램 전송 실패: {e}")

# -------------------
# 📊 데이터 다운로드 및 MA 계산
# -------------------
@st.cache_data(ttl=3600)
def get_data(symbol, interval="1d", period="2y"):
    data = yf.download(symbol, period=period, interval=interval, progress=False)

    # MultiIndex일 경우 첫 번째 레벨로 변경
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Close 컬럼이 존재하지 않으면 종료
    if "Close" not in data.columns:
        st.warning(f"{symbol}: 'Close' 데이터 없음")
        return pd.DataFrame()

    # 이동평균 계산
    for ma in [200, 240, 365]:
        data[f"MA{ma}"] = data["Close"].rolling(ma).mean()

    return data.dropna()

# -------------------
# ⚙️ Streamlit UI
# -------------------
st.set_page_config(page_title="📈 이동평균선 감시 알림", layout="wide")
st.title("📈 이동평균선 감시 대시보드 (일봉 + 주봉)")

stocks = ["AAPL", "MSFT", "NVDA", "GOOG", "AMZN", "META", "TSLA"]
alert_triggered = []

for symbol in stocks:
    st.subheader(f"📊 {symbol}")

    # 일봉 데이터
    daily = get_data(symbol, "1d", "2y")
    if not daily.empty:
        st.line_chart(daily[["Close", "MA200", "MA240", "MA365"]])

        last = daily.iloc[-1]
        for ma in ["MA200", "MA240", "MA365"]:
            if abs(last["Close"] - last[ma]) / last[ma] < 0.001:  # 0.1% 접근 시
                msg = f"⚠️ {symbol} 일봉이 {ma}({last[ma]:.2f})와 만남!"
                alert_triggered.append(msg)
    else:
        st.warning(f"{symbol} 일봉 데이터 없음")

    # 주봉 데이터
    weekly = get_data(symbol, "1wk", "5y")
    if not weekly.empty:
        st.line_chart(weekly[["Close", "MA200", "MA240", "MA365"]])

        last_w = weekly.iloc[-1]
        for ma in ["MA200", "MA240", "MA365"]:
            if abs(last_w["Close"] - last_w[ma]) / last_w[ma] < 0.001:
                msg = f"⚠️ {symbol} 주봉이 {ma}({last_w[ma]:.2f})와 만남!"
                alert_triggered.append(msg)
    else:
        st.warning(f"{symbol} 주봉 데이터 없음")

st.divider()

# -------------------
# 🔔 알림 전송
# -------------------
if alert_triggered:
    st.error("🚨 조건 충족! 알림 전송 중...")
    for msg in alert_triggered:
        send_telegram_message(msg)
        st.write(msg)
else:
    st.success("✅ 현재 모든 종목은 기준선과 거리 있음")

st.caption("10분마다 자동 실행 시, Streamlit Cloud Scheduler 또는 외부 cron으로 반복 가능")
