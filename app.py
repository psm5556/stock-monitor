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

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

MA_LIST = [200, 240, 365]
TOLERANCE = 0.01  # ✅ 근접 임계값 ±1%

st.set_page_config(page_title="📈 장기 MA 접근 모니터", layout="wide")
st.title("📈 장기(200/240/365) 이동평균선 접근 모니터 — 일봉 & 주봉")
st.caption("Daily/Weekly - 근접 & 하향이탈 감지 (중복 허용)")

# available_tickers = [
#     "AAPL","ABCL","ACHR","AEP","AES","ALAB","AMD","AMZN","ANET","ARQQ","ARRY","ASML",
#     "ASTS","AVGO","BA","BAC","BE","BEP","BLK","BMNR","BP","BTQ","BWXT","C","CARR",
#     "CDNS","CEG","CFR.SW","CGON","CLPT","COIN","CONL","COP","COST","CRCL","CRDO",
#     "CRM","CRSP","CSCO","CVX","D","DELL","DNA","DUK","ED","EMR","ENPH","ENR","EOSE",
#     "EQIX","ETN","EXC","FLNC","FSLR","GEV","GLD","GOOGL","GS","HOOD","HSBC","HUBB",
#     "IBM","INTC","IONQ","JCI","JOBY","JPM","KO","LAES","LMT","LRCX","LVMUY","MA",
#     "MPC","MSFT","MSTR","NEE","NGG","NOC","NRG","NRGV","NTLA","NTRA","NVDA","OKLO",
#     "ON","ORCL","OXY","PCG","PG","PLTR","PLUG","PSTG","PYPL","QBTS","QS","QUBT",
#     "QURE","RGTI","RKLB","ROK","SBGSY","SEDG","SHEL","SIEGY","SLDP","SMR","SNPS",
#     "SO","SOFI","SPCE","SPWR","XYZ","SRE","STEM","TLT","TMO","TSLA","TSM","TWST",
#     "UBT","UNH","V","VLO","VRT","VST","WMT","HON","TXG","XOM","ZPTA"
# ]

# available_tickers = [
#     "RKLB","ASTS","JOBY","ACHR","NTLA","CRSP","DNA","TWST","TXG","ABCL"
#     "IONQ","QBTS","RGTI","QUBT","ARQQ","LAES","XOM","CVX","VLO","NEE"
#     "CEG","BE","PLUG","BLDP","SMR","OKLO","LEU","UEC","CCJ","QS"
#     "SLDP","FLNC","ENS","TSLA","GEV","VRT","HON","ANET","CRDO","ALAB","AMD"
#     "ON","AMZN","MSFT","GOOGL","META","AAPL","EQIX","PLTR","CRM","FIG"
#     "PATH","SYM","NBIS","IREN","PANW","CRWD","PG","KO","PEP","WMT"
#     "COST","PM","V","MA","PYPL","XYZ","COIN","SOFI","HOOD","CRCL"
#     "BLK","JPM","RACE","WSM","UNH","NTRA","QURE","TMO","TEM","HIMS"
#     "ECL","XYL","AWK","DD"
# ]

# ==========================
# 구글 시트에서 티커 자동 로드
# ==========================
# @st.cache_data
def load_available_tickers():
    import urllib.parse

    SHEET_ID = st.secrets["GOOGLE_SHEET_ID"]      # 예: "1abcdEFGHijkLMNOP"
    SHEET_NAME = st.secrets["GOOGLE_SHEET_NAME"]  # 예: "포트폴리오"

    sheet_name_encoded = urllib.parse.quote(SHEET_NAME)

    # CSV Export URL
    csv_url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?"
        f"tqx=out:csv&sheet={sheet_name_encoded}"
    )

    # F열(티커, index 5), J열(체크, index 9)만 읽기
    df = pd.read_csv(
        csv_url,
        usecols=[5, 9],              # F열=티커(index 5), J열=체크(index 9)
        on_bad_lines="skip",
        engine="python"
    )

    # 컬럼명 수동 지정
    df.columns = ["티커", "체크"]

    # 체크된 행만 필터링: TRUE / 1 / Y / ✔ 모두 허용
    mask = df["체크"].astype(str).str.upper().isin(["TRUE", "1", "Y", "✔"])
    tickers = (
        df.loc[mask, "티커"]
          .dropna()
          .astype(str)
          .str.upper()
          .str.strip()
          .unique()
          .tolist()
    )

    return tickers

