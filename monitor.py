# monitor.py
import os
import math
import requests
import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

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
    "SNPS", "SO", "SOFI", "SPCE", "SPWR", "SQ", "SRE", "STEM", "TLT",
    "TMO", "TSLA", "TSM", "TWST", "UBT", "UNH", "V", "VLO", "VRT", "VST",
    "WMT", "HON", "TXG", "XOM", "ZPTA"
]  # ABB & CONE 제거됨

MA_LIST = [200, 240, 365]


# ✅ 회사명
def get_company_name(symbol):
    try:
        info = yf.Ticker(symbol).info
        name = info.get("longName") or info.get("shortName")
        return name if name else symbol
    except:
        return symbol


# ✅ 가격 데이터 가져오기 (app.py와 동일)
def get_price(symbol, interval="1d"):
    period = "10y" if interval == "1wk" else "3y"
    try:
        # df = yf.Ticker(symbol).history(period=period, interval=interval)
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval)
            if df.empty:
                # fallback: 전체 데이터
                df = yf.Ticker(symbol).history(period="max", interval=interval)
        except Exception:
            df = yf.Ticker(symbol).history(period="max", interval=interval)
        return df
        if df is None or df.empty:
            return None
        df = df[["Open","High","Low","Close","Volume"]].copy()
        for p in MA_LIST:
            df[f"MA{p}"] = df["Close"].rolling(p).mean()
        df = df.dropna()
        return df
    except:
        return None


# ✅ 하락 추세 확인
def is_downtrend(df, lookback=20):
    if len(df) < lookback + 1:
        return False
    close_slope = (df["Close"].iloc[-1] - df["Close"].iloc[-lookback]) / lookback
    ma200_slope = (df["MA200"].iloc[-1] - df["MA200"].iloc[-lookback]) / lookback if "MA200" in df.columns else 0
    return (close_slope < 0) or (ma200_slope < 0)


# ✅ MA 근접 판단
def detect_ma_touch(df, tolerance=0.005):
    touches = []
    last = df.iloc[-1]
    for p in MA_LIST:
        col = f"MA{p}"
        if col not in df.columns or pd.isna(last[col]):
            continue
        gap = abs(last["Close"] - last[col]) / last[col]
        if gap <= tolerance:
            touches.append(p)
    return touches


# ✅ 심볼 단위 감지
def scan(symbol):
    name = get_company_name(symbol)
    result = {"symbol": symbol, "name": name, "daily": [], "weekly": []}

    # Day
    dfd = get_price(symbol, "1d")
    if dfd is not None and is_downtrend(dfd):
        t = detect_ma_touch(dfd)
        if t: result["daily"] = t

    # Week
    dfw = get_price(symbol, "1wk")
    if dfw is not None and is_downtrend(dfw):
        t = detect_ma_touch(dfw)
        if t: result["weekly"] = t

    return result


# ✅ Telegram 전송
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram 전송 실패:", e)


# ✅ 실행
results = []
for sym in TICKERS:
    r = scan(sym)
    if r["daily"] or r["weekly"]:
        results.append(r)


# ✅ 메시지 구성 (C 방식)
# ts = datetime.now().strftime("%Y-%m-%d %H:%M")
KST = pytz.timezone("Asia/Seoul")
ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
msg = f"📬 장기 MA 접근 감지 결과 ({ts})\n\n"

if not results:
    msg += "이번 스캔에서는 감지된 종목이 없습니다."
else:
    for r in results:
        parts = []
        if r["daily"]:
            parts.append(f"일봉: {', '.join([f'MA{p}' for p in r['daily']])}")
        if r["weekly"]:
            parts.append(f"주봉: {', '.join([f'MA{p}' for p in r['weekly']])}")
        msg += f"- {r['name']} ({r['symbol']}): " + " / ".join(parts) + "\n"

send_telegram(msg)
print("✅ Scan done & Telegram sent.")
