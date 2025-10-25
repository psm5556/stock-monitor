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
def get_company_info():
    data=[]
    for t in tickers:
        info = yf.Ticker(t).info
        name = info.get("longName", info.get("shortName", t))
        data.append((t,name))
    df = pd.DataFrame(data,columns=["Symbol","Name"])
    return df.sort_values("Name") # ✅ 기업명 정렬

company_df = get_company_info()

# ✅ 종목 선택 UI
st.sidebar.subheader("🎯 차트 종목 선택")
options = {f"{row['Name']} ({row['Symbol']})": row['Symbol'] for _,row in company_df.iterrows()}
selected_key = st.sidebar.selectbox("회사 선택", list(options.keys()))
selected_symbol = options[selected_key]

interval = st.sidebar.radio("차트 주기", ["일봉 (1d)","주봉 (1wk)"])
interval_map = {"일봉 (1d)":"1d","주봉 (1wk)":"1wk"}
chart_interval = interval_map[interval]

# ✅ 데이터 로딩
def load_data(symbol, interval):
    period = "3y" if interval == "1d" else "10y"
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty: return df
    df["MA200"] = df.Close.rolling(200).mean()
    df["MA240"] = df.Close.rolling(240).mean()
    df["MA365"] = df.Close.rolling(365).mean()
    return df.dropna()


# ✅ 교차 감지
def detect_cross(df):
    if len(df) < 370: # MA365 최소 보장
        return []

    result=[]
    for ma in ["MA200","MA240","MA365"]:
        prev_close, curr_close = df.Close.iloc[-2], df.Close.iloc[-1]
        prev_ma, curr_ma = df[ma].iloc[-2], df[ma].iloc[-1]

        if prev_close < prev_ma and curr_close >= curr_ma:
            result.append(f"{ma} 상향")
        elif prev_close > prev_ma and curr_close <= curr_ma:
            result.append(f"{ma} 하향")

    return result


# ✅ Telegram 발송
def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})


# ✅ 전체 교차 감지 처리 (일봉+주봉 모두)
def process_cross_detection():
    alerts_daily=[]
    alerts_weekly=[]

    for _, row in company_df.iterrows():
        sym, name = row["Symbol"], row["Name"]

        # 일봉
        df_d = load_data(sym,"1d")
        if not df_d.empty:
            crosses = detect_cross(df_d)
            if crosses:
                alerts_daily.append(f"📅{name} ({sym}):\n" + "\n".join(crosses))

        # 주봉
        df_w = load_data(sym,"1wk")
        if not df_w.empty:
            crosses = detect_cross(df_w)
            if crosses:
                alerts_weekly.append(f"🗓️{name} ({sym}):\n" + "\n".join(crosses))

    # ✅ Streamlit 표시 & Telegram 1회 발송 메시지 구성
    if alerts_daily or alerts_weekly:
        st.error("🚨 이동평균선 교차 감지!")

        if alerts_daily:
            st.subheader("📅 일봉 교차 종목")
            for x in alerts_daily: st.warning(x)

        if alerts_weekly:
            st.subheader("🗓️ 주봉 교차 종목")
            for x in alerts_weekly: st.warning(x)

        telegram_message = "🚨 이동평균선 교차 감지\n\n"
        if alerts_daily:
            telegram_message += "📅 일봉\n" + "\n\n".join(alerts_daily) + "\n\n"
        if alerts_weekly:
            telegram_message += "🗓️ 주봉\n" + "\n\n".join(alerts_weekly)

        send_telegram(telegram_message)

    else:
        st.success("✅ 전체 종목에 교차 없음")


# ✅ 교차 감지 실행 (차트와 독립)
process_cross_detection()


# ✅ 선택한 종목 차트 표시
df_chart = load_data(selected_symbol, chart_interval)
if df_chart.empty:
    st.error("⚠ 데이터 부족")
else:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart.Open, high=df_chart.High,
        low=df_chart.Low, close=df_chart.Close,
        name="Price"
    ))

    for ma,color in zip(["MA200","MA240","MA365"],
                        ["blue","orange","green"]):
        fig.add_trace(go.Scatter(
            x=df_chart.index, y=df_chart[ma],
            mode="lines", name=ma,
            line=dict(color=color,width=1.7)
        ))

    fig.update_yaxes(range=[df_chart.Low.min()*0.97, df_chart.High.max()*1.03])
    fig.update_layout(title=f"{selected_key} — {chart_interval}",
                      height=650,showlegend=True,
                      xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

st.caption(f"⏱ 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