available_tickers = load_available_tickers()

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


# def is_downtrend(df, lookback=20):
#     if len(df) < lookback + 1:
#         return False
#     return (df["Close"].iloc[-1] - df["Close"].iloc[-lookback]) < 0

def is_downtrend(df, lookback=20):
    if len(df) < lookback + 1:
        return False
    
    # 20일 이동평균선 계산
    ma20 = df["Close"].rolling(lookback).mean()
    
    # 최근 MA20 값과 lookback일 전 MA20 값 비교
    if pd.isna(ma20.iloc[-1]) or pd.isna(ma20.iloc[-lookback]):
        return False
    
    # MA20의 기울기가 음수면 하락 추세
    return ma20.iloc[-1] < ma20.iloc[-lookback]


# ✅ 근접/하향이탈 중복 감지 허용
def detect_ma_touch(df):
    touches = []
    last = df.iloc[-1]
    
    for p in MA_LIST:
        ma = last[f"MA{p}"]
        if pd.isna(ma): continue

        close = last["Close"]
        gap = (close - ma) / ma

        # 근접 조건
        if abs(gap) <= TOLERANCE:
            touches.append((p, round(gap*100,2), "근접"))

        # 하향이탈 조건 (근접과 중복 허용)
        if close < ma:
            touches.append((p, round(gap*100,2), "하향이탈"))

    return touches


def detect_symbol(symbol):
    name = get_company_name(symbol)
    result = {"symbol":symbol,"name":name,"daily":[],"weekly":[]}

    for itv, key in [("1d","daily"),("1wk","weekly")]:
        df = get_price(symbol,itv)
        
        if df is not None and is_downtrend(df):
            res = detect_ma_touch(df)
            if res: result[key] = res
    return result


# ✅ 메시지 4섹션 분리
def build_alert_message(results):
    ts = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    msg = f"📬 [수동] MA 접근 감지 ({ts})\n"

    sections = [
        ("📅 Daily — 근접", "daily", "근접"),
        ("🗓 Weekly — 근접", "weekly", "근접"),
        ("📅 Daily — 하향이탈", "daily", "하향이탈"),
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
                for p,gap in rows:
                    emoji = "✅" if sk=="근접" else "🔻"
                    block += f"   {emoji} MA{p} {sk} ({gap:+.2f}%)\n"
        if block:
            msg += f"\n{title}\n{block}"

    if not any_signal:
        msg += "\n감지된 종목 없음"

    return msg


def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                  json={"chat_id":CHAT_ID,"text":msg})


# ✅ 최초 1회 자동 전송
if "scan" not in st.session_state:
    st.session_state["scan"] = True
    res = []
    for s in available_tickers:
        r = detect_symbol(s)
        if r["daily"] or r["weekly"]: res.append(r)
    send_telegram(build_alert_message(res))
    st.success("✅ Telegram 발송 완료!")


# =========================
# Plot UI 유지
# =========================
symbol_map = {s:get_company_name(s) for s in available_tickers}
display_list = sorted([f"{symbol_map[s]} ({s})" for s in available_tickers], key=str.lower)

st.sidebar.header("종목 선택")
sel_display = st.sidebar.selectbox("목록 선택", display_list)
typed = st.sidebar.text_input("직접 입력")

if typed.strip():
    ss = typed.upper()
else:
    ss = sel_display.split("(")[-1].replace(")","").strip()

df_chart = get_price(ss, st.sidebar.radio("차트주기", ["1d","1wk"], index=0))
name = get_company_name(ss)

st.subheader(f"📊 {name} ({ss}) Chart")

if df_chart is None:
    st.error("데이터 부족")
else:
    fig = go.Figure()
    
    # ✅ Box Zoom 적용
    fig.update_layout(
        dragmode="zoom",                # 박스 드래그 확대
        xaxis_rangeslider_visible=False # 하단 미니 차트 제거 (선택)
    )
    
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart["Open"], high=df_chart["High"],
        low=df_chart["Low"], close=df_chart["Close"]
    ))
    for p,c in zip(MA_LIST,["#7752fe","#f97316","#6b7280"]):
        fig.add_trace(go.Scatter(
            x=df_chart.index, y=df_chart[f"MA{p}"],
            mode="lines", name=f"MA{p}",
            line=dict(width=2,color=c)
        ))
    st.plotly_chart(fig, use_container_width=True)

st.caption(f"⏱ 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
