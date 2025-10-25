# app.py
import streamlit as st
import pandas as pd
import yfinance as yf
import datetime as dt

st.set_page_config(page_title="📈 이동평균선 교차 모니터링", layout="wide")
st.title("📈 이동평균선 교차 모니터링 (Daily & Weekly)")

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
] # 25.10.25
PERIODS = [200, 240, 365]


@st.cache_data(ttl=3600)
def get_company_name(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName") or ticker
    except:
        return ticker


@st.cache_data(ttl=3600)
def get_data(ticker, interval="1d"):
    df = yf.download(ticker, period="2y", interval=interval, auto_adjust=True, progress=False)
    if df.empty:
        return df
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    if "Close" not in df.columns:
        return pd.DataFrame()
    for p in PERIODS:
        df[f"MA{p}"] = df["Close"].rolling(p, min_periods=p).mean()
    return df.dropna()


def detect_cross(df):
    result = []
    if len(df) < 2:
        return result
    prev, curr = df.iloc[-2], df.iloc[-1]
    for p in PERIODS:
        col = f"MA{p}"
        if col in df.columns:
            if prev["Close"] < prev[col] and curr["Close"] >= curr[col]:
                result.append((p, "상향"))
            elif prev["Close"] > prev[col] and curr["Close"] <= curr[col]:
                result.append((p, "하향"))
    return result


st.subheader("📌 전체 종목 교차 요약")
summary_rows = []

for t in TICKERS:
    daily = get_data(t, "1d")
    weekly = get_data(t, "1wk")
    name = get_company_name(t)
    daily_cross = detect_cross(daily)
    weekly_cross = detect_cross(weekly)

    summary_rows.append({
        "Ticker": t,
        "Name": name,
        "Daily": ", ".join([f"{p}일선({d})" for p, d in daily_cross]) if daily_cross else "",
        "Weekly": ", ".join([f"{p}주선({d})" for p, d in weekly_cross]) if weekly_cross else "",
    })

df_summary = pd.DataFrame(summary_rows)
st.dataframe(df_summary, use_container_width=True, hide_index=True)

st.divider()

# 🎯 선택 종목 차트
selected = st.selectbox("📊 종목 선택", TICKERS)
daily_sel = get_data(selected, "1d")
weekly_sel = get_data(selected, "1wk")

import plotly.graph_objects as go

def draw_chart(df, title):
    if df.empty:
        st.warning("데이터 없음")
        return

    cols = ["Close", "MA200", "MA240", "MA365"]
    cols = [c for c in cols if c in df.columns]
    if not cols:
        st.warning("표시할 데이터 없음")
        return

    # ✅ y축 범위 자동 설정: min-max 여유를 2~5% 확보
    min_val = df[cols].min().min()
    max_val = df[cols].max().max()
    margin = (max_val - min_val) * 0.05
    y_min, y_max = min_val - margin, max_val + margin

    fig = go.Figure()

    for c in cols:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df[c],
            mode="lines",
            name=c,
            line=dict(width=2)
        ))

    fig.update_layout(
        title=title,
        xaxis_title="날짜",
        yaxis_title="가격",
        height=450,
        yaxis=dict(range=[y_min, y_max]),
        margin=dict(l=40, r=40, t=50, b=40),
        showlegend=True
    )

    st.plotly_chart(fig, use_container_width=True)


draw_chart(daily_sel, "📅 Daily Chart")
draw_chart(weekly_sel, "🗓️ Weekly Chart")

st.caption(f"🕒 마지막 업데이트: {dt.datetime.now():%Y-%m-%d %H:%M:%S}")
