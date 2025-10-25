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
# 환경 변수
# =========================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# =========================
# UI 설정
# =========================
st.set_page_config(page_title="📈 장기 MA 접근 모니터", layout="wide")
st.title("📈 장기(200/240/365) 이동평균선 접근 모니터 — 일봉 & 주봉")
st.caption("일봉/주봉 기반 장기 MA 접근/하향이탈 감지")

# =========================
# 모니터링 대상 티커 목록
# =========================
available_tickers = [
    "AAPL","ABCL","ACHR","AEP","AES","ALAB","AMD","AMZN","ANET","ARQQ","ARRY","ASML",
    "ASTS","AVGO","BA","BAC","BE","BEP","BLK","BMNR","BP","BTQ","BWXT","C","CARR",
    "CDNS","CEG","CFR.SW","CGON","CLPT","COIN","CONL","COP","COST","CRCL","CRDO",
    "CRM","CRSP","CSCO","CVX","D","DELL","DNA","DUK","ED","EMR","ENPH","ENR","EOSE",
    "EQIX","ETN","EXC","FLNC","FSLR","GEV","GLD","GOOGL","GS","HOOD","HSBC","HUBB",
    "IBM","INTC","IONQ","JCI","JOBY","JPM","KO","LAES","LMT","LRCX","LVMUY","MA","MPC",
    "MSFT","MSTR","NEE","NGG","NOC","NRG","NRGV","NTLA","NTRA","NVDA","OKLO","ON",
    "ORCL","OXY","PCG","PG","PLTR","PLUG","PSTG","PYPL","QBTS","QS","QUBT","QURE",
    "RGTI","RKLB","ROK","SBGSY","SEDG","SHEL","SIEGY","SLDP","SMR","SNPS","SO","SOFI",
    "SPCE","SPWR","XYZ","SRE","STEM","TLT","TMO","TSLA","TSM","TWST","UBT","UNH",
    "V","VLO","VRT","VST","WMT","HON","TXG","XOM","ZPTA"
]
MA_LIST = [200, 240, 365]

# =========================
# 회사명 가져오기
# =========================
@st.cache_data(ttl=86400)
def get_company_name(symbol: str) -> str:
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except Exception:
        return symbol

@st.cache_data(ttl=86400)
def build_symbol_map_and_sorted_list(tickers):
    mapping = {sym: get_company_name(sym) for sym in tickers}
    display_list = sorted([f"{mapping[sym]} ({sym})" for sym in tickers], key=str.lower)
    return mapping, display_list

# =========================
# 가격 데이터
# =========================
@st.cache_data(ttl=3600)
def get_price(symbol: str, interval="1d") -> pd.DataFrame | None:
    period = "10y" if interval == "1wk" else "3y"
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            df = ticker.history(period="max", interval=interval)
        if df.empty:
            return None

        df = df[["Open","High","Low","Close","Volume"]].copy()

        for p in MA_LIST:
            df[f"MA{p}"] = df["Close"].rolling(p).mean()

        # ✅ 최신 데이터 유지하며 오래된 NaN만 제거
        valid_min = df.dropna().index.min()
        if valid_min is not None:
            df = df[df.index >= valid_min]

        return df if not df.empty else None

    except Exception as e:
        print(f"[{symbol}][{interval}] error:", e)
        return None

# =========================
# 장기 MA 감지
# =========================
def detect_ma_touch(df, tolerance=0.005):
    touches = []
    last = df.iloc[-1]
    close = last["Close"]

    for p in MA_LIST:
        col = f"MA{p}"
        if col not in df.columns or pd.isna(last[col]):
            continue

        ma = last[col]
        gap = (close - ma) / ma
        pct = round(gap * 100, 2)

        if abs(gap) <= tolerance:
            touches.append((p, pct, "근접"))

        if close < ma:
            touches.append((p, pct, "하향이탈"))

    return touches


