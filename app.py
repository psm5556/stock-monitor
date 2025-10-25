import os
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from datetime import datetime

BOT_TOKEN = os.environ.get('BOT_TOKEN', '8457877356:AAEam56w8yHqX-ymfGArr3BXAlhmjJB2pDA')
CHAT_ID = os.environ.get('CHAT_ID', '5877958037')

st.set_page_config(page_title="📈 MA Cross Monitor", layout="wide")
st.title("📈 이동평균선 교차 모니터링 시스템")

# ✅ 분석 대상 종목 리스트
TICKERS = [
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
def get_company_names(tickers):
    rows = []
    for t in tickers:
        info = yf.Ticker(t).info
        name = info.get("longName", info.get("shortName", t))
        rows.append((t, name))
    df = pd.DataFrame(rows, columns=["Symbol","Name"])
    return df.sort_values("Name")

company_df = get_company_names(TICKERS)

# ✅ 데이터 로딩 함수
def load_data(symbol, interval):
    period = "3y" if interval == "1d" else "10y"
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty:
        return df
    for p in [200,240,365]:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()
    return df.dropna()


# ✅ 교차 감지 함수
def detect_cross(df):
    if len(df) < 370:  # MA365 안정 보장
        return []

    results = []
    for p in [200,240,365]:
        ma = f"MA{p}"
        prev_c = df["Close"].iloc[-2]
        curr_c = df["Close"].iloc[-1]
        prev_m = df[ma].iloc[-2]
        curr_m = df[ma].iloc[-1]

        if prev_c < prev_m and curr_c >= curr_m:
            results.append((ma, "상향"))
        elif prev_c > prev_m and curr_c <= curr_m:
            results.append((ma, "하향"))
    return results


# ✅ Telegram 메시지 발송
def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})


# ✅ (A) 전체 종목 교차 감지 — 최초 실행 단 1회만 수행
if "checked_cross" not in st.session_state:
    st.session_state.checked_cross = False

if not st.session_state.checked_cross:
    daily_alerts = []
    weekly_alerts = []

    for _, row in company_df.iterrows():
        sym = row["Symbol"]

        df_day = load_data(sym, "1d")
        df_week = load_data(sym, "1wk")

        if not df_day.empty:
            cross_d = detect_cross(df_day)
            if cross_d:
                daily_alerts.append(f"{row['Name']} ({sym}) → " +
                                    ", ".join([f"{ma}:{d}" for ma,d in cross_d]))

        if not df_week.empty:
            cross_w = detect_cross(df_week)
            if cross_w:
                weekly_alerts.append(f"{row['Name']} ({sym}) → " +
                                     ", ".join([f"{ma}:{d}" for ma,d in cross_w]))

    if daily_alerts or weekly_alerts:
        st.error("🚨 이동평균 교차 감지 발생!")

        message = "🚨 이동평균 교차 감지 종목 리스트\n\n"

        if daily_alerts:
            message += "📅 Daily\n" + "\n".join(daily_alerts) + "\n\n"
        if weekly_alerts:
            message += "🗓 Weekly\n" + "\n".join(weekly_alerts)

        send_telegram(message)

        if daily_alerts:
            st.subheader("📅 Daily")
            for a in daily_alerts: st.warning(a)
        if weekly_alerts:
            st.subheader("🗓 Weekly")
            for a in weekly_alerts: st.warning(a)

    else:
        st.success("✅ 전체 종목에 교차 없음")

    st.session_state.checked_cross = True


# ✅ (B) 선택 종목 차트만 표시 — UI 반응
st.sidebar.subheader("📊 종목 선택")
options = {f"{row['Name']} ({row['Symbol']})": row['Symbol'] for _, row in company_df.iterrows()}
selected_key = st.sidebar.selectbox("Select Company", list(options.keys()))
selected_symbol = options[selected_key]

interval = st.sidebar.radio("차트 주기 선택", ["1d","1wk"], index=0)

df = load_data(selected_symbol, interval)

if df.empty:
    st.error("⚠ 데이터 조회 실패")
else:
    company = yf.Ticker(selected_symbol).info.get("longName", selected_symbol)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close,
        name="Price"
    ))

    for ma,color in zip(["MA200","MA240","MA365"],["blue","orange","green"]):
        fig.add_trace(go.Scatter(x=df.index, y=df[ma], mode="lines",
                                 name=ma, line=dict(color=color, width=1.8)))

    fig.update_yaxes(autorange=True)

    fig.update_layout(
        title=f"{company} ({selected_symbol}) — {interval}",
        height=650,
        xaxis_rangeslider_visible=False,
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)

st.caption(f"⏱ 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
