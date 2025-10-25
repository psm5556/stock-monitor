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


def get_company_name(s):
    try:
        return yf.Ticker(s).info.get("longName") or s
    except: return s


def get_price(symbol, interval):
    ticker = yf.Ticker(symbol)
    period = "10y" if interval=="1wk" else "3y"
    df = ticker.history(period=period, interval=interval)
    if df is None or df.empty: return None
    df = df[["Open","High","Low","Close","Volume"]].copy()
    for p in MA_LIST:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()
    df.dropna(inplace=True)
    return df if not df.empty else None


def is_downtrend(df):
    if len(df)<21: return False
    close_slope = df["Close"].iloc[-1] - df["Close"].iloc[-21]
    return close_slope<0


def detect(symbol):
    out = {"symbol":symbol,"name":get_company_name(symbol),
           "Daily":{"근접":[],"하향이탈":[]},
           "Weekly":{"근접":[],"하향이탈":[]}}
    for itv,key in [("1d","Daily"),("1wk","Weekly")]:
        df = get_price(symbol,itv)
        if df is not None and is_downtrend(df):
            last=df.iloc[-1]
            for p in MA_LIST:
                ma=last[f"MA{p}"]
                gap=(last["Close"]-ma)/ma
                if abs(gap)<=0.005: out[key]["근접"].append((p,round(gap*100,2)))
                elif last["Close"]<ma: out[key]["하향이탈"].append((p,round(gap*100,2)))
    return out


def build_msg(results):
    ts = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    msg = f"📬 [자동] 장기 MA 감지 ({ts})\n"
    sections=[
        ("📅 Daily — 근접","Daily","근접"),
        ("📅 Daily — 하향이탈","Daily","하향이탈"),
        ("🗓 Weekly — 근접","Weekly","근접"),
        ("🗓 Weekly — 하향이탈","Weekly","하향이탈"),
    ]
    any_sig=False
    for title,k1,k2 in sections:
        block=""
        for r in results:
            rows=r[k1][k2]
            if rows:
                any_sig=True
                block+=f"- {r['name']} ({r['symbol']})\n"
                for p,gap in rows:
                    emoji="✅" if k2=="근접" else "🔻"
                    block+=f"   {emoji} MA{p} {k2} ({gap:+.2f}%)\n"
        if block: msg+=f"\n{title}\n{block}"
    if not any_sig: msg+="\n감지된 종목 없음"
    return msg


def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id":CHAT_ID,"text":msg})


results=[]
for s in TICKERS:
    r = detect(s)
    if any([r["Daily"]["근접"],r["Daily"]["하향이탈"],r["Weekly"]["근접"],r["Weekly"]["하향이탈"]]):
        results.append(r)

msg = build_msg(results)
send(msg)
print("✅ 자동 스캔 완료 & Telegram 전송!")
