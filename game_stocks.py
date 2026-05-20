import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# pykrx
from pykrx import stock as krx

# yfinance (넥슨 도쿄 상장)
import yfinance as yf

# plotly
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ───────────────────────────────────────────
# 종목 정의
# ───────────────────────────────────────────
GAME_STOCKS = {
    # 대형주
    "259960": {"name": "크래프톤",    "market": "KOSPI", "yf": "259960.KS"},
    "263750": {"name": "펄어비스",    "market": "KOSPI", "yf": "263750.KS"},
    "036570": {"name": "엔씨소프트",  "market": "KOSPI", "yf": "036570.KS"},
    "251270": {"name": "넷마블",      "market": "KOSPI", "yf": "251270.KS"},
    "462870": {"name": "시프트업",    "market": "KOSPI", "yf": "462870.KS"},
    # 중형주
    "293490": {"name": "카카오게임즈","market": "KOSDAQ","yf": "293490.KQ"},
    "095660": {"name": "네오위즈",    "market": "KOSDAQ","yf": "095660.KQ"},
    "225570": {"name": "넥슨게임즈",  "market": "KOSDAQ","yf": "225570.KQ"},
    "078340": {"name": "컴투스",      "market": "KOSDAQ","yf": "078340.KQ"},
    "078630": {"name": "게임빌(컴투스홀딩스)", "market": "KOSDAQ","yf": "078630.KQ"},
    # 소형주
    "069080": {"name": "웹젠",        "market": "KOSDAQ","yf": "069080.KQ"},
    "194480": {"name": "데브시스터즈","market": "KOSDAQ","yf": "194480.KQ"},
    "112040": {"name": "위메이드",    "market": "KOSDAQ","yf": "112040.KQ"},
    "067000": {"name": "조이시티",    "market": "KOSDAQ","yf": "067000.KQ"},
    "123420": {"name": "선데이토즈",  "market": "KOSDAQ","yf": "123420.KQ"},
    "201060": {"name": "미투온",      "market": "KOSDAQ","yf": "201060.KQ"},
    # 해외 상장
    "3659.T": {"name": "넥슨(도쿄)",  "market": "TSE",   "yf": "3659.T"},
}

# KRX 티커 (TSE 제외)
KRX_TICKERS = {k: v for k, v in GAME_STOCKS.items() if v["market"] != "TSE"}

# ───────────────────────────────────────────
# 페이지 설정
# ───────────────────────────────────────────
st.set_page_config(
    page_title="한국 게임주 트래커",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }
