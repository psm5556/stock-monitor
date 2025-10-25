import os
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

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
    return df.sort_values("Name")  # ✅ 기업명 기준 정렬

company_df = get_company_names(tickers)

# ✅ Sidebar — 선택 UI
st.sidebar.subheader("🔍 종목 선택")
options = {f"{row['Name']} ({row['Symbol']})": row['Symbol'] for _, row in company_df.iterrows()}
selected_key = st.sidebar.selectbox("Select Company", list(options.keys()))
selected_symbol = options[selected_key]

interval = st.sidebar.radio("차트 주기", ["일봉 (1d)", "주봉 (1wk)"])
interval_map = {"일봉 (1d)": "1d", "주봉 (1wk)": "1wk"}
selected_interval = interval_map[interval]


# ✅ 주가 + MA 계산
def load_data(symbol, interval):
    period = "3y" if interval == "1d" else "10y"
    df = yf.Ticker(symbol).history(period=period, interval=interval)

    if df.empty: return df

    for p in [200,240,365]:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()

    return df.dropna()


# ✅ 교차 감지 함수
def detect_cross(df):
    result = []
    for p in [200,240,365]:
        ma = f"MA{p}"
        if df["Close"].iloc[-2] < df[ma].iloc[-2] and df["Close"].iloc[-1] >= df[ma].iloc[-1]:
            result.append((ma, "상향"))
        if df["Close"].iloc[-2] > df[ma].iloc[-2] and df["Close"].iloc[-1] <= df[ma].iloc[-1]:
            result.append((ma, "하향"))
    return result


# ✅ Telegram 전송
def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID: return
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})


# ✅ 전체 종목 교차 검사 + 알림
cross_alerts = []
for _, row in company_df.iterrows():
    sym = row["Symbol"]
    df = load_data(sym, selected_interval)
    if df.empty: continue
    crosses = detect_cross(df)
    if crosses:
        msg = f"🚨 {row['Name']} ({sym})\n" + "\n".join([f"{ma} {d}" for ma,d in crosses])
        cross_alerts.append(msg)

if cross_alerts:
    for alert in cross_alerts:
        st.error(alert)
        send_telegram(alert)
else:
    st.success("✅ 전체 종목에 최근 이동평균선 교차 없음")


# ✅ 선택한 종목 차트만 표시
df = load_data(selected_symbol, selected_interval)

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
        fig.add_trace(go.Scatter(
            x=df.index, y=df[ma], mode="lines",
            name=ma, line=dict(color=color,width=1.8)
        ))

    fig.update_yaxes(
        autorange=True,
        range=[df.Low.min()*0.97, df.High.max()*1.03]
    )

    fig.update_layout(
        title=f"{company} ({selected_symbol}) — {selected_interval}",
        height=650, xaxis_rangeslider_visible=False,
        showlegend=True
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption(f"⏱ 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
