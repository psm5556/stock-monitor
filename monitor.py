# monitor.py
import os
import requests
import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

TICKERS = [
    "AAPL", "ABCL", "ACHR", "AEP", "AES", "ALAB", "AMD", "AMZN", "ANET",
    "ARQQ", "ARRY", "ASML", "ASTS", "AVGO", "BA", "BAC", "BE", "BEP",
    "BLK", "BMNR", "BP", "BTQ", "BWXT", "C", "CARR", "CDNS", "CEG",
    "CFR.SW", "CGON", "CLPT", "COIN", "COP", "COST", "CRCL", "CRDO",
    "CRM", "CRSP", "CSCO", "CVX", "D", "DELL", "DNA", "DUK", "ED", "EMR",
    "ENPH", "ENR", "EOSE", "EQIX", "ETN", "EXC", "FLNC", "FSLR", "GEV",
    "GLD", "GOOGL", "GS", "HOOD", "HSBC", "HUBB", "IBM", "INTC", "IONQ",
    "JCI", "JOBY", "JPM", "KO", "LAES", "LMT", "LRCX", "LVMUY", "MA",
    "MPC", "MSFT", "MSTR", "NEE", "NGG", "NOC", "NRG", "NRGV", "NTLA",
    "NTRA", "NVDA", "OKLO", "ON", "ORCL", "OXY", "PCG", "PG", "PLTR",
    "PLUG", "PSTG", "PYPL", "QBTS", "QS", "QUBT", "QURE", "RGTI",
    "RKLB", "ROK", "SBGSY", "SEDG", "SHEL", "SIEGY", "SLDP", "SMR",
    "SNPS", "SO", "SOFI", "SPCE", "SPWR", "XYZ", "SRE", "STEM", "TLT",
    "TMO", "TSLA", "TSM", "TWST", "UBT", "UNH", "V", "VLO", "VRT", "VST",
    "WMT", "HON", "TXG", "XOM", "ZPTA"
]

MA_LIST = [200, 240, 365]


# ✅ 회사명
def get_company_name(symbol):
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except:
        return symbol


# ✅ 가격 데이터 (app.py 동일)
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

    # ✅ 장기 이동평균 추가
    for p in MA_LIST:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()

    df.dropna(inplace=True)
    return df if not df.empty else None


# ✅ 하락 추세
def is_downtrend(df, lookback=20):
    if len(df) < lookback + 1:
        return False
    slope = (df.Close.iloc[-1] - df.Close.iloc[-lookback]) / lookback
    return slope < 0


# ✅ 괴리율 계산
def calc_gap(last_close, ma_value):
    return round((last_close - ma_value) / ma_value * 100, 2)


# ✅ MA Touch 감지
def detect_ma_touch(df, tol=0.005):
    touches = []
    last = df.iloc[-1]
    for p in MA_LIST:
        col = f"MA{p}"
        if col in df.columns:
            if abs(last.Close - last[col]) / last[col] <= tol:
                touches.append(p)
    return touches


# ✅ 감지 수행
def scan(symbol):
    name = get_company_name(symbol)
    dfd = get_price(symbol, "1d")
    dfw = get_price(symbol, "1wk")

    return {
        "symbol": symbol,
        "name": name,
        "daily": detect_ma_touch(dfd) if dfd is not None and is_downtrend(dfd) else [],
        "weekly": detect_ma_touch(dfw) if dfw is not None and is_downtrend(dfw) else [],
    }


# ✅ Telegram 전송
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram Error:", e)


# ✅ 메시지 구성 (app.py 개선 기반)
KST = pytz.timezone("Asia/Seoul")
timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
header = f"📬 [자동] 장기 MA 접근 감지 ({timestamp})\n"

daily_msg = "\n📅 Daily\n"
weekly_msg = "\n🗓 Weekly\n"

has_daily = has_weekly = False

for sym in TICKERS:
    r = scan(sym)
    if not r["daily"] and not r["weekly"]:
        continue

    # price refresh
    dfd = get_price(sym, "1d")
    dfw = get_price(sym, "1wk")

    last_d = dfd.iloc[-1] if dfd is not None else None
    last_w = dfw.iloc[-1] if dfw is not None else None

    # ✅ Daily 메시지
    if r["daily"]:
        has_daily = True
        parts = []
        for p in r["daily"]:
            gap = calc_gap(last_d.Close, last_d[f"MA{p}"])
            arrow = "▼" if gap < 0 else "▲"
            parts.append(f"{arrow}{gap}% (MA{p})")
        daily_msg += f"- {r['name']} ({sym})  " + ", ".join(parts) + "\n"

    # ✅ Weekly 메시지
    if r["weekly"]:
        has_weekly = True
        parts = []
        for p in r["weekly"]:
            gap = calc_gap(last_w.Close, last_w[f"MA{p}"])
            arrow = "▼" if gap < 0 else "▲"
            parts.append(f"{arrow}{gap}% (MA{p})")
        weekly_msg += f"- {r['name']} ({sym})  " + ", ".join(parts) + "\n"

# ✅ 최종 메시지 구성
msg = header
if has_daily: msg += daily_msg
if has_weekly: msg += weekly_msg
if not (has_daily or has_weekly):
    msg += "감지된 종목 없음"

# ✅ Telegram 발송
send_telegram(msg)
print("✅ Scan Done & Telegram Sent")