.stApp { background: #0d1117; color: #e6edf3; }

/* 메트릭 카드 */
.metric-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 8px;
    transition: border-color .2s;
}
.metric-card:hover { border-color: #58a6ff; }
.metric-label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 4px; }
.metric-value { font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 600; }
.metric-sub { font-size: 12px; margin-top: 3px; }
.up   { color: #3fb950; }
.down { color: #f85149; }
.flat { color: #8b949e; }

/* 섹션 헤더 */
.section-header {
    font-size: 13px; font-weight: 700; color: #8b949e;
    text-transform: uppercase; letter-spacing: .1em;
    border-bottom: 1px solid #21262d; padding-bottom: 6px; margin: 20px 0 12px;
}

/* 사이드바 */
[data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }

/* 탭 */
.stTabs [data-baseweb="tab"] { color: #8b949e; }
.stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom-color: #58a6ff !important; }

/* 데이터프레임 */
.dataframe { font-family: 'JetBrains Mono', monospace; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────
# 데이터 로드 함수
# ───────────────────────────────────────────

def today_str():
    return datetime.today().strftime("%Y%m%d")

def n_days_ago_str(n=90):
    return (datetime.today() - timedelta(days=n)).strftime("%Y%m%d")

@st.cache_data(ttl=1800, show_spinner=False)
def load_price_data(ticker: str, days: int = 90) -> pd.DataFrame:
    """KRX 주가 데이터 (일봉)"""
    try:
        df = krx.get_market_ohlcv_by_date(n_days_ago_str(days), today_str(), ticker)
        df.index = pd.to_datetime(df.index)
        df.columns = ["open","high","low","close","volume","value","change_pct"]
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=1800, show_spinner=False)
def load_price_yf(ticker_yf: str, days: int = 90) -> pd.DataFrame:
    """yfinance 주가 (도쿄 상장 넥슨 등)"""
    try:
        end = datetime.today()
        start = end - timedelta(days=days)
        df = yf.download(ticker_yf, start=start, end=end, progress=False)
        if df.empty:
            return pd.DataFrame()
        df = df[["Open","High","Low","Close","Volume"]].copy()
        df.columns = ["open","high","low","close","volume"]
        df["change_pct"] = df["close"].pct_change() * 100
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def load_fundamental(ticker: str) -> dict:
    """시총, 외인비율 등 기본 정보"""
    try:
        df = krx.get_market_cap_by_date(n_days_ago_str(5), today_str(), ticker)
        if df.empty:
            return {}
        latest = df.iloc[-1]
        return {
            "market_cap": int(latest.get("시가총액", 0)),
            "shares": int(latest.get("상장주식수", 0)),
        }
    except Exception:
        return {}

@st.cache_data(ttl=3600, show_spinner=False)
def load_foreign_ratio(ticker: str, days: int = 60) -> pd.DataFrame:
    """외국인 보유 비율"""
    try:
        df = krx.get_exhaustion_rates_of_foreign_investment_by_date(
            n_days_ago_str(days), today_str(), ticker
        )
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def load_shorting_volume(ticker: str, days: int = 60) -> pd.DataFrame:
    """공매도 거래량 및 비중"""
    try:
        df = krx.get_shorting_volume_by_date(
            n_days_ago_str(days), today_str(), ticker
        )
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def load_shorting_balance(ticker: str, days: int = 60) -> pd.DataFrame:
    """공매도 잔고"""
    try:
        df = krx.get_shorting_balance_by_date(
            n_days_ago_str(days), today_str(), ticker
        )
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=1800, show_spinner=False)
def load_investor_trading(ticker: str, days: int = 30) -> pd.DataFrame:
    """투자자별 순매수 (외국인/기관/개인)"""
    try:
        df = krx.get_market_trading_value_by_date(
            n_days_ago_str(days), today_str(), ticker
        )
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()

# ───────────────────────────────────────────
# 요약 행 계산
# ───────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def build_summary_table() -> pd.DataFrame:
    rows = []
    for ticker, meta in GAME_STOCKS.items():
        is_tse = meta["market"] == "TSE"
        if is_tse:
            price_df = load_price_yf(meta["yf"], days=5)
        else:
            price_df = load_price_data(ticker, days=5)

        if price_df.empty:
            continue

        latest = price_df.iloc[-1]
        prev   = price_df.iloc[-2] if len(price_df) > 1 else latest

        close      = float(latest["close"])
        prev_close = float(prev["close"])
        chg_pct    = (close - prev_close) / prev_close * 100 if prev_close else 0
        vol        = int(latest["volume"])

        hi52 = float(price_df["high"].max()) if len(price_df) >= 2 else close
        lo52 = float(price_df["low"].min())  if len(price_df) >= 2 else close

        short_ratio = None
        foreign_ratio = None

        if not is_tse:
            sv = load_shorting_volume(ticker, days=5)
            if not sv.empty:
                last_sv = sv.iloc[-1]
                cols = sv.columns.tolist()
                # 공매도비중 컬럼 찾기
                ratio_col = next((c for c in cols if "비중" in c or "ratio" in c.lower()), None)
                if ratio_col:
                    short_ratio = float(last_sv[ratio_col])

            fr = load_foreign_ratio(ticker, days=5)
            if not fr.empty:
                cols = fr.columns.tolist()
                ratio_col = next((c for c in cols if "보유율" in c or "비율" in c or "ratio" in c.lower()), None)
                if ratio_col:
                    foreign_ratio = float(fr.iloc[-1][ratio_col])

        rows.append({
            "티커": ticker,
            "종목명": meta["name"],
            "시장": meta["market"],
            "현재가": close,
            "등락률(%)": round(chg_pct, 2),
            "거래량": vol,
            "52주고": hi52,
            "52주저": lo52,
            "공매도비중(%)": short_ratio,
            "외인보유율(%)": foreign_ratio,
        })

    return pd.DataFrame(rows)

# ───────────────────────────────────────────
# 사이드바
# ───────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎮 게임주 트래커")
    st.markdown("---")

    selected_tickers = st.multiselect(
        "종목 선택",
        options=list(GAME_STOCKS.keys()),
        default=list(GAME_STOCKS.keys())[:8],
        format_func=lambda x: f"{GAME_STOCKS[x]['name']} ({x})",
    )

    period_map = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
    selected_period_label = st.selectbox("기간", list(period_map.keys()), index=1)
    selected_period = period_map[selected_period_label]

    chart_type = st.radio("차트 유형", ["캔들", "라인"], horizontal=True)

    st.markdown("---")
    if st.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"마지막 업데이트: {datetime.now().strftime('%H:%M:%S')}")

# ───────────────────────────────────────────
# 메인 헤더
# ───────────────────────────────────────────
st.markdown("## 🎮 한국 게임주 트래커")
st.markdown(f"<span style='color:#8b949e;font-size:13px'>{datetime.today().strftime('%Y년 %m월 %d일')} 기준 · KRX 데이터</span>", unsafe_allow_html=True)
st.markdown("---")

# ───────────────────────────────────────────
# 탭 구성
# ───────────────────────────────────────────
tab_overview, tab_chart, tab_short, tab_foreign, tab_investor = st.tabs([
    "📊 종목 요약", "📈 주가 차트", "🔻 공매도", "🌍 외국인", "💰 투자자 동향"
])

# ══════════════════════════════════════════
# TAB 1 — 종목 요약
# ══════════════════════════════════════════
with tab_overview:
    with st.spinner("요약 데이터 로딩 중..."):
        summary = build_summary_table()

    if summary.empty:
        st.warning("데이터를 불러올 수 없습니다.")
    else:
        # 필터
        display = summary[summary["티커"].isin(selected_tickers)] if selected_tickers else summary

        # 상단 KPI
        col1, col2, col3, col4 = st.columns(4)
        ups   = (display["등락률(%)"] > 0).sum()
        downs = (display["등락률(%)"] < 0).sum()
        avg_chg = display["등락률(%)"].mean()

        with col1:
            st.metric("추적 종목 수", f"{len(display)}개")
        with col2:
            st.metric("상승 종목", f"{ups}개", delta=f"하락 {downs}개")
        with col3:
            color = "normal" if avg_chg >= 0 else "inverse"
            st.metric("평균 등락률", f"{avg_chg:+.2f}%")
        with col4:
            avg_short = display["공매도비중(%)"].dropna().mean()
            st.metric("평균 공매도비중", f"{avg_short:.2f}%" if not np.isnan(avg_short) else "N/A")

        st.markdown('<div class="section-header">종목별 현황</div>', unsafe_allow_html=True)

        # 등락률 컬러 포맷
        def color_change(val):
            if pd.isna(val): return ""
            c = "#3fb950" if val > 0 else "#f85149" if val < 0 else "#8b949e"
            return f"color: {c}; font-weight: 600"

        def color_short(val):
            if pd.isna(val): return ""
            c = "#f85149" if val > 5 else "#e3b341" if val > 2 else "#3fb950"
            return f"color: {c}"

        styled = display.style \
            .applymap(color_change, subset=["등락률(%)"]) \
            .applymap(color_short, subset=["공매도비중(%)"]) \
            .format({
                "현재가": "{:,.0f}",
                "등락률(%)": "{:+.2f}%",
                "거래량": "{:,.0f}",
                "52주고": "{:,.0f}",
                "52주저": "{:,.0f}",
                "공매도비중(%)": lambda x: f"{x:.2f}%" if pd.notna(x) else "-",
                "외인보유율(%)": lambda x: f"{x:.2f}%" if pd.notna(x) else "-",
            }) \
            .hide(axis="index")

        st.dataframe(styled, use_container_width=True, height=500)

        # 등락률 바 차트
        st.markdown('<div class="section-header">등락률 비교</div>', unsafe_allow_html=True)
        fig_bar = go.Figure(go.Bar(
            x=display["종목명"],
            y=display["등락률(%)"],
            marker_color=[
                "#3fb950" if v > 0 else "#f85149" if v < 0 else "#8b949e"
                for v in display["등락률(%)"]
            ],
            text=[f"{v:+.2f}%" for v in display["등락률(%)"]],
            textposition="outside",
        ))
        fig_bar.update_layout(
            paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
            font_color="#e6edf3", height=300,
            xaxis=dict(tickfont=dict(size=11)),
            yaxis=dict(zeroline=True, zerolinecolor="#30363d", gridcolor="#21262d"),
            margin=dict(t=20, b=40),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ══════════════════════════════════════════
# TAB 2 — 주가 차트
# ══════════════════════════════════════════
with tab_chart:
    if not selected_tickers:
        st.info("사이드바에서 종목을 선택해주세요.")
    else:
        chart_ticker = st.selectbox(
            "차트 종목",
            options=selected_tickers,
            format_func=lambda x: f"{GAME_STOCKS[x]['name']} ({x})",
            key="chart_sel"
        )
        meta = GAME_STOCKS[chart_ticker]

        with st.spinner(f"{meta['name']} 데이터 로딩..."):
            if meta["market"] == "TSE":
                price_df = load_price_yf(meta["yf"], days=selected_period)
            else:
                price_df = load_price_data(chart_ticker, days=selected_period)

        if price_df.empty:
            st.warning("가격 데이터를 불러올 수 없습니다.")
        else:
            # 이동평균
            price_df["ma5"]  = price_df["close"].rolling(5).mean()
            price_df["ma20"] = price_df["close"].rolling(20).mean()
            price_df["ma60"] = price_df["close"].rolling(60).mean()

            fig = make_subplots(
                rows=3, cols=1,
                row_heights=[0.6, 0.2, 0.2],
                shared_xaxes=True,
                vertical_spacing=0.03,
                subplot_titles=["", "거래량", "공매도비중(%)"],
            )

            if chart_type == "캔들":
                fig.add_trace(go.Candlestick(
                    x=price_df.index,
                    open=price_df["open"], high=price_df["high"],
                    low=price_df["low"],   close=price_df["close"],
                    increasing_line_color="#3fb950",
                    decreasing_line_color="#f85149",
                    name="OHLC",
                ), row=1, col=1)
            else:
                fig.add_trace(go.Scatter(
                    x=price_df.index, y=price_df["close"],
                    line=dict(color="#58a6ff", width=2), name="종가"
                ), row=1, col=1)

            for ma, color, name in [
                ("ma5","#f0e68c","MA5"),("ma20","#ff8c00","MA20"),("ma60","#da70d6","MA60")
            ]:
                fig.add_trace(go.Scatter(
                    x=price_df.index, y=price_df[ma],
                    line=dict(color=color, width=1, dash="dot"),
                    name=name, opacity=0.8
                ), row=1, col=1)

            # 거래량
            vol_colors = [
                "#3fb950" if price_df["close"].iloc[i] >= price_df["close"].iloc[i-1]
                else "#f85149"
                for i in range(len(price_df))
            ]
            fig.add_trace(go.Bar(
                x=price_df.index, y=price_df["volume"],
                marker_color=vol_colors, name="거래량", showlegend=False,
            ), row=2, col=1)

            # 공매도비중 (KRX만)
            if meta["market"] != "TSE":
                sv = load_shorting_volume(chart_ticker, days=selected_period)
                if not sv.empty:
                    cols = sv.columns.tolist()
                    ratio_col = next((c for c in cols if "비중" in c), None)
                    if ratio_col:
                        fig.add_trace(go.Bar(
                            x=sv.index, y=sv[ratio_col],
                            marker_color="#f0883e", name="공매도비중", showlegend=False,
                        ), row=3, col=1)

            fig.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font_color="#e6edf3", height=600,
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", y=1.02, x=0),
                margin=dict(t=30, b=20),
            )
            for i in range(1, 4):
                fig.update_xaxes(gridcolor="#21262d", showgrid=True, row=i, col=1)
                fig.update_yaxes(gridcolor="#21262d", showgrid=True, row=i, col=1)

            st.plotly_chart(fig, use_container_width=True)

            # 상대 수익률 비교
            st.markdown('<div class="section-header">선택 종목 상대 수익률 비교</div>', unsafe_allow_html=True)
            fig_rel = go.Figure()
            for t in selected_tickers[:8]:  # 최대 8개
                m = GAME_STOCKS[t]
                if m["market"] == "TSE":
                    df_t = load_price_yf(m["yf"], days=selected_period)
                else:
                    df_t = load_price_data(t, days=selected_period)
                if df_t.empty or len(df_t) < 2:
                    continue
                base = df_t["close"].iloc[0]
                rel  = (df_t["close"] / base - 1) * 100
                fig_rel.add_trace(go.Scatter(
                    x=df_t.index, y=rel,
                    name=m["name"], mode="lines", line=dict(width=1.5)
                ))
            fig_rel.add_hline(y=0, line_dash="dot", line_color="#30363d")
            fig_rel.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font_color="#e6edf3", height=320,
                xaxis=dict(gridcolor="#21262d"),
                yaxis=dict(gridcolor="#21262d", ticksuffix="%"),
                margin=dict(t=10, b=20),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_rel, use_container_width=True)

# ══════════════════════════════════════════
# TAB 3 — 공매도
# ══════════════════════════════════════════
with tab_short:
    st.markdown('<div class="section-header">공매도 거래량 · 잔고 현황</div>', unsafe_allow_html=True)

    short_ticker = st.selectbox(
        "공매도 조회 종목",
        options=[t for t in selected_tickers if GAME_STOCKS[t]["market"] != "TSE"],
        format_func=lambda x: f"{GAME_STOCKS[x]['name']} ({x})",
        key="short_sel"
    )

    if short_ticker:
        col_sv, col_sb = st.columns(2)

        with col_sv:
            st.markdown("**공매도 거래량 & 비중**")
            with st.spinner("로딩..."):
                sv = load_shorting_volume(short_ticker, days=selected_period)

            if not sv.empty:
                cols = sv.columns.tolist()
                vol_col   = next((c for c in cols if "거래량" in c and "공매도" in c), cols[0] if cols else None)
                ratio_col = next((c for c in cols if "비중" in c), None)

                fig_sv = make_subplots(specs=[[{"secondary_y": True}]])
                if vol_col:
                    fig_sv.add_trace(go.Bar(
                        x=sv.index, y=sv[vol_col],
                        name="공매도거래량", marker_color="rgba(248,81,73,0.6)"
                    ), secondary_y=False)
                if ratio_col:
                    fig_sv.add_trace(go.Scatter(
                        x=sv.index, y=sv[ratio_col],
                        name="공매도비중(%)", line=dict(color="#f0883e", width=2)
                    ), secondary_y=True)

                fig_sv.update_layout(
                    paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                    font_color="#e6edf3", height=300,
                    xaxis=dict(gridcolor="#21262d"),
                    yaxis=dict(gridcolor="#21262d"),
                    margin=dict(t=10, b=20),
                    legend=dict(orientation="h", y=1.05),
                )
                st.plotly_chart(fig_sv, use_container_width=True)
            else:
                st.info("공매도 거래량 데이터 없음")

        with col_sb:
            st.markdown("**공매도 잔고 & 잔고비율**")
            with st.spinner("로딩..."):
                sb = load_shorting_balance(short_ticker, days=selected_period)

            if not sb.empty:
                cols = sb.columns.tolist()
                bal_col   = next((c for c in cols if "잔고" in c and "비율" not in c), cols[0] if cols else None)
                ratio_col = next((c for c in cols if "비율" in c or "비중" in c), None)

                fig_sb = make_subplots(specs=[[{"secondary_y": True}]])
                if bal_col:
                    fig_sb.add_trace(go.Bar(
                        x=sb.index, y=sb[bal_col],
                        name="공매도잔고", marker_color="rgba(240,136,62,0.5)"
                    ), secondary_y=False)
                if ratio_col:
                    fig_sb.add_trace(go.Scatter(
                        x=sb.index, y=sb[ratio_col],
                        name="잔고비율(%)", line=dict(color="#ffa657", width=2)
                    ), secondary_y=True)

                fig_sb.update_layout(
                    paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                    font_color="#e6edf3", height=300,
                    xaxis=dict(gridcolor="#21262d"),
                    yaxis=dict(gridcolor="#21262d"),
                    margin=dict(t=10, b=20),
                    legend=dict(orientation="h", y=1.05),
                )
                st.plotly_chart(fig_sb, use_container_width=True)
            else:
                st.info("공매도 잔고 데이터 없음")

        # 전종목 공매도비중 비교
        st.markdown('<div class="section-header">전 종목 공매도비중 비교 (최근)</div>', unsafe_allow_html=True)
        short_rows = []
        krx_selected = [t for t in selected_tickers if GAME_STOCKS[t]["market"] != "TSE"]
        for t in krx_selected:
            sv = load_shorting_volume(t, days=5)
            sb = load_shorting_balance(t, days=5)
            ratio = None
            bal_ratio = None
            if not sv.empty:
                cols = sv.columns.tolist()
                rc = next((c for c in cols if "비중" in c), None)
                if rc:
                    ratio = float(sv.iloc[-1][rc])
            if not sb.empty:
                cols = sb.columns.tolist()
                rc = next((c for c in cols if "비율" in c or "비중" in c), None)
                if rc:
                    bal_ratio = float(sb.iloc[-1][rc])
            short_rows.append({
                "종목명": GAME_STOCKS[t]["name"],
                "공매도거래비중(%)": ratio,
                "공매도잔고비율(%)": bal_ratio,
            })

        df_short = pd.DataFrame(short_rows).dropna(how="all", subset=["공매도거래비중(%)","공매도잔고비율(%)"])
        if not df_short.empty:
            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Bar(
                name="거래비중(%)", x=df_short["종목명"], y=df_short["공매도거래비중(%)"],
                marker_color="#f85149"
            ))
            fig_cmp.add_trace(go.Bar(
                name="잔고비율(%)", x=df_short["종목명"], y=df_short["공매도잔고비율(%)"],
                marker_color="#f0883e"
            ))
            fig_cmp.update_layout(
                barmode="group",
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font_color="#e6edf3", height=320,
                xaxis=dict(gridcolor="#21262d"),
                yaxis=dict(gridcolor="#21262d", ticksuffix="%"),
                margin=dict(t=10, b=20),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_cmp, use_container_width=True)

