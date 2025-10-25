import os
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# ✅ 환경변수 기반 Telegram 설정(앱에서는 알림 미사용)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8457877356:AAEam56w8yHqX-ymfGArr3BXAlhmjJB2pDA')
CHAT_ID = os.environ.get('CHAT_ID', '5877958037')

st.set_page_config(page_title="📈 이동평균 감시", page_icon="📈")

# ✅ 제공된 전체 티커 적용
available_tickers = [
    "AAPL", "ABB", "ABCL", "ACHR", "AEP",
    "AES", "ALAB", "AMD", "AMZN", "ANET", "ARQQ", "ARRY", "ASML", "ASTS", "AVGO",
    "BA", "BAC", "BE", "BEP", "BLK", "BMNR", "BP", "BTQ", "BWXT", "C", "CARR",
    "CDNS", "CEG", "CFR.SW", "CGON", "CLPT", "COIN", "CONE", "CONL", "COP", "COST",
    "CRCL", "CRDO", "CRM", "CRSP", "CSCO", "CVX", "D", "DELL", "DNA", "DUK", "ED",
    "EMR", "ENPH", "ENR", "EOSE", "EQIX", "ETN", "EXC", "FLNC", "FSLR", "GEV", "GLD",
    "GOOGL", "GS", "HOOD", "HSBC", "HUBB", "IBM", "INTC", "IONQ", "JCI", "JOBY", "JPM",
    "KO", "LAES", "LMT", "LRCX", "LVMUY", "MA", "MPC", "MSFT", "MSTR", "NEE", "NGG",
    "NOC", "NRG", "NRGV", "NTLA", "NTRA", "NVDA", "OKLO", "ON", "ORCL", "OXY", "PCG",
    "PG", "PLTR", "PLUG", "PSTG", "PYPL", "QBTS", "QS", "QUBT", "QURE", "RGTI", "RKLB",
    "ROK", "SBGSY", "SEDG", "SHEL", "SIEGY", "SLDP", "SMR", "SNPS", "SO", "SOFI",
    "SPCE", "SPWR", "SQ", "SRE", "STEM", "TLT", "TMO", "TSLA", "TSM", "TWST", "UBT",
    "UNH", "V", "VLO", "VRT", "VST", "WMT", "HON", "TXG", "XOM", "ZPTA"
]


@st.cache_data
def load_price(symbol, interval="1d"):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="5y", interval=interval)
    if df.empty: return df
    df["MA200"] = df["Close"].rolling(200).mean()
    df["MA240"] = df["Close"].rolling(240).mean()
    df["MA365"] = df["Close"].rolling(365).mean()
    return df.dropna()

st.title("📈 이동평균 감시 대시보드")

# 선택 + 직접입력 모두 지원
ticker_selected = st.selectbox("티커 선택", options=available_tickers)
ticker_input = st.text_input("직접 티커 입력", value=ticker_selected).upper()
symbol = ticker_input if ticker_input else ticker_selected

interval = st.radio("차트 간격", ["1d (일봉)", "1wk (주봉)"])
interval = "1d" if "1d" in interval else "1wk"

df = load_price(symbol, interval)

if df.empty:
    st.error("데이터 조회 실패")
    st.stop()

# 회사명 가져오기
company = yf.Ticker(symbol).info.get("longName", symbol)

# 차트 생성 및 표시
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df.index,
    open=df["Open"],
    high=df["High"],
    low=df["Low"],
    close=df["Close"],
    name="Price"
))

for ma, color in [("MA200","blue"),("MA240","orange"),("MA365","green")]:
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df[ma],
        mode="lines",
        name=ma,
        line=dict(color=color, width=1.8)
    ))

fig.update_yaxes(
    autorange=True,
    range=[df["Low"].min()*0.98, df["High"].max()*1.02]
)

fig.update_layout(
    title=f"{company} ({symbol})",
    height=650,
    xaxis_rangeslider_visible=False
)

st.success("✅ 데이터 정상 로드")

st.plotly_chart(fig, use_container_width=True)



st.info("⚙ Telegram 알림은 monitor.py(자동 감시 스케줄러)에서 동작합니다.")
