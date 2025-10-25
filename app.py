import os
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from datetime import datetime

# ✅ 환경변수 (GitHub Actions / Streamlit Secrets)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8457877356:AAEam56w8yHqX-ymfGArr3BXAlhmjJB2pDA')
CHAT_ID = os.environ.get('CHAT_ID', '5877958037')

# ✅ Streamlit 설정
st.set_page_config(page_title="📈 이동평균선 교차 모니터링", layout="wide")
st.title("📈 이동평균선 교차 모니터링 대시보드")

# ✅ 사용자 설정
available_tickers = [
    "AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "AMD", "JPM", "V", "PLTR",
    "IONQ", "RGTI", "NTLA", "QUBT", "RKLB", "VRT", "COST", "META", "IBM",
]

st.sidebar.subheader("🔍 종목 선택")
selected_ticker = st.sidebar.selectbox("Select from list", available_tickers)

custom_ticker = st.sidebar.text_input("또는 직접 입력", "")

symbol = custom_ticker.strip().upper() if custom_ticker else selected_ticker

interval = st.sidebar.radio("Interval", ["1d", "1wk"], index=0)


# ✅ 데이터 조회 함수 (주봉은 10년 확장)
def get_price(symbol, interval):
    period = "3y" if interval == "1d" else "10y"

    df = yf.Ticker(symbol).history(period=period, interval=interval)

    if df.empty:
        return df

    df["MA200"] = df["Close"].rolling(200).mean()
    df["MA240"] = df["Close"].rolling(240).mean()
    df["MA365"] = df["Close"].rolling(365).mean()

    return df.dropna()


# ✅ 이동평균 교차 감지 함수
def detect_cross(df):
    crosses = []
    for ma in ["MA200", "MA240", "MA365"]:
        if df["Close"].iloc[-2] < df[ma].iloc[-2] and df["Close"].iloc[-1] >= df[ma].iloc[-1]:
            crosses.append((ma, "상향"))
        if df["Close"].iloc[-2] > df[ma].iloc[-2] and df["Close"].iloc[-1] <= df[ma].iloc[-1]:
            crosses.append((ma, "하향"))
    return crosses


# ✅ Telegram 전송
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message})


# ✅ 차트 표시 함수
def plot_chart(df, symbol):
    info = yf.Ticker(symbol).info
    company = info.get("longName", symbol)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close,
        name="Price"
    ))

    for ma, color in zip(["MA200","MA240","MA365"], ["blue","orange","green"]):
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma], mode="lines",
            name=ma, line=dict(color=color, width=1.5)
        ))

    fig.update_yaxes(
        autorange=True,
        range=[df.Low.min()*0.97, df.High.max()*1.03]
    )

    fig.update_layout(
        title=f"{company} ({symbol}) {interval.upper()} Chart",
        xaxis_rangeslider_visible=False,
        height=650,
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)


# ✅ 실행
df = get_price(symbol, interval)

if df.empty:
    st.error("⚠️ 데이터 조회 실패")
else:
    plot_chart(df, symbol)

    crosses = detect_cross(df)

    if crosses:
        msg = f"🚨 교차 발생: {symbol}\n" + "\n".join([f"{ma} - {dir}" for ma,dir in crosses])
        st.error(msg)
        send_telegram(msg)
    else:
        st.success("✅ 최근 교차 없음")

    st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
