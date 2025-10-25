# app.py
import os
import time
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime

# ───────────────────────────────────────────────────────────────────────────────
# 기본 설정
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="📈 MA 터치 기반 분할매수 모니터", layout="wide")
st.title("📈 장기 이동평균(MA200/240/365) 터치 기반 분할매수 모니터 (일봉·주봉)")

# 환경변수에서 토큰/챗아이디 로드 (사용자 요청값을 기본값으로 유지)
# BOT_TOKEN = os.environ.get('BOT_TOKEN', '8457877356:AAEam56w8yHqX-ymfGArr3BXAlhmjJB2pDA')
# CHAT_ID = os.environ.get('CHAT_ID', '5877958037')

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 감시 대상 티커(요청된 목록)
TICKERS  = [
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

# ✅ 회사명 자동 수집
@st.cache_data
def get_company_df():
    company_map = {}
    for t in TICKERS:
        try:
            info = requests.get(
                f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{t}?modules=price"
            ).json()
            name = info["quoteSummary"]["result"][0]["price"].get("shortName", t)
            company_map[t] = name
        except:
            company_map[t] = t
        time.sleep(0.3)
    df = pd.DataFrame({"Symbol": list(company_map.keys()), "Company": list(company_map.values())})
    return df.sort_values("Company")


company_df = get_company_df()


# ✅ 데이터 가져오기 (일봉 / 주봉)
@st.cache_data(ttl=3600)
def get_price(ticker, interval="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": interval, "range": "2y"}
    r = requests.get(url, params=params).json()

    if "chart" not in r or r["chart"].get("error"):
        return None

    res = r["chart"]["result"][0]
    timestamps = res["timestamp"]
    prices = res["indicators"]["quote"][0]
    df = pd.DataFrame(prices)
    df["Date"] = pd.to_datetime(timestamps, unit="s")
    df.set_index("Date", inplace=True)

    for ma in [200,240,365]:
        df[f"MA{ma}"] = df["close"].rolling(ma).mean()

    df.rename(columns={"close": "Close", "open": "Open", "high": "High", "low": "Low"}, inplace=True)
    return df.dropna()


# ✅ 매수 신호 감지 로직
def detect_buy_signal(df_day, df_week, symbol, company):
    score = 0
    touch_list = []

    if len(df_day) < 370:  # 데이터 부족시 제외
        return None

    for ma, pts in [(365,60),(240,45),(200,30)]:
        col = f"MA{ma}"
        if col not in df_day.columns: continue

        prev = df_day["Close"].iloc[-2] - df_day[col].iloc[-2]
        curr = df_day["Close"].iloc[-1] - df_day[col].iloc[-1]

        # ✅ 하락 속 MA 접근만 인정
        if prev > 0 and curr <= 0:
            score += pts
            touch_list.append(f"{ma}일선")

    # ✅ 장기 하락 추세
    if df_day["Close"].iloc[-1] < df_day["MA200"].iloc[-1]:
        score += 25

    # ✅ 주봉 접근 시
    for ma, pts in [(365,10),(240,10),(200,10)]:
        col = f"MA{ma}"
        if col in df_week.columns:
            prev_w = df_week["Close"].iloc[-2] - df_week[col].iloc[-2]
            curr_w = df_week["Close"].iloc[-1] - df_week[col].iloc[-1]
            if prev_w > 0 and curr_w <= 0:
                score += pts

    # ✅ 일 + 주봉 동시 강도 보정
    if score >= 90:
        score += 20

    if score >= 80:
        return {
            "symbol": symbol,
            "company": company,
            "score": score,
            "touch": ", ".join(touch_list)
        }
    return None


# ✅ Telegram 메시지
def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    return requests.post(url, json=payload).status_code == 200


# ✅ 앱 시작 시 교차 감지 & 알림 1회 실행
if "alert_sent" not in st.session_state:
    strong = []
    medium = []

    for _, row in company_df.iterrows():
        symbol = row.Symbol
        company = row.Company

        df_day = get_price(symbol, "1d")
        df_week = get_price(symbol, "1wk")

        if df_day is None or df_week is None:
            continue

        signal = detect_buy_signal(df_day, df_week, symbol, company)
        if signal:
            if signal["score"] >= 100:
                strong.append(signal)
            else:
                medium.append(signal)

    if strong or medium:
        msg = "<b>📉 저점 매수 기회 탐지!</b>\n\n"

        if strong:
            msg += "🔥 <b>강력 매수 (100점 이상)</b>\n"
            for s in strong:
                msg += f"• {s['company']} ({s['symbol']}) — {s['touch']} ({s['score']}점)\n"
            msg += "\n"

        if medium:
            msg += "⚠️ <b>관망 매수 (80~99점)</b>\n"
            for s in medium:
                msg += f"• {s['company']} ({s['symbol']}) — {s['touch']} ({s['score']}점)\n"

        send_telegram(msg)

    st.session_state.alert_sent = True


# ✅ UI – 종목 차트 (선택 시만 업데이트)
st.title("📉 저점 매수 레이더 – 장기선 기반 분할매수 시스템")

selected_company = st.selectbox("종목 선택", company_df["Company"])
selected_symbol = company_df.loc[company_df["Company"] == selected_company, "Symbol"].values[0]

df_day = get_price(selected_symbol, "1d")

st.subheader(f"{selected_company} ({selected_symbol}) 일봉")
st.line_chart(df_day[["Close","MA200","MA240","MA365"]].dropna())

