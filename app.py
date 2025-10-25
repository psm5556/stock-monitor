import os
import math
import requests
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
from datetime import datetime
import plotly.graph_objects as go

# =========================
# 환경 변수 설정 (수동)
# =========================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# =========================
# UI 헤더
# =========================
st.set_page_config(page_title="📈 장기 MA 접근 모니터", layout="wide")
st.title("📈 장기(200/240/365) 이동평균선 접근 모니터 — 일봉 & 주봉")
st.caption("Daily/Weekly - 근접 및 하향이탈 감지")

# =========================
# 감지대상 티커 (원본 유지)
# =========================
available_tickers = [
    "AAPL","ABCL","ACHR","AEP","AES","ALAB","AMD","AMZN","ANET","ARQQ","ARRY","ASML",
    "ASTS","AVGO","BA","BAC","BE","BEP","BLK","BMNR","BP","BTQ","BWXT","C","CARR",
    "CDNS","CEG","CFR.SW","CGON","CLPT","COIN","CONL","COP","COST","CRCL","CRDO",
    "CRM","CRSP","CSCO","CVX","D","DELL","DNA","DUK","ED","EMR","ENPH","ENR","EOSE",
    "EQIX","ETN","EXC","FLNC","FSLR","GEV","GLD","GOOGL","GS","HOOD","HSBC","HUBB",
    "IBM","INTC","IONQ","JCI","JOBY","JPM","KO","LAES","LMT","LRCX","LVMUY","MA",
    "MPC","MSFT","MSTR","NEE","NGG","NOC","NRG","NRGV","NTLA","NTRA","NVDA","OKLO",
    "ON","ORCL","OXY","PCG","PG","PLTR","PLUG","PSTG","PYPL","QBTS","QS","QUBT",
    "QURE","RGTI","RKLB","ROK","SBGSY","SEDG","SHEL","SIEGY","SLDP","SMR","SNPS",
    "SO","SOFI","SPCE","SPWR","XYZ","SRE","STEM","TLT","TMO","TSLA","TSM","TWST",
    "UBT","UNH","V","VLO","VRT","VST","WMT","HON","TXG","XOM","ZPTA"
]

MA_LIST = [200, 240, 365]


# =========================
# 회사명 캐싱 조회
# =========================
@st.cache_data(ttl=86400)
def get_company_name(symbol):
    try:
        t = yf.Ticker(symbol)
        info = t.info
        return info.get("longName") or info.get("shortName") or symbol
    except:
        return symbol


# =========================
# 가격 데이터 조회 + MA 계산
# =========================
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


# =========================
# 하락 추세 판단
# =========================
def is_downtrend(df, lookback=20):
    if len(df) < lookback + 1:
        return False
    slope = df["Close"].iloc[-1] - df["Close"].iloc[-lookback]
    return slope < 0


# =========================
# MA 근접/하향이탈 감지
# =========================
def detect_ma_touch(df):
    touches = []
    last = df.iloc[-1]
    for p in MA_LIST:
        col = f"MA{p}"
        if pd.isna(last[col]):
            continue
        close = last["Close"]
        ma = last[col]
        gap = (close - ma) / ma
        abs_gap = abs(gap)
        if abs_gap <= 0.005:
            status = "근접"
        elif close < ma:
            status = "하향이탈"
        else:
            continue
        touches.append((p, round(gap*100,2), status))
    return touches


# =========================
# 심볼별 감지 결과 생성
# =========================
def detect_signals_for_symbol(symbol):
    name = get_company_name(symbol)
    result = {"symbol":symbol,"name":name,"daily":[],"weekly":[]}

    for interval, key in [("1d","daily"),("1wk","weekly")]:
        df = get_price(symbol, interval)
        if df is not None and is_downtrend(df):
            detected = detect_ma_touch(df)
            if detected:
                result[key] = detected
    return result


# =========================
# ✅ 메시지 구성 — 4섹션 분리
# =========================
def build_alert_message(results):
    timestamp = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    msg = f"📬 [수동] MA 접근 감지 결과 ({timestamp})\n"

    sections = [
        ("📅 Daily — 근접",  "daily",  "근접"),
        ("📅 Daily — 하향이탈", "daily",  "하향이탈"),
        ("🗓 Weekly — 근접",  "weekly", "근접"),
        ("🗓 Weekly — 하향이탈", "weekly", "하향이탈"),
    ]

    any_signal = False
    for title, tf, sk in sections:
        block = ""
        for r in results:
            rows = [(p,g) for (p,g,s) in r[tf] if s == sk]
            if rows:
                any_signal = True
                block += f"- {r['name']} ({r['symbol']})\n"
                for p, gap in rows:
                    emoji = "✅" if sk=="근접" else "🔻"
                    block += f"   {emoji} MA{p} {sk} ({gap:+.2f}%)\n"
        if block:
            msg += f"\n{title}\n{block}"

    if not any_signal:
        msg += "\n감지된 종목 없음"

    return msg


# =========================
# Telegram 전송
# =========================
def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id":CHAT_ID,"text":text})
    return r.status_code == 200


# =========================
# 앱 최초 실행 시 1회 자동 스캔 & 메시지 전송
# =========================
if "scan_done" not in st.session_state:
    st.session_state["scan_done"] = True
    results = []
    for sym in available_tickers:
        r = detect_signals_for_symbol(sym)
        if r["daily"] or r["weekly"]:
            results.append(r)

    msg = build_alert_message(results)
    send_telegram(msg)

    st.success("✅ Telegram으로 감지 결과 전송 완료!")


# =========================
# 유저 UI 영역 (원본 Plot 모두 유지)
# =========================
symbol_map = {sym: get_company_name(sym) for sym in available_tickers}
display_list = sorted([f"{symbol_map[sym]} ({sym})" for sym in available_tickers], key=str.lower)

st.sidebar.header("종목 선택")
sel_display = st.sidebar.selectbox("회사명 선택", display_list)
typed_symbol = st.sidebar.text_input("또는 직접 입력")

if typed_symbol.strip():
    selected_symbol = typed_symbol.upper()
else:
    selected_symbol = sel_display.split("(")[-1].replace(")","").strip()

selected_name = get_company_name(selected_symbol)

chart_interval = st.sidebar.radio("차트 주기",
                                 options=["1d","1wk"],
                                 format_func=lambda x: "일봉" if x=="1d" else "주봉")


st.subheader("📊 선택 종목 차트")
df_chart = get_price(selected_symbol, chart_interval)

if df_chart is None:
    st.error("데이터 부족")
else:
    title = f"{selected_name} ({selected_symbol}) — {'일봉' if chart_interval=='1d' else '주봉'}"
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart["Open"], high=df_chart["High"],
        low=df_chart["Low"], close=df_chart["Close"],
        increasing_line_color="red",
        decreasing_line_color="blue"
    ))
    for p,color in zip(MA_LIST,["#7752fe","#f97316","#6b7280"]):
        col = f"MA{p}"
        if col in df_chart.columns:
            fig.add_trace(go.Scatter(
                x=df_chart.index, y=df_chart[col], mode="lines",
                name=f"MA{p}", line=dict(width=2,color=color)
            ))
    fig.update_layout(height=560)
    st.plotly_chart(fig, use_container_width=True)

st.caption(f"⏱ 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
