import streamlit as st
import pandas as pd
import yfinance as yf
import datetime as dt

st.set_page_config(page_title="📈 이동평균선 교차 모니터링", layout="wide")
st.title("📈 이동평균선 교차 모니터링 대시보드 (Daily & Weekly)")

# 미리 지정된 모니터링 대상
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
def get_data(ticker, interval="1d"):
    t = yf.Ticker(ticker)
    df = t.history(period="5y", interval=interval, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if "Close" not in df.columns:
        return pd.DataFrame()
    for p in PERIODS:
        df[f"MA{p}"] = df["Close"].rolling(p, min_periods=1).mean()
    return df.dropna(subset=["Close"])

def detect_cross(data):
    cross = []
    if len(data) < 2:
        return cross
    for p in PERIODS:
        col = f"MA{p}"
        if col not in data.columns:
            continue
        if data["Close"].iloc[-2] < data[col].iloc[-2] and data["Close"].iloc[-1] >= data[col].iloc[-1]:
            cross.append((p, "상향"))
        elif data["Close"].iloc[-2] > data[col].iloc[-2] and data["Close"].iloc[-1] <= data[col].iloc[-1]:
            cross.append((p, "하향"))
    return cross

# ✅ 전체 종목 분석
results = []
for ticker in TICKERS:
    daily = get_data(ticker, "1d")
    weekly = get_data(ticker, "1wk")
    daily_cross = detect_cross(daily)
    weekly_cross = detect_cross(weekly)
    if daily_cross or weekly_cross:
        result = {"종목": ticker, "일단위": daily_cross, "주단위": weekly_cross}
        results.append(result)

# ✅ 결과 표시
if results:
    st.error("🚨 교차 발생 종목 감지됨!")
    for r in results:
        msg = f"**{r['종목']}** → "
        if r["일단위"]:
            msg += "일단위: " + ", ".join([f"{p}일선({d})" for p, d in r["일단위"]]) + " / "
        if r["주단위"]:
            msg += "주단위: " + ", ".join([f"{p}주선({d})" for p, d in r["주단위"]])
        st.write(msg)
else:
    st.success("✅ 최근 교차 없음 (전체 종목 기준)")

st.caption(f"마지막 업데이트: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
