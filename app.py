# app.py
import os
import time
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime

# ───────────────────────────────────────────────────────────────────────────────
# 기본 설정
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="📈 MA 터치 기반 분할매수 모니터", layout="wide")
st.title("📈 장기 이동평균(MA200/240/365) 터치 기반 분할매수 모니터 (일봉·주봉)")

# 환경변수에서 토큰/챗아이디 로드 (사용자 요청값을 기본값으로 유지)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8457877356:AAEam56w8yHqX-ymfGArr3BXAlhmjJB2pDA')
CHAT_ID   = os.environ.get('CHAT_ID',   '5877958037')

# 감시 대상 티커(요청된 목록)
available_tickers = [
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
]

MA_WINDOWS = [200, 240, 365]

# ───────────────────────────────────────────────────────────────────────────────
# 유틸: 텔레그램 메시지 전송 (한 번에 하나의 메시지)
# ───────────────────────────────────────────────────────────────────────────────
def send_telegram_message(text: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        r = requests.post(url, data=payload, timeout=10)
        return r.ok
    except Exception:
        return False

# ───────────────────────────────────────────────────────────────────────────────
# 데이터 로딩 & 가공
# ───────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_history(symbol: str, interval: str = "1d", period: str = "2y") -> pd.DataFrame:
    """
    yfinance.Ticker().history만 사용합니다. (yf.download 사용 금지)
    - interval: '1d' or '1wk'
    - period: 충분히 길게(기본 2y) 가져와서 MA365 계산 가능
    """
    try:
        tkr = yf.Ticker(symbol)
        df = tkr.history(period=period, interval=interval, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        # 컬럼 정리
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        # 이동평균(가격)
        for w in MA_WINDOWS:
            df[f"MA{w}"] = df["Close"].rolling(window=w, min_periods=w).mean()
        # 거래량 이동평균
        df["VOL_MA20"] = df["Volume"].rolling(window=20, min_periods=20).mean()
        return df.dropna().copy()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=86400, show_spinner=False)
def get_company_name(symbol: str) -> str:
    "기업명 자동 수집(하드코딩 X). 실패 시 심볼 반환."
    try:
        info = yf.Ticker(symbol).info
        name = info.get("longName") or info.get("shortName") or symbol
        return str(name)
    except Exception:
        return symbol

@st.cache_data(ttl=86400, show_spinner=False)
def build_sorted_company_list(symbols: list[str]) -> pd.DataFrame:
    rows = []
    for s in symbols:
        name = get_company_name(s)
        rows.append({"symbol": s, "name": name})
        # API rate 제한 완화
        time.sleep(0.02)
    df = pd.DataFrame(rows)
    df = df.sort_values("name").reset_index(drop=True)
    return df

# ───────────────────────────────────────────────────────────────────────────────
# 전략 로직 (보수적 기준)
# ───────────────────────────────────────────────────────────────────────────────
def calc_buy_score_row(prev_c, cur_c, cur_ma, cur_vol, vol_ma20) -> tuple[int, list[str]]:
    score = 0
    details = []

    # (1) 하락 중 MA 터치: 이전엔 위, 현재 MA 아래/접촉
    if prev_c > cur_ma and cur_c <= cur_ma:
        score += 20
        details.append("MA 하락 접촉")

    # (2) 괴리율(근접도) — MA에 가까울수록 가점 (보수적)
    if cur_ma and cur_ma > 0:
        diff = abs(cur_c - cur_ma) / cur_ma * 100
        if diff <= 0.5:
            score += 20
            details.append(f"괴리율 {diff:.2f}%")
        elif diff <= 1.0:
            score += 10
            details.append(f"괴리율 {diff:.2f}%")

    # (3) 거래량 돌파: 최근 20일 평균대비 30%↑
    if vol_ma20 and vol_ma20 > 0 and cur_vol > vol_ma20 * 1.3:
        score += 20
        details.append("거래량 돌파(+30%)")

    # (4) 반등률: MA 대비 1% 이상 반등
    if cur_ma and cur_ma > 0:
        rebound = (cur_c - cur_ma) / cur_ma * 100
        if rebound >= 1.0:
            score += 20
            details.append(f"반등률 {rebound:.2f}%")

    return score, details

def score_on_df(df: pd.DataFrame, ma_label: str) -> tuple[int, list[str]]:
    """
    df는 NA 없는 상태(rolling 후 dropna).
    마지막 두 개 캔들 기준으로 점수 계산.
    """
    if df is None or df.empty or len(df) < 2:
        return 0, []
    prev_c = df["Close"].iloc[-2]
    cur_c  = df["Close"].iloc[-1]
    cur_ma = df[ma_label].iloc[-1]
    cur_vol = df["Volume"].iloc[-1]
    vol_ma20 = df["VOL_MA20"].iloc[-1]
    return calc_buy_score_row(prev_c, cur_c, cur_ma, cur_vol, vol_ma20)

def detect_signals_for_symbol(symbol: str) -> dict:
    """
    심볼에 대해 일봉/주봉 각각 최고 점수 MA와 상세 사유를 반환.
    """
    out = {"symbol": symbol, "daily": None, "weekly": None}
    # Daily
    dfd = fetch_history(symbol, interval="1d", period="3y")
    best_d = (0, "", [])
    if not dfd.empty:
        for w in MA_WINDOWS:
            label = f"MA{w}"
            if label in dfd.columns:
                sc, dtl = score_on_df(dfd, label)
                # 장기일수 보너스(240/365) — 보수적 가점
                if w in (240, 365) and sc > 0:
                    sc += 10
                if sc > best_d[0]:
                    best_d = (sc, label, dtl)
    if best_d[0] > 0:
        out["daily"] = best_d

    # Weekly
    dfw = fetch_history(symbol, interval="1wk", period="10y")
    best_w = (0, "", [])
    if not dfw.empty:
        for w in MA_WINDOWS:
            label = f"MA{w}"
            if label in dfw.columns:
                sc, dtl = score_on_df(dfw, label)
                # 주봉은 더 보수적으로 가점
                if sc > 0:
                    sc += 20
                if w in (240, 365) and sc > 0:
                    sc += 10
                if sc > best_w[0]:
                    best_w = (sc, label, dtl)
    if best_w[0] > 0:
        out["weekly"] = best_w

    return out

def combine_score(daily_tuple, weekly_tuple) -> int:
    """
    일+주봉 동시 신호 시 1.2 배 보너스 (보수적)
    """
    d = daily_tuple[0] if daily_tuple else 0
    w = weekly_tuple[0] if weekly_tuple else 0
    if d > 0 and w > 0:
        return int((d + w) * 1.2)
    return d + w

def score_grade(score: int) -> str:
    if score >= 100:
        return "매수 강력 추천 💎"
    elif score >= 80:
        return "관찰 + 분할매수 👍"
    elif score >= 60:
        return "관심 종목 👀"
    else:
        return "보류 ⚠️"

# ───────────────────────────────────────────────────────────────────────────────
# 차트
# ───────────────────────────────────────────────────────────────────────────────
def plot_price_ma(df: pd.DataFrame, title: str):
    if df is None or df.empty:
        st.warning("데이터가 부족하여 차트를 표시할 수 없습니다.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines", name="Close"))
    for w in MA_WINDOWS:
        label = f"MA{w}"
        if label in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[label], mode="lines", name=label))

    # y축 동적 범위: 전체선의 min/max ±3%
    cols = ["Close"] + [f"MA{w}" for w in MA_WINDOWS if f"MA{w}" in df.columns]
    ydata = pd.concat([df[c] for c in cols], axis=1).dropna().values.ravel()
    if len(ydata) > 0:
        ymin, ymax = float(np.nanmin(ydata)), float(np.nanmax(ydata))
        pad = (ymax - ymin) * 0.03 if ymax > ymin else (ymin * 0.03)
        fig.update_yaxes(range=[ymin - pad, ymax + pad])

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Price",
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# ───────────────────────────────────────────────────────────────────────────────
# UI — 기업명 정렬 리스트 + 직접 입력
# ───────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔎 조회/차트 설정")
    company_df = build_sorted_company_list(available_tickers)
    display_names = [f"{row['name']} ({row['symbol']})" for _, row in company_df.iterrows()]
    picked = st.selectbox("종목 선택(기업명 오름차순)", display_names, index=0)
    manual = st.text_input("직접 티커 입력(우선 적용, 예: NVDA)", value="")

    timeframe = st.radio("차트 주기", ["일봉", "주봉"], horizontal=True, index=0)

