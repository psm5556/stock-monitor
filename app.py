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

MA_LIST = [200, 240, 365]

@st.cache_data(ttl=86400)
def get_company_name(symbol):
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except:
        return symbol

@st.cache_data(ttl=86400)
def build_symbol_map_and_sorted_list(tickers):
    mapping = {}
    for sym in tickers:
        mapping[sym] = get_company_name(sym)
    display_list = [f"{mapping[sym]} ({sym})" for sym in tickers]
    display_sorted = sorted(display_list, key=lambda s: s.lower())
    return mapping, display_sorted

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

def calc_gap(last_close, ma_value):
    return round((last_close - ma_value) / ma_value * 100, 2)

def is_downtrend(df, lookback=20):
    if len(df) < lookback + 1:
        return False
    close_slope = (df["Close"].iloc[-1] - df["Close"].iloc[-lookback]) / lookback
    ma200_slope = (
        df["MA200"].iloc[-1] - df["MA200"].iloc[-lookback]
        if "MA200" in df.columns else 0
    ) / lookback
    return (close_slope < 0) or (ma200_slope < 0)

def detect_ma_touch(df, tolerance=0.005):
    touches = []
    last = df.iloc[-1]

    for p in MA_LIST:
        col = f"MA{p}"
        if col not in df.columns or pd.isna(last[col]):
            continue

        close_price = last["Close"]
        ma_value = last[col]
        gap = (close_price - ma_value) / ma_value
        abs_gap = abs(gap)

        if abs_gap <= tolerance:
            status = "근접"
        elif close_price < ma_value:
            status = "하향이탈"
        else:
            continue

        touches.append((p, round(gap * 100, 2), status))

    return touches

def detect_signals_for_symbol(symbol):
    name = get_company_name(symbol)
    out = {"symbol": symbol, "name": name, "daily": [], "weekly": []}

    for interval, key in [("1d", "daily"), ("1wk", "weekly")]:
        df = get_price(symbol, interval)
        if df is not None and is_downtrend(df):
            touches = detect_ma_touch(df)
            if touches:
                out[key] = touches

    return out

# ✅ 메시지 분리 버전
def build_alert_messages(results):
    KST = pytz.timezone("Asia/Seoul")
    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    near_daily = []
    near_weekly = []
    break_daily = []
    break_weekly = []

    for r in results:
        name = r["name"]
        sym = r["symbol"]

        for p, gap, status in r["daily"]:
            if status == "근접":
                near_daily.append((name, sym, p, gap))
            elif status == "하향이탈":
                break_daily.append((name, sym, p, gap))

        for p, gap, status in r["weekly"]:
            if status == "근접":
                near_weekly.append((name, sym, p, gap))
            elif status == "하향이탈":
                break_weekly.append((name, sym, p, gap))

    def build_msg(title, d_list, w_list):
        if not (d_list or w_list):
            return None
        emoji = "✅" if "근접" in title else "🔻"
        msg = f"📬 [수동] {title} ({timestamp})\n"
        if d_list:
            msg += "\n📅 Daily\n"
            for name, sym, p, gap in d_list:
                msg += f"- {name} ({sym})\n   {emoji} MA{p} ({gap:+.2f}%)\n"
        if w_list:
            msg += "\n🗓 Weekly\n"
            for name, sym, p, gap in w_list:
                msg += f"- {name} ({sym})\n   {emoji} MA{p} ({gap:+.2f}%)\n"
        return msg

    msg_near = build_msg("장기 MA 근접", near_daily, near_weekly)
    msg_break = build_msg("장기 MA 하향이탈", break_daily, break_weekly)

    return msg_near, msg_break


def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text})
        return r.status_code == 200
    except:
        return False


if "scan_done_once" not in st.session_state:
    with st.spinner("초기 스캔 중…"):
        results = []
        for sym in available_tickers:
            r = detect_signals_for_symbol(sym)
            if r["daily"] or r["weekly"]:
                results.append(r)

        st.session_state["scan_done_once"] = True
        st.session_state["scan_results"] = results

        msg_near, msg_break = build_alert_messages(results)
        if msg_near:
            send_telegram_message(msg_near)
        if msg_break:
            send_telegram_message(msg_break)

        st.success("Telegram으로 감지 메시지를 전송했습니다.")

symbol_map, display_options = build_symbol_map_and_sorted_list(available_tickers)

st.sidebar.header("종목 선택")
sel_display = st.sidebar.selectbox("회사명 정렬 목록", display_options, index=0)
typed_symbol = st.sidebar.text_input("직접 티커 입력 (우선 적용)", value="")

if typed_symbol.strip():
    selected_symbol = typed_symbol.strip().upper()
    selected_name = get_company_name(selected_symbol)
else:
    selected_symbol = sel_display.split("(")[-1].replace(")", "").strip()
    selected_name = symbol_map.get(selected_symbol, selected_symbol)

chart_interval = st.sidebar.radio("차트 주기", options=["1d", "1wk"], index=0,
                                 format_func=lambda x: "일봉" if x=="1d" else "주봉")

st.subheader("🔎 초기 스캔 요약")
scan_results = st.session_state.get("scan_results", [])

if scan_results:
    rows = []
    for r in scan_results:
        rows.append({
            "Symbol": r["symbol"],
            "Company": r["name"],
            "Daily Touch": ", ".join([f"MA{p}" for p,_,_ in r["daily"]]),
            "Weekly Touch": ", ".join([f"MA{p}" for p,_,_ in r["weekly"]]),
        })
    df_summary = pd.DataFrame(rows).sort_values(["Company", "Symbol"]).reset_index(drop=True)
    st.dataframe(df_summary, use_container_width=True, hide_index=True)
else:
    st.info("이번 초기 스캔에서는 감지된 종목이 없습니다.")

import plotly.graph_objects as go

def plot_price_with_ma(df, symbol, name, interval):
    if df is None or df.empty:
        st.error("데이터 없음")
        return
    title = f"{name} ({symbol}) — {'일봉' if interval=='1d' else '주봉'}"
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="가격"
    ))
    for p, color in zip(MA_LIST, ["#7752fe", "#f97316", "#6b7280"]):
        col = f"MA{p}"
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines", name=f"MA{p}",
                                     line=dict(width=2, color=color)))
    fig.update_layout(height=560, legend=dict(orientation="h",
                        yanchor="bottom", y=1.02, xanchor="left", x=0))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("📊 선택 종목 차트")
df_chart = get_price(selected_symbol, chart_interval)
if df_chart is None:
    st.error("데이터 조회 실패")
else:
    plot_price_with_ma(df_chart, selected_symbol, selected_name, chart_interval)

st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