def detect_signals_for_symbol(symbol: str) -> dict:
    name = get_company_name(symbol)
    out = {"symbol": symbol, "name": name, "daily": [], "weekly": []}

    for interval, key in [("1d", "daily"), ("1wk", "weekly")]:
        df = get_price(symbol, interval)
        if df is not None:
            touches = detect_ma_touch(df)
            if touches:
                out[key] = touches

    return out

# =========================
# 메시지 구성 + Telegram 전송
# =========================
def build_alert_message(results: list[dict]) -> str:
    KST = pytz.timezone("Asia/Seoul")
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    msg = f"📬 장기 MA 접근 감지 ({ts})\n"

    section_added = False

    for frame, title in [("daily", "📅 Daily"), ("weekly", "🗓 Weekly")]:
        section = ""
        for r in results:
            if r[frame]:
                section += f"\n- {r['name']} ({r['symbol']})\n"
                for p, gap, status in r[frame]:
                    emoji = "✅" if status == "근접" else "🔻"
                    section += f"   {emoji} MA{p} {status} ({gap:+.2f}%)\n"
        if section:
            msg += f"\n{title}{section}"
            section_added = True

    if not section_added:
        msg += "\n감지된 종목 없음"

    return msg[:3800]

def send_telegram_message(text: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text})
        return r.status_code == 200
    except:
        return False

# =========================
# 실행 시 스캔
# =========================
with st.spinner("스캔 중… (일봉/주봉)"):
    results = []
    for sym in available_tickers:
        r = detect_signals_for_symbol(sym)
        if r["daily"] or r["weekly"]:
            results.append(r)
    st.session_state["scan_results"] = results

msg = build_alert_message(results)
if send_telegram_message(msg):
    st.success("Telegram 전송 완료 ✅")
else:
    st.warning("Telegram 전송 실패 ❌")

# =========================
# UI: 결과 테이블 + 차트
# =========================
symbol_map, display_options = build_symbol_map_and_sorted_list(available_tickers)

st.subheader("🔎 감지 결과 요약")
scan_results = st.session_state["scan_results"]

if scan_results:
    df_summary = pd.DataFrame([
        {
            "Symbol": r["symbol"],
            "Company": r["name"],
            "Daily": ", ".join([f"MA{p}" for p,_,_ in r["daily"]]),
            "Weekly": ", ".join([f"MA{p}" for p,_,_ in r["weekly"]]),
        }
        for r in scan_results
    ])
    st.dataframe(df_summary, use_container_width=True, hide_index=True)
else:
    st.info("감지된 종목 없음")

st.sidebar.header("종목 선택")
sel_display = st.sidebar.selectbox("회사명 검색", display_options)
typed_symbol = st.sidebar.text_input("직접 입력", "")

if typed_symbol.strip():
    selected_symbol = typed_symbol.strip().upper()
else:
    selected_symbol = sel_display.split("(")[-1].replace(")", "").strip()

selected_name = get_company_name(selected_symbol)
chart_interval = st.sidebar.radio("주기", ["1d", "1wk"], format_func=lambda x: "일봉" if x=="1d" else "주봉")

st.subheader("📊 차트")
df_chart = get_price(selected_symbol, chart_interval)
if df_chart is None:
    st.error("데이터 부족")
else:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_chart.index,
        open=df_chart["Open"], high=df_chart["High"], low=df_chart["Low"], close=df_chart["Close"],
        name="가격", increasing_line_color="red", decreasing_line_color="blue"
    ))
    for p,c in zip(MA_LIST,["#7752fe","#f97316","#6b7280"]):
        col=f"MA{p}"
        if col in df_chart.columns:
            fig.add_trace(go.Scatter(x=df_chart.index,y=df_chart[col],mode="lines",
                                     name=f"MA{p}",line=dict(width=2,color=c)))
    fig.update_layout(height=560,xaxis=dict(rangeslider=dict(visible=False)))
    st.plotly_chart(fig, use_container_width=True)

st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
