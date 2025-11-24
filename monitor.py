import os
import requests
import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime
import urllib.parse
import time

# =========================
# Telegram 설정 (자동)
# =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# =========================
# 감지 기본 설정
# =========================
MA_LIST = [200, 240, 365]
TOLERANCE = 0.01  # ✅ 근접 임계값 ±1%

# TICKERS = [
#     "RKLB","ASTS","JOBY","ACHR","NTLA","CRSP","DNA","TWST","TXG","ABCL",
#     "RXRX","BEAM","TEM","HIMS","IONQ","QBTS","RGTI","IBM","QUBT","SMR",
#     "OKLO","LEU","CCJ","DNA","TWST","TXG","ABCL","ARQQ","LAES","BTQ",
#     "CLPT","NPCE","WATT","AIRJ","COIN","HOOD","CRCL","XYZ","MSTR","BMNR",
#     "PLTR","CRM","SMCI","APP","DDOG","FIG","PATH","SYM","NBIS","IREN",
#     "CRWV","PLUG","QS","SLDP","BE","FLNC","ENS","EOSE","TSLA","ENPH",
#     "DUK","GEV","NEE","AES","CEG","VST","FSLR","NXT","XOM","CVX",
#     "OXY","VRT","CARR","HON","JCI","ANET","CRDO","ALAB","MRVL","MU",
#     "AMD","INTC","AVGO","TSM","LRCX","ON","SNPS","AMZN","MSFT","GOOGL",
#     "META","AAPL","EQIX","PANW","CRWD","ZS","PG","KO","PEP","WMT",
#     "COST","KMB","PM","UL","V","MA","AXP","PYPL","XYZ","SOFI",
#     "AFRM","BLK","JPM","COF","CB","RACE","WSM","LVMUY","UNH","NTRA",
#     "JNJ","TMO","ABT","ISRG","CVS","BSX","MRK","LLY","XYL","ECL",
#     "AWK","DD"
# ]

# ==========================
# 구글 시트에서 티커 자동 로드
# ==========================
# @st.cache_data(ttl=86400)
def load_available_tickers():
    import urllib.parse

    SHEET_ID = os.environ.get("GOOGLE_SHEET_ID") #st.secrets["GOOGLE_SHEET_ID"]      # 예: "1abcdEFGHijkLMNOP"
    SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME") #st.secrets["GOOGLE_SHEET_NAME"]  # 예: "포트폴리오"

    sheet_name_encoded = urllib.parse.quote(SHEET_NAME)

    # CSV Export URL
    csv_url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?"
        f"tqx=out:csv&sheet={sheet_name_encoded}"
    )

    # F열(티커, index 5), J열(체크, index 9)만 읽기
    df = pd.read_csv(
        csv_url,
        usecols=[5, 9],              # F열=티커(index 5), J열=체크(index 9)
        on_bad_lines="skip",
        engine="python"
    )

    # 컬럼명 수동 지정
    df.columns = ["티커", "체크"]

    # 체크된 행만 필터링: TRUE / 1 / Y / ✔ 모두 허용
    mask = df["체크"].astype(str).str.upper().isin(["TRUE", "1", "Y", "✔"])
    tickers = (
        df.loc[mask, "티커"]
          .dropna()
          .astype(str)
          .str.upper()
          .str.strip()
          .unique()
          .tolist()
    )

    return tickers

TICKERS = load_available_tickers()

if not TICKERS:
    print("⚠️ 티커 목록이 비어있습니다. 환경변수 설정을 확인하세요.")
    exit(1)

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
    # df.dropna(inplace=True)
    return df if not df.empty else None


def is_downtrend(df, lookback=20):
    if len(df) < lookback + 1:
        return False
    
    # 20일 이동평균선 계산
    ma20 = df["Close"].rolling(lookback).mean()
    
    # 최근 MA20 값과 lookback일 전 MA20 값 비교
    if pd.isna(ma20.iloc[-1]) or pd.isna(ma20.iloc[-lookback]):
        return False
    
    # MA20의 기울기가 음수면 하락 추세
    return ma20.iloc[-1] < ma20.iloc[-lookback]


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
        ("🗓 Weekly — 근접", "weekly", "근접"),
        ("📅 Daily — 하향이탈", "daily", "하향이탈"),
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


# ✅ 메시지 분할 전송 함수
def send(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ BOT_TOKEN 또는 CHAT_ID가 설정되지 않았습니다.")
        return
    
    MAX_LENGTH = 4000  # 안전 마진 포함 (텔레그램 제한 4096자)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # 메시지가 짧으면 그냥 전송
    if len(msg) <= MAX_LENGTH:
        try:
            response = requests.post(url, json={"chat_id": CHAT_ID, "text": msg})
            if response.status_code == 200:
                print("✅ 텔레그램 전송 성공")
            else:
                print(f"⚠️ 텔레그램 전송 실패: {response.status_code}")
        except Exception as e:
            print(f"⚠️ 텔레그램 전송 오류: {e}")
        return
    
    # 메시지가 길면 줄바꿈 기준으로 분할
    lines = msg.split('\n')
    current_msg = ""
    msg_count = 1
    
    for i, line in enumerate(lines):
        # 다음 줄을 추가했을 때 길이 체크
        test_msg = current_msg + line + "\n"
        
        if len(test_msg) > MAX_LENGTH:
            # 현재 메시지 전송
            if current_msg:
                try:
                    response = requests.post(url, json={"chat_id": CHAT_ID, "text": current_msg.strip()})
                    if response.status_code == 200:
                        print(f"✅ 텔레그램 전송 성공 (Part {msg_count})")
                    else:
                        print(f"⚠️ 텔레그램 전송 실패 (Part {msg_count}): {response.status_code}")
                    time.sleep(0.5)  # 연속 전송 시 딜레이
                    msg_count += 1
                except Exception as e:
                    print(f"⚠️ 텔레그램 전송 오류 (Part {msg_count}): {e}")
            
            # 새 메시지 시작 (헤더 정보 유지)
            if msg_count > 1:
                current_msg = f"📬 [계속...] Part {msg_count}\n\n{line}\n"
            else:
                current_msg = line + "\n"
        else:
            current_msg = test_msg
    
    # 마지막 남은 메시지 전송
    if current_msg.strip():
        try:
            response = requests.post(url, json={"chat_id": CHAT_ID, "text": current_msg.strip()})
            if response.status_code == 200:
                print(f"✅ 텔레그램 전송 성공 (최종 Part {msg_count})")
            else:
                print(f"⚠️ 텔레그램 전송 실패 (최종): {response.status_code}")
        except Exception as e:
            print(f"⚠️ 텔레그램 전송 오류 (최종): {e}")


# =========================
# 자동 스캔 실행
# =========================
print(f"📊 스캔 시작: {len(TICKERS)}개 티커")
results = []
for i, s in enumerate(TICKERS, 1):
    print(f"  [{i}/{len(TICKERS)}] {s} 분석 중...")
    r = detect_symbol(s)
    if r["daily"] or r["weekly"]:
        results.append(r)

print(f"\n✅ 스캔 완료: {len(results)}개 종목 감지")
msg = build_msg(results)
print(f"📬 메시지 길이: {len(msg)}자")
send(msg)
print("✅ 자동 스캔 완료 & Telegram 전송!")
