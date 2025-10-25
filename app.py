# app.py
import os
import math
import requests
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime

# =========================
# 환경 변수 (제공값 기본 세팅)
# =========================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# =========================
# UI 기본 설정
# =========================
st.set_page_config(page_title="📈 장기 MA 접근 모니터", layout="wide")
st.title("📈 장기(200/240/365) 이동평균선 접근 모니터 — 일봉 & 주봉")

st.caption("목적: 하락 추세에서 장기 MA(200/240/365)에 **접근/터치**하는 순간을 포착하여 저점 분할매수 기회를 찾습니다.")

# =========================
# 모니터링 대상 티커 (원하시면 자유롭게 수정)
# =========================
available_tickers = [
    "AAPL", "ABCL", "ACHR", "AEP",
    "AES", "ALAB", "AMD", "AMZN", "ANET", "ARQQ", "ARRY", "ASML", "ASTS", "AVGO",
    "BA", "BAC", "BE", "BEP", "BLK", "BMNR", "BP", "BTQ", "BWXT", "C", "CARR",
    "CDNS", "CEG", "CFR.SW", "CGON", "CLPT", "COIN", "CONL", "COP", "COST",
    "CRCL", "CRDO", "CRM", "CRSP", "CSCO", "CVX", "D", "DELL", "DNA", "DUK", "ED",
    "EMR", "ENPH", "ENR", "EOSE", "EQIX", "ETN", "EXC", "FLNC", "FSLR", "GEV", "GLD",
    "GOOGL", "GS", "HOOD", "HSBC", "HUBB", "IBM", "INTC", "IONQ", "JCI", "JOBY", "JPM",
    "KO", "LAES", "LMT", "LRCX", "LVMUY", "MA", "MPC", "MSFT", "MSTR", "NEE", "NGG",
    "NOC", "NRG", "NRGV", "NTLA", "NTRA", "NVDA", "OKLO", "ON", "ORCL", "OXY", "PCG",
    "PG", "PLTR", "PLUG", "PSTG", "PYPL", "QBTS", "QS", "QUBT", "QURE", "RGTI", "RKLB",
    "ROK", "SBGSY", "SEDG", "SHEL", "SIEGY", "SLDP", "SMR", "SNPS", "SO", "SOFI",
    "SPCE", "SPWR", "XYZ", "SRE", "STEM", "TLT", "TMO", "TSLA", "TSM", "TWST", "UBT",
    "UNH", "V", "VLO", "VRT", "VST", "WMT", "HON", "TXG", "XOM", "ZPTA"
]

MA_LIST = [200, 240, 365]


@st.cache_data(ttl=86400)
def get_company_name(symbol):
    try:
        i = yf.Ticker(symbol).info
        return i.get("longName") or i.get("shortName") or symbol
    except:
        return symbol


@st.cache_data(ttl=3600)
def get_price(symbol, interval="1d"):
    period = "10y" if interval == "1wk" else "3y"
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty:
        df = yf.Ticker(symbol).history(period="max", interval=interval)
    if df.empty:
        return None
    df = df[["Open","High","Low","Close","Volume"]].copy()
    for p in MA_LIST:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()
    df.dropna(inplace=True)
    return df


def is_downtrend(df, lookback=20):
    if len(df) < lookback+1:
        return False
    slope = (df.Close.iloc[-1]-df.Close.iloc[-lookback])/lookback
    ma200_slope = (df.MA200.iloc[-1]-df.MA200.iloc[-lookback])/lookback
    return (slope < 0) or (ma200_slope < 0)


def detect_ma_touch(df, tolerance=0.005):
    touches = []
    last = df.iloc[-1]
    for p in MA_LIST:
        col=f"MA{p}"
        if col not in df.columns: continue
        gap = (last.Close - last[col]) / last[col]
        if abs(gap) <= tolerance:
            status="근접"
        elif last.Close < last[col]:
            status="하향이탈"
        else:
            continue
        touches.append((p, round(gap*100,2), status))
    return touches


def detect_signals_for_symbol(sym):
    name = get_company_name(sym)
    out={"symbol": sym, "name": name, "daily": [], "weekly":[]}
    for interval,key in [("1d","daily"),("1wk","weekly")]:
        df=get_price(sym,interval)
        if df is not None and is_downtrend(df):
            t=detect_ma_touch(df)
            if t: out[key]=t
    return out


def send_telegram(msg):
    url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url,json={"chat_id":CHAT_ID,"text":msg})


def build_and_send_messages(results):
    if not BOT_TOKEN or not CHAT_ID: return
    KST=pytz.timezone("Asia/Seoul")
    ts=datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    near_d=near_w=below_d=below_w=""
    for r in results:
        name, sym = r["name"],r["symbol"]

        if r["daily"]:
            d_list=[x for x in r["daily"]]
            for p,g,s in d_list:
                if s=="근접": near_d+=f"- {name} ({sym}) MA{p} ✅ ({g:+.2f}%)\n"
                else: below_d+=f"- {name} ({sym}) MA{p} 🔻 ({g:+.2f}%)\n"

        if r["weekly"]:
            w_list=[x for x in r["weekly"]]
            for p,g,s in w_list:
                if s=="근접": near_w+=f"- {name} ({sym}) MA{p} ✅ ({g:+.2f}%)\n"
                else: below_w+=f"- {name} ({sym}) MA{p} 🔻 ({g:+.2f}%)\n"

    def send_block(title,d,w):
        if not d and not w: return
        m=f"{title} ({ts})\n"
        if d: m+="📅 Daily\n"+d
        if w: m+="🗓 Weekly\n"+w
        send_telegram(m)

    send_block("📬 MA 근접 감지", near_d, near_w)
    send_block("📉 MA 하향이탈 감지", below_d, below_w)


if "scan_done" not in st.session_state:
    with st.spinner("초기 스캔중…"):
        results=[r for r in [detect_signals_for_symbol(x) for x in available_tickers] if r["daily"] or r["weekly"]]
        st.session_state["scan_done"]=True
        st.session_state["scan_res"]=results
        build_and_send_messages(results)


st.subheader("스캔 요약")

summary_rows = []
for r in st.session_state["scan_res"]:
    daily_str = ", ".join([f"MA{p} {status}({gap:+.2f}%)"
                           for (p, gap, status) in r["daily"]]) if r["daily"] else ""
    weekly_str = ", ".join([f"MA{p} {status}({gap:+.2f}%)"
                            for (p, gap, status) in r["weekly"]]) if r["weekly"] else ""
    
    summary_rows.append({
        "Symbol": r["symbol"],
        "Company": r["name"],
        "Daily": daily_str,
        "Weekly": weekly_str
    })

df_summary = pd.DataFrame(summary_rows)
st.dataframe(df_summary, use_container_width=True)


st.subheader("📊 선택 종목 차트")
import plotly.graph_objects as go
sym=st.selectbox("티커 선택",available_tickers,index=0)
df=get_price(sym,"1d")
name=get_company_name(sym)
fig=go.Figure()
fig.add_trace(go.Candlestick(x=df.index,open=df.Open,high=df.High,low=df.Low,close=df.Close,name="OHLC"))
for p in MA_LIST:
    if f"MA{p}" in df.columns:
        fig.add_trace(go.Scatter(x=df.index,y=df[f"MA{p}"],mode="lines",name=f"MA{p}"))
fig.update_layout(title=f"{name} ({sym})",height=600)
st.plotly_chart(fig, use_container_width=True)
