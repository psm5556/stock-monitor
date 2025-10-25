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

# ── 미국 주말(토/일)에는 조기 종료
def is_us_weekend_now() -> bool:
    ny_tz = pytz.timezone("America/New_York")
    now_ny = datetime.now(ny_tz)
    # Monday=0 ... Sunday=6
    return now_ny.weekday() >= 5

if is_us_weekend_now():
    print("US weekend — skipping monitor run.")
    raise SystemExit(0)

# 회사명
def get_company_name(symbol: str) -> str:
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except Exception:
        return symbol

# 가격
def get_price(symbol: str, interval: str = "1d") -> pd.DataFrame | None:
    period = "10y" if interval == "1wk" else "3y"
    ticker = yf.Ticker(symbol)
    try:
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            df = ticker.history(period="max", interval=interval)
    except Exception:
        df = ticker.history(period="max", interval=interval)

    if df is None or df.empty:
        return None

    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[keep].copy()

    if "Close" in df.columns:
        for p in MA_LIST:
            df[f"MA{p}"] = df["Close"].rolling(p, min_periods=p).mean()
    return df

# 하락추세/괴리율/근접&하향이탈
def is_downtrend(df: pd.DataFrame, lookback: int = 20) -> bool:
    if df is None or df.empty or len(df) < lookback + 1 or "Close" not in df.columns:
        return False
    close_slope = (df["Close"].iloc[-1] - df["Close"].iloc[-lookback]) / lookback
    ma200_slope = 0.0
    if "MA200" in df.columns and not pd.isna(df["MA200"].iloc[-1]) and not pd.isna(df["MA200"].iloc[-lookback]):
        ma200_slope = (df["MA200"].iloc[-1] - df["MA200"].iloc[-lookback]) / lookback
    return (close_slope < 0) or (ma200_slope < 0)

def calc_gap(last_close: float, ma_value: float) -> float:
    if ma_value is None or pd.isna(ma_value) or ma_value == 0:
        return float("nan")
    return round((last_close - ma_value) / ma_value * 100, 2)

def detect_near_and_below(df: pd.DataFrame, tol: float = 0.5):
    near_list, below_list = [], []
    if df is None or df.empty or "Close" not in df.columns:
        return near_list, below_list
    last = df.iloc[-1]
    last_close = last["Close"]
    for p in MA_LIST:
        col = f"MA{p}"
        if col not in df.columns or pd.isna(last[col]):
            continue
        gap = calc_gap(last_close, last[col])
        if math.isfinite(gap) and abs(gap) <= tol:
            near_list.append((p, gap))
        if math.isfinite(gap) and last_close < last[col]:
            below_list.append((p, gap))
    return near_list, below_list

def scan(symbol: str) -> dict:
    name = get_company_name(symbol)
    out = {
        "symbol": symbol, "name": name,
        "daily_near": [], "daily_below": [],
        "weekly_near": [], "weekly_below": [],
    }
    dfd = get_price(symbol, "1d")
    if dfd is not None and is_downtrend(dfd):
        n, b = detect_near_and_below(dfd, tol=0.5)
        out["daily_near"], out["daily_below"] = n, b
    dfw = get_price(symbol, "1wk")
    if dfw is not None and is_downtrend(dfw):
        n, b = detect_near_and_below(dfw, tol=0.5)
        out["weekly_near"], out["weekly_below"] = n, b
    return out

# 메시지 빌드 & 전송
def send_telegram(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram not configured (BOT_TOKEN/CHAT_ID missing). Skipped send.")
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text})
        if r.status_code != 200:
            print("Telegram error:", r.text)
            return False
        return True
    except Exception as e:
        print("Telegram exception:", e)
        return False

def build_split_messages(results: list[dict]) -> tuple[str | None, str | None]:
    KST = pytz.timezone("Asia/Seoul")
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    header_near = f"📬 장기 MA **근접(±0.5%)** 감지 ({ts})\n"
    daily_near_lines, weekly_near_lines = [], []

    header_below = f"📬 장기 MA **하향 이탈** 감지 ({ts})\n"
    daily_below_lines, weekly_below_lines = [], []

    for r in results:
        if r["daily_near"]:
            parts = []
            for p, gap in r["daily_near"]:
                arrow = "▼" if gap < 0 else "▲"
                parts.append(f"{arrow}{gap}% (MA{p})")
            daily_near_lines.append(f"- {r['name']} ({r['symbol']})  " + ", ".join(parts))
        if r["weekly_near"]:
            parts = []
            for p, gap in r["weekly_near"]:
                arrow = "▼" if gap < 0 else "▲"
                parts.append(f"{arrow}{gap}% (MA{p})")
            weekly_near_lines.append(f"- {r['name']} ({r['symbol']})  " + ", ".join(parts))

        if r["daily_below"]:
            parts = []
            for p, gap in r["daily_below"]:
                parts.append(f"▼{gap}% (MA{p})")
            daily_below_lines.append(f"- {r['name']} ({r['symbol']})  " + ", ".join(parts))
        if r["weekly_below"]:
            parts = []
            for p, gap in r["weekly_below"]:
                parts.append(f"▼{gap}% (MA{p})")
            weekly_below_lines.append(f"- {r['name']} ({r['symbol']})  " + ", ".join(parts))

    msg_near = None
    if daily_near_lines or weekly_near_lines:
        body = []
        if daily_near_lines:
            body.append("\n📅 Daily\n" + "\n".join(daily_near_lines))
        if weekly_near_lines:
            body.append("\n🗓 Weekly\n" + "\n".join(weekly_near_lines))
        msg_near = header_near + "\n".join(body)

    msg_below = None
    if daily_below_lines or weekly_below_lines:
        body = []
        if daily_below_lines:
            body.append("\n📅 Daily\n" + "\n".join(daily_below_lines))
        if weekly_below_lines:
            body.append("\n🗓 Weekly\n" + "\n".join(weekly_below_lines))
        msg_below = header_below + "\n".join(body)

    def truncate(m: str | None) -> str | None:
        if m and len(m) > 3800:
            return m[:3700] + "\n…(결과가 많아 일부 생략)"
        return m

    return truncate(msg_near), truncate(msg_below)

# 실행
results = []
for sym in TICKERS:
    r = scan(sym)
    if (r["daily_near"] or r["weekly_near"] or r["daily_below"] or r["weekly_below"]):
        results.append(r)

msg_near, msg_below = build_split_messages(results)
sent_any = False
if msg_near:
    ok = send_telegram(msg_near); sent_any = sent_any or ok
if msg_below:
    ok = send_telegram(msg_below); sent_any = sent_any or ok

print("✅ Monitor done. Messages sent?" , sent_any)
