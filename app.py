import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import requests
import time

# ===============================
# 🔧 설정
# ===============================
TELEGRAM_BOT_TOKEN = "여기에_본인_텔레그램_봇_토큰_입력"
TELEGRAM_CHAT_ID = "여기에_본인_Chat_ID_입력"

# 모니터링할 티커 (예시)
WATCHLIST = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOG", "AMZN"]

# ===============================
# 📤 텔레그램 알림 함수
# ===============================
def send_telegram_alert(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, data=payload)
    except Exception as e:
        print(f"[ERROR] 텔레그램 전송 실패: {e}")

# ===============================
# 📈 데이터 수집 함수
# ===============================
def get_data(ticker, interval="1d", period="2y"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if df.empty or "Close" not in df.columns:
            return pd.DataFrame()
        for ma in [200, 240, 365]:
            df[f"MA{ma}"] = df["Close"].rolling(ma).mean()
        return df
    except Exception as e:
        print(f"[ERROR] {ticker} 데이터 수집 실패: {e}")
        return pd.DataFrame()

# ===============================
# ⚙️ 교차 체크 함수
# ===============================
def check_cross(df, ticker, timeframe="일"):
    if df.empty:
        return None

    latest = df.iloc[-1]
    close = latest["Close"]
    alerts = []
    for ma in [200, 240, 365]:
        ma_value = latest[f"MA{ma}"]
        prev = df.iloc[-2][f"MA{ma}"]
        if pd.notna(ma_value) and pd.notna(prev):
            if (close >= ma_value and df.iloc[-2]["Close"] < prev) or \
               (close <= ma_value and df.iloc[-2]["Close"] > prev):
                alerts.append(f"{ticker} — {timeframe} {ma}일선 교차 감지!")

    return alerts

# ===============================
# 🚀 메인 실행 함수
# ===============================
def main():
    st.set_page_config(page_title="Stock MA Alert", layout="wide")
    st.title("📊 이동평균선 교차 모니터링 시스템")
    st.caption("200, 240, 365일선 + 주간 동일 조건 감시")

    alert_list = []

    with st.spinner("데이터 수집 중..."):
        for ticker in WATCHLIST:
            df_daily = get_data(ticker, "1d", "2y")
            df_weekly = get_data(ticker, "1wk", "5y")

            daily_alerts = check_cross(df_daily, ticker, "일")
            weekly_alerts = check_cross(df_weekly, ticker, "주")

            if daily_alerts:
                alert_list.extend(daily_alerts)
            if weekly_alerts:
                alert_list.extend(weekly_alerts)

    # ===============================
    # 🧾 결과 표시
    # ===============================
    if alert_list:
        st.success("🚨 교차 발생 감지!")
        for a in alert_list:
            st.write(a)
        message = "\n".join(alert_list)
        send_telegram_alert(f"📢 MA 교차 감지 알림\n{message}")
    else:
        st.info("현재 교차 조건을 만족하는 종목이 없습니다.")

    st.markdown("---")
    st.markdown("⏱️ 마지막 실행 시각: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    st.markdown("""
    ### ⚙️ 자동실행 설정 (예시)
    - Streamlit Cloud에서 주기 실행은 직접 지원되지 않으므로,
      GitHub + [cron-job.org](https://cron-job.org/) 또는 GitHub Actions로 10분 간격으로 호출할 수 있습니다.
    - 예시 URL:  
      `https://your-app.streamlit.app/`
    """)

# ===============================
# 🕒 자동실행 (로컬 테스트 시)
# ===============================
if __name__ == "__main__":
    main()
