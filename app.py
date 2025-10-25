import os
import math
import requests
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

st.set_page_config(page_title="📈 장기 MA 접근 모니터", layout="wide")
st.title("📈 장기(200/240/365) 이동평균선 접근 모니터 — 일봉 & 주봉")

st.caption("목적: 하락 추세에서 장기 MA(200/240/365)에 접근/하향이탈하는 순간을 포착하여 저점 분할매수 기회를 찾습니다.")

available_tickers = [
    "AAPL", "ABCL", "ACHR", "AEP", "AES", "ALAB", "AMD", "AMZN", "ANET", "ARQQ", "ARRY", "ASML", "ASTS", "AVGO",
    "BA", "BAC", "BE", "BEP", "BLK", "BMNR", "BP", "BTQ", "BWXT", "C", "CARR", "CDNS", "CEG", "CFR.SW", "CGON",
    "CLPT", "COIN", "CONL", "COP", "COST", "CRCL", "CRDO", "CRM", "CRSP", "CSCO", "CVX", "D", "DELL", "DNA", "DUK",
    "ED", "EMR", "ENPH", "ENR", "EOSE", "EQIX", "ETN", "EXC", "FLNC", "FSLR", "GEV", "GLD", "GOOGL", "GS", "HOOD",
    "HSBC", "HUBB", "IBM", "INTC", "IONQ", "JCI", "JOBY", "JPM", "KO", "LAES", "LMT", "LRCX", "LVMUY", "MA", "MPC",
    "MSFT", "MSTR", "NEE", "NGG", "NOC", "NRG", "NRGV", "NTLA", "NTRA", "NVDA", "OKLO", "ON", "ORCL", "OXY", "PCG",
    "PG", "PLTR", "PLUG", "PSTG", "PYPL", "QBTS", "QS", "QUBT", "QURE", "RGTI", "RKLB", "ROK", "SBGSY", "SEDG",
    "SHEL", "SIEGY", "SLDP", "SMR", "SNPS", "SO", "SOFI", "SPCE", "SPWR", "XYZ", "SRE", "STEM", "TLT",
    "TMO", "TSLA", "TSM", "TWST", "UBT", "UNH", "V", "VLO", "VRT", "VST", "WMT", "HON", "TXG", "XOM", "ZPTA"
]

@st.cache_data(ttl=86400)
def get_company_name(symbol):
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except:
        return symbol


@st.cache_data(ttl=3600)
def get_price(symbol, interval="1d"):
    period = "10y" if interval == "1wk" else "3y"
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df is None or df.empty:
        return None

    df = df[["Open","High","Low","Close","Volume"]].copy()

    for p in MA_LIST:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()

    df.dropna(inplace=True)
    return df if not df.empty else None


def is_downtrend(df, lookback=20):
    if len(df) < lookback + 1:
        return False
    close_slope = (df["Close"].iloc[-1] - df["Close"].iloc[-lookback]) / lookback
    return close_slope < 0


def detect_ma_touch(df):
    result = {"근접": [], "하향이탈": []}
    last = df.iloc[-1]

    for p in MA_LIST:
        ma_value = last[f"MA{p}"]
        if pd.isna(ma_value):
            continue

        close = last["Close"]
        gap = (close - ma_value) / ma_value

        if abs(gap) <= 0.005:
            result["근접"].append((p, round(gap*100,2)))
        elif close < ma_value:
            result["하향이탈"].append((p, round(gap*100,2)))

    return result


def detect_signal(symbol):
    name = get_company_name(symbol)
    out = {"symbol":symbol,"name":name,
           "Daily":{"근접":[],"하향이탈":[]},
           "Weekly":{"근접":[],"하향이탈":[]}}

    for interval, key in [("1d","Daily"),("1wk","Weekly")]:
        df = get_price(symbol, interval)
        if df is not None and is_downtrend(df):
            res = detect_ma_touch(df)
            if res:
                out[key]["근접"] += res["근접"]
                out[key]["하향이탈"] += res["하향이탈"]

    return out


def build_alert_message(results):
    ts = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    msg = f"📬 [수동] 장기 MA 감지 결과 ({ts})\n"

    sections = [
        ("📅 Daily — 근접", "Daily", "근접"),
        ("📅 Daily — 하향이탈","Daily","하향이탈"),
        ("🗓 Weekly — 근접","Weekly","근접"),
        ("🗓 Weekly — 하향이탈","Weekly","하향이탈"),
    ]

    any_signal = False
    for title, k1, k2 in sections:
        block = ""
        for r in results:
            rows = r[k1][k2]
            if rows:
                any_signal = True
                block += f"- {r['name']} ({r['symbol']})\n"
                for p, gap in rows:
                    emoji = "✅" if k2=="근접" else "🔻"
                    block += f"   {emoji} MA{p} {k2} ({gap:+.2f}%)\n"
        if block:
            msg += f"\n{title}\n{block}"

    if not any_signal:
        msg += "\n감지된 종목 없음"
    return msg


def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ BOT_TOKEN 또는 CHAT_ID 없음")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id":CHAT_ID,"text":text})
    return r.status_code==200


# 초기 스캔 + 메시지
results = []
for sym in available_tickers:
    r = detect_signal(sym)
    if any([r["Daily"]["근접"], r["Daily"]["하향이탈"], r["Weekly"]["근접"], r["Weekly"]["하향이탈"]]):
        results.append(r)

if "sent" not in st.session_state:
    st.session_state["sent"]=True
    msg = build_alert_message(results)
    send_telegram(msg)

st.success("✅ 초기 스캔 완료 & Telegram 발송 완료!")
