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

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ BOT_TOKEN/CHAT_ID 누락. 메시지를 전송하지 않습니다.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    except Exception as e:
        print(f"❌ Telegram 전송 실패: {e}")

def get_data(ticker, interval="1d"):
    period = "2y" if interval == "1d" else "5y"
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)
        if df is None or df.empty or "Close" not in df.columns:
            return pd.DataFrame()
        for p in PERIODS:
            df[f"MA{p}"] = df["Close"].rolling(p).mean()
        return df
    except Exception as e:
        print(f"[WARN] {ticker} 데이터 오류: {e}")
        return pd.DataFrame()

def detect_cross(df):
    res = []
    if df is None or df.empty or len(df) < 2:
        return res
    prev = df.iloc[-2]
    last = df.iloc[-1]
    for p in PERIODS:
        col = f"MA{p}"
        if col not in df.columns:
            continue
        prev_ma = df[col].iloc[-2]
        last_ma = df[col].iloc[-1]
        if pd.isna(prev_ma) or pd.isna(last_ma):
            continue
        if prev["Close"] < prev_ma and last["Close"] >= last_ma:
            res.append((p, "상향"))
        elif prev["Close"] > prev_ma and last["Close"] <= last_ma:
            res.append((p, "하향"))
    return res

def main():
    alerts = []
    for tkr in TICKERS:
        daily = get_data(tkr, "1d")
        weekly = get_data(tkr, "1wk")
        d = detect_cross(daily)
        w = detect_cross(weekly)
        if d or w:
            lines = [f"📈 {tkr} 교차 감지"]
            if d:
                lines.append("• 일단위: " + ", ".join([f"{p}일선({d})" for p, d in d]))
            if w:
                lines.append("• 주단위: " + ", ".join([f"{p}주선({d})" for p, d in w]))
            alerts.append("\n".join(lines))

    if alerts:
        msg = "🚨 이동평균선 교차 알림 🚨\n\n" + "\n\n".join(alerts)
        send_telegram(msg)
        print(msg)
    else:
        print("✅ 교차 없음")

if __name__ == "__main__":
    main()

