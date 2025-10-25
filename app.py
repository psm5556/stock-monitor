# app.py
import os
import math
import requests
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# =========================
# 환경 변수 (제공값 기본 세팅)
# =========================
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8457877356:AAEam56w8yHqX-ymfGArr3BXAlhmjJB2pDA')
CHAT_ID = os.environ.get('CHAT_ID', '5877958037')

# =========================
# UI 기본 설정
# =========================
st.set_page_config(page_title="📈 장기 MA 접근 모니터", layout="wide")
st.title("📈 장기(200/240/365) 이동평균선 접근 모니터 — 일봉 & 주봉")

st.caption("목적: 하락 추세에서 장기 MA(200/240/365)에 **접근/터치**하는 순간을 포착하여 저점 분할매수 기회를 찾습니다.")

# =========================
# 모니터링 대상 티커 (원하시면 자유롭게 수정)
# =========================
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

MA_LIST = [200, 240, 365]

# =========================
# 유틸: 회사명 얻기
# =========================
@st.cache_data(ttl=86400)
def get_company_name(symbol: str) -> str:
    try:
        t = yf.Ticker(symbol)
        # 새 fast_info에 이름이 없을 수 있으니 info와 병행
        info = t.info
        name = info.get("longName") or info.get("shortName")
        if name:
            return name
    except Exception:
        pass
    return symbol  # 실패 시 심볼로 반환

@st.cache_data(ttl=86400)
def build_symbol_map_and_sorted_list(tickers: list[str]) -> tuple[dict, list[str]]:
    """
    {symbol: company_name} 맵과, 회사명 기준 정렬된 "Company (SYMBOL)" 표시 목록을 반환
    """
    mapping = {}
    for sym in tickers:
        mapping[sym] = get_company_name(sym)
    # 표시 문자열 생성
    display_list = [f"{mapping[sym]} ({sym})" for sym in tickers]
    # 회사명으로 정렬
    display_list_sorted = sorted(display_list, key=lambda s: s.lower())
    return mapping, display_list_sorted

# =========================
# 가격 데이터 (일/주봉)
# =========================
@st.cache_data(ttl=3600)
def get_price(symbol: str, interval: str = "1d") -> pd.DataFrame | None:
    """
    yfinance.Ticker(symbol).history()만 사용.
    interval: "1d" 또는 "1wk"
    period: 일봉 3y, 주봉 10y (MA365 계산 여유)
    """
    period = "10y" if interval == "1wk" else "3y"
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval)
        if df is None or df.empty:
            return None
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        # 장기 이동평균
        for p in MA_LIST:
            df[f"MA{p}"] = df["Close"].rolling(p).mean()
        # 계산 가능한 구간만 사용
        df = df.dropna()
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"[{symbol}][{interval}] get_price error:", str(e))
        return None

# =========================
# 장기 하락 중 MA '접근/터치' 감지
# =========================
def is_downtrend(df: pd.DataFrame, lookback: int = 20) -> bool:
    """
    보수적 하락 판단: 최근 lookback 구간에서 Close 기울기 음수
    + MA200 기울기도 음수면 더 확실한 하락.
    """
    if len(df) < lookback + 1:
        return False
    close_slope = (df["Close"].iloc[-1] - df["Close"].iloc[-lookback]) / lookback
    ma200_slope = (
        (df["MA200"].iloc[-1] - df["MA200"].iloc[-lookback]) / lookback
        if "MA200" in df.columns
        else 0
    )
    return (close_slope < 0) or (ma200_slope < 0)

def detect_ma_touch(df: pd.DataFrame, tolerance: float = 0.005) -> list[int]:
    """
    현재가가 각 MA 대비 허용오차(tolerance, 예: 0.5%) 이내면 '접근/터치'
    """
    touches = []
    if df is None or df.empty:
        return touches
    last = df.iloc[-1]
    for p in MA_LIST:
        col = f"MA{p}"
        if col not in df.columns or pd.isna(last[col]):
            continue
        gap = abs(last["Close"] - last[col]) / last[col]
        if gap <= tolerance:
            touches.append(p)
    return touches

def detect_signals_for_symbol(symbol: str) -> dict:
    """
    심볼 단위로 일봉/주봉 모두 검사.
    하락 추세 + MA 접근/터치가 있을 때만 기록.
    반환: {"symbol": str, "name": str, "daily": [..], "weekly": [..]}
    """
    name = get_company_name(symbol)
    out = {"symbol": symbol, "name": name, "daily": [], "weekly": []}

    # 일봉
    dfd = get_price(symbol, "1d")
    if dfd is not None and not dfd.empty:
        if is_downtrend(dfd):
            touches_d = detect_ma_touch(dfd, tolerance=0.005)  # 0.5%
            if touches_d:
                out["daily"] = touches_d

    # 주봉
    dfw = get_price(symbol, "1wk")
    if dfw is not None and not dfw.empty:
        if is_downtrend(dfw):
            touches_w = detect_ma_touch(dfw, tolerance=0.005)
            if touches_w:
                out["weekly"] = touches_w

    return out

# =========================
# Telegram 전송 (한 번에 묶어서 1건)
# =========================
def send_telegram_message(text: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text})
        ok = (r.status_code == 200)
        if not ok:
            print("Telegram error:", r.text)
        return ok
    except Exception as e:
        print("Telegram exception:", str(e))
        return False

