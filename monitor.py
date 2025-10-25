import yfinance as yf
import pandas as pd
import requests
import os

# 환경변수에서 토큰/챗아이디를 읽어옵니다.
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8457877356:AAEam56w8yHqX-ymfGArr3BXAlhmjJB2pDA')
CHAT_ID = os.environ.get('CHAT_ID', '5877958037')

TICKERS = [
    "AAPL", "ABB", "ABCL", "ACHR", "AEP",
    "AES", "ALAB", "AMD", "AMZN", "ANET", "ARQQ", "ARRY", "ASML", "ASTS", "AVGO",
    "BA", "BAC", "BE", "BEP", "BLK", "BMNR", "BP", "BTQ", "BWXT", "C", "CARR",
    "CDNS", "CEG", "CFR.SW", "CGON", "CLPT", "COIN", "CONE", "CONL", "COP", "COST",
    "CRCL", "CRDO", "CRM", "CRSP", "CSCO", "CVX", "D", "DELL", "DNA", "DUK", "ED",
    "EMR", "ENPH", "ENR", "EOSE", "EQIX", "ETN", "EXC", "FLNC", "FSLR", "GEV", "GLD",
    "GOOGL", "GS", "HOOD", "HSBC", "HUBB", "IBM", "INTC", "IONQ", "JCI", "JOBY", "JPM",
    "KO", "LAES", "LMT", "LRCX", "LVMUY", "MA", "MPC", "MSFT", "MSTR", "NEE", "NGG",
    "NOC", "NRG", "NRGV", "NTLA", "NTRA", "NVDA", "OKLO", "ON", "ORCL", "OXY", "PCG",
    "PG", "PLTR", "PLUG", "PSTG", "PYPL", "QBTS", "QS", "QUBT", "QURE", "RGTI", "RKLB",
    "ROK", "SBGSY", "SEDG", "SHEL", "SIEGY", "SLDP", "SMR", "SNPS", "SO", "SOFI",
    "SPCE", "SPWR", "SQ", "SRE", "STEM", "TLT", "TMO", "TSLA", "TSM", "TWST", "UBT",
    "UNH", "V", "VLO", "VRT", "VST", "WMT", "HON", "TXG", "XOM", "ZPTA"
] # 25.10.25
PERIODS = [200, 240, 365]

def send_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram 전송 실패: {e}")

def detect_cross(df):
    results = []
    if len(df) < 2:
        return results
    prev, curr = df.iloc[-2], df.iloc[-1]
    for p in PERIODS:
        col = f"MA{p}"
        if col not in df.columns:
            continue
        if prev["Close"] < prev[col] and curr["Close"] >= curr[col]:
            results.append((p, "상향"))
        elif prev["Close"] > prev[col] and curr["Close"] <= curr[col]:
            results.append((p, "하향"))
    return results


alerts = []
for ticker in TICKERS:
    df = yf.download(ticker, period="2y", interval="1d", auto_adjust=True, progress=False)
    if df.empty:
        continue
    
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    for p in PERIODS:
        df[f"MA{p}"] = df["Close"].rolling(p, min_periods=p).mean()
    df = df.dropna()

    cross = detect_cross(df)
    if cross:
        alerts.append(
            f"{ticker} → " + ", ".join([f"{p}일선 {d}" for p, d in cross])
        )

if alerts:
    send_telegram("🚨 이동평균선 교차 감지!\n" + "\n".join(alerts))
else:
    send_telegram("✅ 최근 교차 없음")

