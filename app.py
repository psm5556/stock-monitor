import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import requests
import time

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
# 📊 데이터 불러오기 (캐시)
# -------------------
@st.cache_data(ttl=3600)
def get_data(symbol):
    data = yf.download(symbol, period="2y")
    if data.empty:
        return pd.DataFrame()
    data["MA200"] = data["Close"].rolling(200).mean()
    data["MA240"] = data["Close"].rolling(240).mean()
    data["MA365"] = data["Close"].rolling(365).mean()
    return data

@st.cache_data(ttl=3600)
def get_weekly_data(symbol):
    data = yf.download(symbol, period="5y", interval="1wk")
    if data.empty:
        return pd.DataFrame()
    data["MA200"] = data["Close"].rolling(200).mean()
    data["MA240"] = data["Close"].rolling(240).mean()
    data["MA365"] = data["Close"].rolling(365).mean()
    return data

# -------------------
# ⚙️ Streamlit UI
# -------------------
st.set_page_config(page_title="📈 이동평균선 감시 알림", layout="wide")
st.title("📈 이동평균선 감시 대시보드 (일봉 + 주봉)")

stocks = ["AAPL", "MSFT", "NVDA", "GOOG", "AMZN", "META", "TSLA"]  # 미리 등록된 기업 리스트
alert_triggered = []

for symbol in stocks:
    st.subheader(f"📊 {symbol}")

    # 일봉 데이터
    daily = get_data(symbol)
    if not daily.empty:
        st.line_chart(daily[["Close", "MA200", "MA240", "MA365"]].dropna())
        last = daily.iloc[-1]
        for ma in ["MA200", "MA240", "MA365"]:
            if abs(last["Close"] - last[ma]) / last[ma] < 0.001:  # 0.1% 이내 접근 시
                msg = f"⚠️ {symbol} 일봉이 {ma}({last[ma]:.2f})와 만남!"
                alert_triggered.append(msg)
    else:
        st.warning(f"{symbol} 일봉 데이터 없음")

    # 주봉 데이터
    weekly = get_weekly_data(symbol)
    if not weekly.empty:
        st.line_chart(weekly[["Close", "MA200", "MA240", "MA365"]].dropna())
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
