import yfinance as yf
import requests
import os

# 환경변수에서 토큰/챗아이디를 읽어옵니다.
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'CHANGE_ME_BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID', 'CHANGE_ME_CHAT_ID')

# 모니터링 대상과 기간(일/주 단위 이동평균 기간)
TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOG"]
PERIODS = [200, 240, 365]

def send_telegram(msg):
    if BOT_TOKEN.startswith('CHANGE_ME') or CHAT_ID.startswith('CHANGE_ME'):
        print("[WARN] BOT_TOKEN or CHAT_ID not configured - skipping send")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def check_cross(ticker, interval):
    # interval: '1d' 또는 '1wk'
    data = yf.download(ticker, period="2y", interval=interval, progress=False)
    close = data['Close']
    res = []
    if len(close) < 2:
        return res
    for p in PERIODS:
        ma = close.rolling(p).mean()
        if ma.isna().all():
            continue
        # 직전과 현재의 관계를 비교해 교차(상향/하향)를 감지
        prev_close = close.iloc[-2]
        last_close = close.iloc[-1]
        prev_ma = ma.iloc[-2]
        last_ma = ma.iloc[-1]
        if prev_close < prev_ma and last_close >= last_ma:
            res.append((p, '상향'))
        elif prev_close > prev_ma and last_close <= last_ma:
            res.append((p, '하향'))
    return res

def main():
    alerts = []
    for t in TICKERS:
        daily_cross = check_cross(t, '1d')
        weekly_cross = check_cross(t, '1wk')
        if daily_cross or weekly_cross:
            parts = []
            if daily_cross:
                parts.append('일단위: ' + ', '.join([f"{p}일선({d})" for p,d in daily_cross]))
            if weekly_cross:
                parts.append('주단위: ' + ', '.join([f"{p}주선({d})" for p,d in weekly_cross]))
            alerts.append(f"{t} -> " + ' / '.join(parts))

    if alerts:
        send_telegram('🚨 이동평균선 교차 감지:\n' + '\n'.join(alerts))
    else:
        send_telegram('✅ 교차 없음 (최근 데이터 기준)')

if __name__ == '__main__':
    main()
