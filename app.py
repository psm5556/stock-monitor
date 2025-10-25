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
def get_company_name(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName") or ticker
    except Exception:
        return ticker

@st.cache_data(ttl=3600)
def get_data(ticker, interval="1d"):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="5y", interval=interval, auto_adjust=True)

        # ✅ MultiIndex 방어
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # ✅ Close 존재 확인
        if "Close" not in df.columns or df.empty:
            return pd.DataFrame()

        # ✅ 이동평균 계산
        for p in PERIODS:
            df[f"MA{p}"] = df["Close"].rolling(p, min_periods=1).mean()

        return df.dropna(subset=["Close"]).tail(500)

    except Exception as e:
        st.warning(f"{ticker} 데이터 로드 실패: {e}")
        return pd.DataFrame()

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

# ✅ 기업명 자동 표시
company_names = {t: get_company_name(t) for t in TICKERS}
display_options = [f"{company_names[t]} ({t})" for t in TICKERS]

col1, col2 = st.columns([1, 3])
with col1:
    selection = st.selectbox("📊 종목 선택", display_options)
    selected = selection.split("(")[-1].replace(")", "")
with col2:
    st.write("최근 주가 및 이동평균선 (일/주 단위)")

# ✅ 일간 데이터
daily = get_data(selected, "1d")
if not daily.empty and "Close" in daily.columns:
    st.subheader("📅 일 단위 (Daily) 차트")
    cols = [c for c in ["Close", "MA200", "MA240", "MA365"] if c in daily.columns]
    st.line_chart(daily[cols])
else:
    st.warning("일 단위 데이터가 없습니다.")

# ✅ 주간 데이터
weekly = get_data(selected, "1wk")
if not weekly.empty and "Close" in weekly.columns:
    st.subheader("🗓️ 주 단위 (Weekly) 차트")
    cols = [c for c in ["Close", "MA200", "MA240", "MA365"] if c in weekly.columns]
    st.line_chart(weekly[cols])
else:
    st.warning("주 단위 데이터가 없습니다.")

# ✅ 교차 감지
daily_cross = detect_cross(daily)
weekly_cross = detect_cross(weekly)

if daily_cross or weekly_cross:
    msg_lines = []
    if daily_cross:
        msg_lines.append("일 단위: " + ", ".join([f"{p}일선({d})" for p, d in daily_cross]))
    if weekly_cross:
        msg_lines.append("주 단위: " + ", ".join([f"{p}주선({d})" for p, d in weekly_cross]))
    st.error("🚨 교차 발생 — " + " / ".join(msg_lines))
else:
    st.success("✅ 최근 교차 없음")

st.caption(f"마지막 업데이트: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