def build_alert_message(results: list[dict]) -> str:
    """
    감지 결과를 한 건의 메시지로 정리
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"📬 장기 MA 접근 감지 결과 ({ts})\n"
    if not results:
        return header + "이번 스캔에서는 감지된 종목이 없습니다."

    lines = []
    for r in results:
        parts = []
        if r["daily"]:
            parts.append(f"일봉: {', '.join([f'MA{p}' for p in r['daily']])}")
        if r["weekly"]:
            parts.append(f"주봉: {', '.join([f'MA{p}' for p in r['weekly']])}")
        if parts:
            lines.append(f"- {r['name']} ({r['symbol']}): " + " / ".join(parts))

    if not lines:
        return header + "이번 스캔에서는 감지된 종목이 없습니다."

    body = "\n".join(lines)
    msg = header + body
    # 텔레그램 4096자 제한 대비 (되도록 한 건 유지, 초과시 뒤를 잘라 알림)
    if len(msg) > 3800:
        msg = msg[:3700] + "\n…(너무 많은 결과로 일부 생략)"
    return msg

# =========================
# 앱 최초 실행 시에만 전체 스캔 & 전송
# =========================
if "scan_done_once" not in st.session_state:
    with st.spinner("초기 스캔 중… (일봉/주봉)"):
        results = []
        for sym in available_tickers:
            r = detect_signals_for_symbol(sym)
            if r["daily"] or r["weekly"]:
                results.append(r)

        st.session_state["scan_done_once"] = True
        st.session_state["scan_results"] = results

        # 텔레그램 1건 전송
        msg = build_alert_message(results)
        ok = send_telegram_message(msg)
        if ok:
            st.success("Telegram으로 감지 요약을 1건 전송했습니다.")
        else:
            st.warning("Telegram 전송에 실패했습니다. BOT_TOKEN/CHAT_ID 및 네트워크를 확인하세요.")

# =========================
# 사이드바: 티커 선택 (회사명 정렬), 프리 텍스트 입력
# =========================
symbol_map, display_options = build_symbol_map_and_sorted_list(available_tickers)

st.sidebar.header("종목 선택")
sel_display = st.sidebar.selectbox("목록에서 선택 (회사명 오름차순)", display_options, index=0)
typed_symbol = st.sidebar.text_input("또는 직접 티커 입력 (우선 적용)", value="")

# 선택 티커 결정
if typed_symbol.strip():
    selected_symbol = typed_symbol.strip().upper()
    selected_name = get_company_name(selected_symbol)
else:
    # "Company (SYMBOL)" → SYMBOL 파싱
    selected_symbol = sel_display.split("(")[-1].replace(")", "").strip()
    selected_name = symbol_map.get(selected_symbol, selected_symbol)

# 차트 주기 선택 (일/주)
chart_interval = st.sidebar.radio("차트 주기", options=["1d", "1wk"], format_func=lambda x: "일봉" if x=="1d" else "주봉", index=0)

# =========================
# 본문: 스캔 요약 테이블 + 선택 종목 차트
# =========================
st.subheader("🔎 초기 스캔 요약 (앱 시작 시 1회)")
scan_results = st.session_state.get("scan_results", [])

if scan_results:
    rows = []
    for r in scan_results:
        rows.append({
            "Symbol": r["symbol"],
            "Company": r["name"],
            "Daily Touch": ", ".join([f"MA{p}" for p in r["daily"]]) if r["daily"] else "",
            "Weekly Touch": ", ".join([f"MA{p}" for p in r["weekly"]]) if r["weekly"] else "",
        })
    df_summary = pd.DataFrame(rows).sort_values(["Company", "Symbol"]).reset_index(drop=True)
    st.dataframe(df_summary, use_container_width=True, hide_index=True)
else:
    st.info("이번 초기 스캔에서는 감지된 종목이 없습니다.")

# =========================
# 선택 종목 차트 (Plotly, y축 자동 스케일)
# =========================
import plotly.graph_objects as go

def plot_price_with_ma(df: pd.DataFrame, symbol: str, name: str, interval: str):
    if df is None or df.empty:
        st.error("데이터가 없습니다.")
        return
    title = f"{name} ({symbol}) — {'일봉' if interval=='1d' else '주봉'}"
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="가격", increasing_line_color="red", decreasing_line_color="blue"
    ))
    for p, color in zip(MA_LIST, ["#7752fe", "#f97316", "#6b7280"]):
        col = f"MA{p}"
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[col], mode="lines", name=f"MA{p}", line=dict(width=2, color=color)))

    # y축 자동 (plotly 기본이 auto지만, margin 여유)
    ymin = min(df[["Low"] + [f"MA{p}" for p in MA_LIST if f"MA{p}" in df.columns]].min())
    ymax = max(df[["High"] + [f"MA{p}" for p in MA_LIST if f"MA{p}" in df.columns]].max())
    pad = (ymax - ymin) * 0.07 if math.isfinite(ymax - ymin) else 0
    fig.update_yaxes(range=[ymin - pad, ymax + pad])

    fig.update_layout(
        title=title, xaxis_title="Date", yaxis_title="Price",
        xaxis=dict(rangeslider=dict(visible=False)),
        height=560, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("📊 선택 종목 차트")
df_chart = get_price(selected_symbol, chart_interval)
if df_chart is None:
    st.error("데이터 조회 실패 (해당 티커/거래소의 주기 데이터가 부족할 수 있습니다).")
else:
    plot_price_with_ma(df_chart, selected_symbol, selected_name, chart_interval)

st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