# ══════════════════════════════════════════
# TAB 4 — 외국인
# ══════════════════════════════════════════
with tab_foreign:
    st.markdown('<div class="section-header">외국인 보유율 추이</div>', unsafe_allow_html=True)

    foreign_ticker = st.selectbox(
        "외국인 조회 종목",
        options=[t for t in selected_tickers if GAME_STOCKS[t]["market"] != "TSE"],
        format_func=lambda x: f"{GAME_STOCKS[x]['name']} ({x})",
        key="foreign_sel"
    )

    if foreign_ticker:
        with st.spinner("외국인 데이터 로딩..."):
            fr = load_foreign_ratio(foreign_ticker, days=selected_period)

        if not fr.empty:
            cols = fr.columns.tolist()
            ratio_col = next((c for c in cols if "보유율" in c or "비율" in c), cols[0] if cols else None)

            price_df2 = load_price_data(foreign_ticker, days=selected_period)

            fig_fr = make_subplots(specs=[[{"secondary_y": True}]])
            if not price_df2.empty:
                fig_fr.add_trace(go.Scatter(
                    x=price_df2.index, y=price_df2["close"],
                    name="주가", line=dict(color="#58a6ff", width=1.5)
                ), secondary_y=False)
            if ratio_col:
                fig_fr.add_trace(go.Scatter(
                    x=fr.index, y=fr[ratio_col],
                    name="외인보유율(%)", line=dict(color="#3fb950", width=2)
                ), secondary_y=True)

            fig_fr.update_layout(
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font_color="#e6edf3", height=380,
                xaxis=dict(gridcolor="#21262d"),
                yaxis=dict(gridcolor="#21262d", title="주가(원)"),
                yaxis2=dict(gridcolor="#21262d", title="외인보유율(%)", ticksuffix="%"),
                margin=dict(t=10, b=20),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_fr, use_container_width=True)

            if ratio_col:
                latest_fr  = float(fr.iloc[-1][ratio_col])
                max_fr     = float(fr[ratio_col].max())
                min_fr     = float(fr[ratio_col].min())
                avg_fr     = float(fr[ratio_col].mean())
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("현재 외인보유율",   f"{latest_fr:.2f}%")
                c2.metric("기간 최고",         f"{max_fr:.2f}%")
                c3.metric("기간 최저",         f"{min_fr:.2f}%")
                c4.metric("기간 평균",         f"{avg_fr:.2f}%")
        else:
            st.info("외국인 보유율 데이터를 불러올 수 없습니다.")

    # 전종목 외인비율 히트맵
    st.markdown('<div class="section-header">전 종목 외인 보유율 히트맵</div>', unsafe_allow_html=True)
    heatmap_data = {}
    krx_sel = [t for t in selected_tickers if GAME_STOCKS[t]["market"] != "TSE"]
    for t in krx_sel:
        fr2 = load_foreign_ratio(t, days=30)
        if fr2.empty:
            continue
        cols = fr2.columns.tolist()
        rc = next((c for c in cols if "보유율" in c or "비율" in c), None)
        if rc:
            heatmap_data[GAME_STOCKS[t]["name"]] = fr2[rc]

    if heatmap_data:
        hm_df = pd.DataFrame(heatmap_data).tail(20)
        fig_hm = go.Figure(go.Heatmap(
            z=hm_df.T.values,
            x=[d.strftime("%m/%d") for d in hm_df.index],
            y=hm_df.columns.tolist(),
            colorscale="RdYlGn",
            text=np.round(hm_df.T.values, 1),
            texttemplate="%{text}",
            colorbar=dict(title="%"),
        ))
        fig_hm.update_layout(
            paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
            font_color="#e6edf3", height=max(300, len(heatmap_data) * 35 + 80),
            margin=dict(t=10, b=20),
        )
        st.plotly_chart(fig_hm, use_container_width=True)