# 실제 사용할 심볼
if manual.strip():
    symbol = manual.strip().upper()
    symbol_name = get_company_name(symbol)
else:
    idx = display_names.index(picked)
    symbol = company_df.loc[idx, "symbol"]
    symbol_name = company_df.loc[idx, "name"]

# ───────────────────────────────────────────────────────────────────────────────
# 앱 최초 시작 시에만: 전체 교차 감지 → 텔레그램 1회 알림
# ───────────────────────────────────────────────────────────────────────────────
if "did_notify" not in st.session_state:
    st.session_state.did_notify = False

if not st.session_state.did_notify:
    with st.status("전체 종목 교차 감지(일봉·주봉) 실행 중…", expanded=False):
        hits = []
        for s in available_tickers:
            sig = detect_signals_for_symbol(s)
            if sig.get("daily") or sig.get("weekly"):
                name = get_company_name(s)
                d = sig.get("daily")
                w = sig.get("weekly")
                total = combine_score(d, w)
                grade = score_grade(total)
                detail_lines = []
                if d:
                    detail_lines.append(f"• 일봉 {d[1]}: {d[0]}점 / " + ", ".join(d[2]))
                if w:
                    detail_lines.append(f"• 주봉 {w[1]}: {w[0]}점 / " + ", ".join(w[2]))
                hits.append({
                    "symbol": s, "name": name, "total": total, "grade": grade,
                    "detail": "\n".join(detail_lines)
                })
        # 점수 순 정렬
        hits.sort(key=lambda x: x["total"], reverse=True)

        # 테이블 미리 보여주기
        if hits:
            table_df = pd.DataFrame([{
                "Symbol": h["symbol"],
                "Name": h["name"],
                "Score": h["total"],
                "Grade": h["grade"]
            } for h in hits])
            st.write("🔔 감지 결과 요약 (점수 내림차순)")
            st.dataframe(table_df, use_container_width=True, hide_index=True)

        # 텔레그램 메시지(하나의 메시지로)
        if hits:
            lines = []
            lines.append("🔔 <b>MA 터치 기반 분할매수 감지 결과</b> (일봉·주봉)\n")
            for h in hits:
                lines.append(f"▪️ <b>{h['name']} ({h['symbol']})</b> — 점수 {h['total']} / {h['grade']}")
                lines.append(h["detail"])
                lines.append("")  # 빈 줄
            lines.append(f"📅 기준시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            msg = "\n".join(lines).strip()
            ok = send_telegram_message(msg)
            if ok:
                st.success("텔레그램으로 감지 결과를 전송했습니다.")
            else:
                st.warning("텔레그램 전송에 실패했습니다. BOT_TOKEN/CHAT_ID를 확인하세요.")
        else:
            st.info("현재 감지된 교차/조건 충족 종목이 없습니다.")
    # 세션 내 중복 알림 방지
    st.session_state.did_notify = True

# ───────────────────────────────────────────────────────────────────────────────
# 차트: 선택된 종목만 표시 (일봉/주봉)
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader(f"📊 {symbol_name} ({symbol}) — {'일봉' if timeframe=='일봉' else '주봉'} 차트")

if timeframe == "일봉":
    df_show = fetch_history(symbol, interval="1d", period="3y")
else:
    df_show = fetch_history(symbol, interval="1wk", period="10y")

plot_price_ma(df_show, f"{symbol_name} ({symbol}) — {'Daily' if timeframe=='일봉' else 'Weekly'}")

# ───────────────────────────────────────────────────────────────────────────────
# 각 주기에서의 현재 점수/사유 확인(선택 종목)
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("### 📌 현재 시그널 점검")
sig_sel = detect_signals_for_symbol(symbol)
d_sig = sig_sel.get("daily")
w_sig = sig_sel.get("weekly")
total_score = combine_score(d_sig, w_sig)
st.write(f"- 종합 점수: **{total_score}** / {score_grade(total_score)}")
if d_sig:
    st.write(f"- 일봉 {d_sig[1]}: {d_sig[0]}점 — {', '.join(d_sig[2])}")
else:
    st.write("- 일봉: 해당 없음")
if w_sig:
    st.write(f"- 주봉 {w_sig[1]}: {w_sig[0]}점 — {', '.join(w_sig[2])}")
else:
    st.write("- 주봉: 해당 없음")

st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  데이터 소스: Yahoo Finance (yfinance)")
