import os
import requests
import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime

# =========================
# Telegram 설정 (자동)
# =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# =========================
# 감지 기본 설정
# =========================
MA_LIST = [200, 240, 365]
TOLERANCE = 0.05  # ✅ 근접 임계값 ±1%

TICKERS = [
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


def get_company_name(symbol):
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except:
        return symbol


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


def is_downtrend(df, lookback=20):
    if len(df) < lookback + 1:
        return False
    return (df["Close"].iloc[-1] - df["Close"].iloc[-lookback]) < 0


# ✅ 근접 + 하향이탈 중복 감지 허용
def detect_ma_touch(df):
    touches = []
    last = df.iloc[-1]

    for p in MA_LIST:
        ma = last[f"MA{p}"]
        if pd.isna(ma): continue

        close = last["Close"]
        gap = (close - ma) / ma

        # 근접 감지
        if abs(gap) <= TOLERANCE:
            touches.append((p, round(gap*100,2), "근접"))

        # 하향이탈 감지 (근접과 중복 허용)
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


# ✅ 메시지 4섹션 구성
def build_msg(results):
    ts = datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
    msg = f"📬 [자동] MA 접근 감지 ({ts})\n"

    sections = [
        ("📅 Daily — 근접", "daily", "근접"),
        ("📅 Daily — 하향이탈", "daily", "하향이탈"),
        ("🗓 Weekly — 근접", "weekly", "근접"),
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


def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id":CHAT_ID,"text":msg})


# =========================
# 자동 스캔 실행
# =========================
results = []
for s in TICKERS:
    r = detect_symbol(s)
    if r["daily"] or r["weekly"]:
        results.append(r)

send(build_msg(results))
print("✅ 자동 스캔 완료 & Telegram 전송!")
