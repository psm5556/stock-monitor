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


def get_company_name(symbol):
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except:
        return symbol


# ✅ app.py 동일 (return 위치 Fix + MA 추가)
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


# ✅ app.py 동일
def is_downtrend(df, lookback=20):
    if len(df) < lookback + 1:
        return False

    close_slope = (df["Close"].iloc[-1] - df["Close"].iloc[-lookback]) / lookback
    ma200_slope = (
        df["MA200"].iloc[-1] - df["MA200"].iloc[-lookback]
        if "MA200" in df.columns else 0
    ) / lookback

    return (close_slope < 0) or (ma200_slope < 0)


# ✅ app.py 동일 (MA 아래 있어도 감지)
def detect_ma_touch(df, tolerance=0.005):
    touches = []
    last = df.iloc[-1]

    for p in MA_LIST:
        col = f"MA{p}"
        if col not in df.columns or pd.isna(last[col]):
            continue

        close_price = last["Close"]
        ma_value = last[col]
        gap = abs(close_price - ma_value) / ma_value
        is_near = gap <= tolerance
        is_below = close_price < ma_value

        if is_near or is_below:
            touches.append((p, round(gap*100, 2))) # ✅ gap % 포함 반환

    return touches


def scan(symbol):
    name = get_company_name(symbol)
    result = {"symbol": symbol, "name": name, "daily": [], "weekly": []}

    for interval, key in [("1d", "daily"), ("1wk", "weekly")]:
        df = get_price(symbol, interval)
        if df is not None and is_downtrend(df):
            touches = detect_ma_touch(df)
            if touches:
                result[key] = touches

    return result


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})


KST = pytz.timezone("Asia/Seoul")
timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
header = f"📬 [자동] 장기 MA 접근 감지 ({timestamp})\n"

daily_msg = "\n📅 Daily\n"
weekly_msg = "\n🗓 Weekly\n"
has_daily = has_weekly = False

for sym in TICKERS:
    r = scan(sym)

    if r["daily"]:
        has_daily = True
        line = f"- {r['name']} ({sym}): "
        line += ", ".join([f"MA{p}({gap}%)" for p, gap in r["daily"]]) + "\n"
        daily_msg += line

    if r["weekly"]:
        has_weekly = True
        line = f"- {r['name']} ({sym}): "
        line += ", ".join([f"MA{p}({gap}%)" for p, gap in r["weekly"]]) + "\n"
        weekly_msg += line


msg = header
if has_daily: msg += daily_msg
if has_weekly: msg += weekly_msg
if not (has_daily or has_weekly):
    msg += "감지된 종목 없음\n"


send_telegram(msg)
print("✅ Scan Done & Telegram Sent")
