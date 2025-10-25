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

# ======================================
# ✅ 환경 변수 (Streamlit Secrets 권장)
# ======================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

# ======================================
# UI 설정
# ======================================
st.set_page_config(page_title="📈 장기 MA 접근 모니터", layout="wide")
st.title("📈 장기 이동평균선 접근 모니터 — 저점 분할매수 전략")

st.caption("✅ 목적: **하락 추세**에서 **200/240/365 MA 근접/터치** 순간 포착 (저점 분할 매수 타점)")

# ======================================
# 티커
# ======================================
available_tickers = [
    "AAPL", "ABCL", "ACHR", "AEP", "AES", "ALAB", "AMD", "AMZN", "ANET", "ARQQ", "ARRY",
    "ASML", "ASTS", "AVGO", "BA", "BAC", "BE", "BEP", "BLK", "BMNR", "BP", "BTQ", "BWXT",
    "C", "CARR", "CDNS", "CEG", "CFR.SW", "CGON", "CLPT", "COIN", "CONL", "COP", "COST",
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

MA_LIST = [200, 240, 365]

# ✅ 회사명 캐시
@st.cache_data(ttl=86400)
def get_company_name(symbol):
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except:
        return symbol

# ✅ 정렬된 리스트 반환
@st.cache_data(ttl=86400)
def build_symbol_map(tickers):
    mapping = {sym: get_company_name(sym) for sym in tickers}
    sorted_list = sorted(tickers, key=lambda x: mapping[x])
    return mapping, sorted_list

symbol_map, sorted_symbols = build_symbol_map(available_tickers)

# ✅ 가격 + MA 계산
@st.cache_data(ttl=3600)
def get_price(symbol, interval="1d"):
    period = "10y" if interval == "1wk" else "3y"
    ticker = yf.Ticker(symbol)
    try:
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            df = ticker.history(period="max", interval=interval)
    except:
        df = ticker.history(period="max", interval=interval)

    if df is None or df.empty:
        return None

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    for p in MA_LIST:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()
    df.dropna(inplace=True)
    return df if not df.empty else None

# ✅ 하락 추세 확인
def is_downtrend(df, lb=20):
    if len(df) < lb + 1:
        return False
    slope = (df.Close.iloc[-1] - df.Close.iloc[-lb]) / lb
    return slope < 0

# ✅ MA 접근 감지
def detect_ma_touch(df, tol=0.005):
    touches = []
    last = df.iloc[-1]
    for p in MA_LIST:
        col = f"MA{p}"
        if col in df.columns:
            if abs(last.Close - last[col]) / last[col] <= tol:
                touches.append(p)
    return touches

# ✅ Telegram (한번에 하나)
def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram 정보 미설정")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text})
    return r.status_code == 200

# ✅ 메시지 생성
def build_msg(results):
    KST = pytz.timezone("Asia/Seoul")
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    if not results:
        return f"📬 ({ts})\n이번 스캔에서는 감지 없음"
    lines = [f"📬 장기 MA 접근 감지 결과 ({ts})\n"]
    for r in results:
        detail = []
        if r["daily"]:
            detail.append("일봉:" + ",".join(f"MA{x}" for x in r["daily"]))
        if r["weekly"]:
            detail.append("주봉:" + ",".join(f"MA{x}" for x in r["weekly"]))
        lines.append(f"- {r['name']} ({r['symbol']}): {' / '.join(detail)}")
    return "\n".join(lines)

# ✅ 최초 실행 시 전체 스캔 + Telegram 1회
if "scanned" not in st.session_state:
    st.session_state["scanned"] = True
    with st.spinner("📡 초기 스캔 중..."):
        result_list = []
        for sym in available_tickers:
            item = {"symbol": sym, "name": symbol_map[sym], "daily": [], "weekly": []}
            d = get_price(sym, "1d")
            if d is not None and is_downtrend(d):
                item["daily"] = detect_ma_touch(d)
            w = get_price(sym, "1wk")
            if w is not None and is_downtrend(w):
                item["weekly"] = detect_ma_touch(w)
            if item["daily"] or item["weekly"]:
                result_list.append(item)

        st.session_state["results"] = result_list
        send_telegram(build_msg(result_list))

st.subheader("📊 초기 감지 종목 요약")
results = st.session_state.get("results", [])

if results:
    df_sum = pd.DataFrame([{
        "Symbol": r["symbol"],
        "Company": r["name"],
        "Daily": ",".join(f"MA{x}" for x in r["daily"]),
        "Weekly": ",".join(f"MA{x}" for x in r["weekly"])
    } for r in results])
    st.dataframe(df_sum, use_container_width=True, hide_index=True)
else:
    st.info("감지된 종목 없음")

# --------------------------------------
# ✅ 선택 차트
# --------------------------------------
st.subheader("📈 종목 차트 보기")

sym = st.selectbox("종목 선택", sorted_symbols)
interval = st.radio("주기 선택", ["1d", "1wk"], horizontal=True)

df_chart = get_price(sym, interval)
name = symbol_map[sym]

import plotly.graph_objects as go
if df_chart is not None:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart.index,
        open=df_chart.Open,
        high=df_chart.High,
        low=df_chart.Low,
        close=df_chart.Close,
        name="가격"
    ))
    colors = ["#be185d", "#2563eb", "#22c55e"]  # red/blue/green
    for p, c in zip(MA_LIST, colors):
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart[f"MA{p}"], name=f"MA{p}", line=dict(width=2, color=c)))

    fig.update_layout(height=540, title=f"{name} ({sym}) — {'일봉' if interval=='1d' else '주봉'}")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("데이터 부족")

st.caption(f"⏱ 최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} KST")