# ══════════════════════════════════════════
# TAB 5 — 투자자 동향
# ══════════════════════════════════════════
with tab_investor:
    st.markdown('<div class="section-header">투자자별 순매수 동향</div>', unsafe_allow_html=True)

    inv_ticker = st.selectbox(
        "투자자 동향 종목",
        options=[t for t in selected_tickers if GAME_STOCKS[t]["market"] != "TSE"],
        format_func=lambda x: f"{GAME_STOCKS[x]['name']} ({x})",
        key="inv_sel"
    )

    if inv_ticker:
        with st.spinner("투자자 데이터 로딩..."):
            inv_df = load_investor_trading(inv_ticker, days=selected_period)

        if not inv_df.empty:
            cols = inv_df.columns.tolist()
            # 외국인/기관/개인 컬럼 찾기
            foreign_col  = next((c for c in cols if "외국인" in c), None)
            inst_col     = next((c for c in cols if "기관" in c), None)
            retail_col   = next((c for c in cols if "개인" in c), None)

            fig_inv = go.Figure()
            for col, color, name in [
                (foreign_col, "#3fb950", "외국인"),
                (inst_col,    "#58a6ff", "기관"),
                (retail_col,  "#f0883e", "개인"),
            ]:
                if col and col in inv_df.columns:
                    fig_inv.add_trace(go.Bar(
                        x=inv_df.index, y=inv_df[col],
                        name=name, marker_color=color
                    ))

            fig_inv.add_hline(y=0, line_color="#30363d", line_dash="dot")
            fig_inv.update_layout(
                barmode="group",
                paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                font_color="#e6edf3", height=380,
                xaxis=dict(gridcolor="#21262d"),
                yaxis=dict(gridcolor="#21262d", tickformat=",.0f"),
                margin=dict(t=10, b=20),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_inv, use_container_width=True)

            # 누적 순매수
            st.markdown("**누적 순매수 (기간 합계)**")
            cumsum_data = {}
            for col, name in [(foreign_col,"외국인"),(inst_col,"기관"),(retail_col,"개인")]:
                if col and col in inv_df.columns:
                    cumsum_data[name] = inv_df[col].sum()
            if cumsum_data:
                fig_cum = go.Figure(go.Bar(
                    x=list(cumsum_data.keys()),
                    y=list(cumsum_data.values()),
                    marker_color=["#3fb950","#58a6ff","#f0883e"],
                    text=[f"{v/1e8:+.1f}억" for v in cumsum_data.values()],
                    textposition="outside",
                ))
                fig_cum.add_hline(y=0, line_color="#30363d", line_dash="dot")
                fig_cum.update_layout(
                    paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                    font_color="#e6edf3", height=280,
                    yaxis=dict(gridcolor="#21262d"),
                    margin=dict(t=20, b=20),
                )
                st.plotly_chart(fig_cum, use_container_width=True)
        else:
            st.info("투자자 데이터를 불러올 수 없습니다.")
