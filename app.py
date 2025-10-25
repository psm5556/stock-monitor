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
tickers = [
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
    data = []
    for t in tickers:
        info = yf.Ticker(t).info
        name = info.get("longName", info.get("shortName", t))
        data.append((t, name))
    df = pd.DataFrame(data, columns=["Symbol","Name"])
    return df.sort_values("Name")

company_df = get_company_names(tickers)

def load_data(symbol, interval):
    period = "3y" if interval == "1d" else "10y"
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty: return df
    for p in [200,240,365]:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()
    return df.dropna()

def detect_cross(df):
    if len(df) < 370: return []  # 안정성 보장
    results = []
    for p in [200,240,365]:
        ma = f"MA{p}"
        prev_c = df["Close"].iloc[-2]
        cur_c = df["Close"].iloc[-1]
        prev_m = df[ma].iloc[-2]
        cur_m = df[ma].iloc[-1]
        if prev_c < prev_m and cur_c >= cur_m:
            results.append((ma, "상향"))
        elif prev_c > prev_m and cur_c <= cur_m:
            results.append((ma, "하향"))
    return results

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})


# ✅ (1) 전체 교차 감지 — 일봉 & 주봉
daily_alerts = []
weekly_alerts = []

for _, row in company_df.iterrows():
    sym = row["Symbol"]
    df_day = load_data(sym, "1d")
    df_week = load_data(sym, "1wk")

    if not df_day.empty:
        c1 = detect_cross(df_day)
        if c1:
            formatted = ", ".join([f"{ma}:{d}" for ma,d in c1])
            daily_alerts.append(f"{row['Name']} ({sym})\n{formatted}")

    if not df_week.empty:
        c2 = detect_cross(df_week)
        if c2:
            formatted = ", ".join([f"{ma}:{d}" for ma,d in c2])
            weekly_alerts.append(f"{row['Name']} ({sym})\n{formatted}")


# ✅ Streamlit에 요약 표시
if daily_alerts or weekly_alerts:
    st.error("🚨 이동평균선 교차 감지 종목 존재!")

    if daily_alerts:
        st.subheader("📅 Daily (일봉) 교차 감지")
        for alert in daily_alerts:
            st.warning(alert)

    if weekly_alerts:
        st.subheader("🗓 Weekly (주봉) 교차 감지")
        for alert in weekly_alerts:
            st.warning(alert)

    full_msg = "🚨 이동평균선 교차 감지\n\n"
    if daily_alerts:
        full_msg += "📅 Daily\n" + "\n\n".join(daily_alerts) + "\n\n"
    if weekly_alerts:
        full_msg += "🗓 Weekly\n" + "\n\n".join(weekly_alerts)

    send_telegram(full_msg)

else:
    st.success("✅ 전체 종목에 교차 없음")


# ✅ (2) UI — 선택 종목만 차트 표시
st.sidebar.subheader("📊 종목 선택")

options = {f"{row['Name']} ({row['Symbol']})": row['Symbol'] for _, row in company_df.iterrows()}
selected_key = st.sidebar.selectbox("종목 선택", list(options.keys()))
selected_symbol = options[selected_key]

interval = st.sidebar.radio("차트 주기", ["1d","1wk"], index=0)

df = load_data(selected_symbol, interval)

if df.empty:
    st.error("⚠ 데이터 조회 실패 또는 데이터 부족")
else:
    company = yf.Ticker(selected_symbol).info.get("longName", selected_symbol)

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close,
        name="Price"
    ))

    for ma,color in zip(["MA200","MA240","MA365"],["blue","orange","green"]):
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma], mode="lines",
            name=ma, line=dict(color=color,width=1.8)
        ))

    fig.update_yaxes(
        autorange=True,
        range=[df.Low.min()*0.97, df.High.max()*1.03]
    )

    fig.update_layout(
        title=f"{selected_key} — {interval}",
        height=650, xaxis_rangeslider_visible=False,
        showlegend=True
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption(f"⏱ 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
