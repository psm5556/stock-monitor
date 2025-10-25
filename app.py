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


# ---------------------------
# ✅ 데이터 로딩 함수
# ---------------------------
@st.cache_data(ttl=3600)
def load_stock_data(symbol="AAPL", period="1y"):
    try:
        df = yf.download(symbol, period=period, interval="1d", auto_adjust=True, progress=False)
        if df.empty:
            return pd.DataFrame()
        return df
    except:
        return pd.DataFrame()

# ✅ 기업명 자동 로딩
@st.cache_data(ttl=86400)
def get_company_name(symbol):
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName", info.get("shortName", symbol))
    except:
        return symbol

# ✅ 이동평균 계산
def add_mas(df):
    for w in [200, 240, 365]:
        df[f"MA{w}"] = df["Close"].rolling(window=w).mean()
    return df

# ✅ 교차 감지
def detect_cross(df):
    result = {}
    for w in [200, 240, 365]:
        now = df["Close"].iloc[-1]
        prev = df["Close"].iloc[-2]
        ma_now = df[f"MA{w}"].iloc[-1]
        ma_prev = df[f"MA{w}"].iloc[-2]

        if prev < ma_prev and now > ma_now:
            result[w] = "골든크로스 ✅"
        elif prev > ma_prev and now < ma_now:
            result[w] = "데드크로스 ⚠️"
        else:
            result[w] = "교차 없음"
    return result

# ✅ Plotly 차트 (동적 축)
def draw_chart(df, title):
    cols = ["Close", "MA200", "MA240", "MA365"]
    cols = [c for c in cols if c in df.columns]
    min_v = df[cols].min().min()
    max_v = df[cols].max().max()
    margin = (max_v - min_v) * 0.05

    fig = go.Figure()
    for c in cols:
        fig.add_trace(go.Scatter(x=df.index, y=df[c], mode="lines", name=c))

    fig.update_layout(
        title=title,
        yaxis=dict(range=[min_v - margin, max_v + margin]),
        height=500,
        showlegend=True
    )
    st.plotly_chart(fig, use_container_width=True)


# ==================================================
# ✅ UI 구성
# ==================================================
st.title("📈 200/240/365 이동평균 감시 시스템")

# ✅ 리스트 + 직접 입력 모두 가능
col1, col2 = st.columns([2, 1])
with col1:
    selected_ticker = st.selectbox("📊 티커 선택", available_tickers)
with col2:
    input_ticker = st.text_input("직접 입력 (선택보다 우선 적용)", "")

symbol = input_ticker.upper().strip() if input_ticker else selected_ticker
period = st.selectbox("📅 조회 기간", ["6mo", "1y", "2y", "5y"], index=1)

if st.button("🔍 조회"):
    with st.spinner("데이터 로딩 중..."):
        df = load_stock_data(symbol, period)

    if df.empty:
        st.error("📌 데이터 없음. 티커를 확인해주세요.")
        st.stop()

    df = add_mas(df)
    company = get_company_name(symbol)
    status = detect_cross(df)

    st.subheader(f"📌 분석 결과: {company} ({symbol})")
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("200일선", status[200])
    col_b.metric("240일선", status[240])
    col_c.metric("365일선", status[365])

    st.subheader("📈 차트")
    draw_chart(df, f"{company} ({symbol}) 가격 / 이동평균선")

st.info("⚙ Telegram 알림은 monitor.py(자동 감시 스케줄러)에서 동작합니다.")
