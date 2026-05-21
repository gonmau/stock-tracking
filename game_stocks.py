"""
game_stocks.py
한국 게임주 트래커 대시보드
app.py와 동일한 방식 — GitHub Raw에서 {ticker}_game.json 읽기
pykrx 직접 호출 없음
"""

import requests
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ───────────────────────────────────────────
# 설정
# ───────────────────────────────────────────
GITHUB_RAW = "https://raw.githubusercontent.com/{owner}/{repo}/main/data/{ticker}_game.json"

GAME_STOCKS = {
    # 대형주
    "259960": {"name": "크래프톤",            "market": "KOSPI"},
    "263750": {"name": "펄어비스",            "market": "KOSPI"},
    "036570": {"name": "엔씨소프트",          "market": "KOSPI"},
    "251270": {"name": "넷마블",              "market": "KOSPI"},
    "462870": {"name": "시프트업",            "market": "KOSPI"},
    # 중형주
    "293490": {"name": "카카오게임즈",        "market": "KOSDAQ"},
    "095660": {"name": "네오위즈",            "market": "KOSDAQ"},
    "225570": {"name": "넥슨게임즈",          "market": "KOSDAQ"},
    "078340": {"name": "컴투스",              "market": "KOSDAQ"},
    "078630": {"name": "게임빌(컴투스홀딩스)","market": "KOSDAQ"},
    # 소형주
    "069080": {"name": "웹젠",               "market": "KOSDAQ"},
    "194480": {"name": "데브시스터즈",        "market": "KOSDAQ"},
    "112040": {"name": "위메이드",            "market": "KOSDAQ"},
    "067000": {"name": "조이시티",            "market": "KOSDAQ"},
    "123420": {"name": "선데이토즈",          "market": "KOSDAQ"},
    "201060": {"name": "미투온",              "market": "KOSDAQ"},
}

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

.metric-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 8px;
}
.metric-card:hover { border-color: #58a6ff; }
.metric-label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 4px; }
.metric-value { font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 600; }

.section-header {
    font-size: 13px; font-weight: 700; color: #8b949e;
    text-transform: uppercase; letter-spacing: .1em;
    border-bottom: 1px solid #21262d; padding-bottom: 6px; margin: 20px 0 12px;
}
[data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #21262d; }
.stTabs [data-baseweb="tab"] { color: #8b949e; }
.stTabs [aria-selected="true"] { color: #58a6ff !important; border-bottom-color: #58a6ff !important; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────
# 데이터 로드 (app.py 동일 패턴)
# ───────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_ticker(owner: str, repo: str, ticker: str) -> dict:
    url = GITHUB_RAW.format(owner=owner, repo=repo, ticker=ticker)
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def build_df(meta: dict) -> pd.DataFrame:
    """JSON records → DataFrame. app.py의 build_df와 동일"""
    df = pd.DataFrame(meta["records"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

def get_df(owner: str, repo: str, ticker: str) -> pd.DataFrame:
    meta = load_ticker(owner, repo, ticker)
    if "error" in meta or not meta.get("records"):
        return pd.DataFrame()
    return build_df(meta)

def slice_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    if df.empty:
        return df
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df[df.index >= cutoff]

# ───────────────────────────────────────────
# 사이드바
# ───────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎮 게임주 트래커")
    st.markdown("---")

    owner = st.text_input("GitHub 사용자명", value="gonmau")
    repo  = st.text_input("레포지터리명",    value="stock-tracking")

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

    chart_type = st.radio("차트 유형", ["캔들스틱", "라인"], horizontal=True)

    st.markdown("---")
    if st.button("🔄 새로고침"):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"마지막 업데이트: {datetime.now().strftime('%H:%M:%S')}")

# ───────────────────────────────────────────
# 메인 헤더
# ───────────────────────────────────────────
st.markdown("## 🎮 한국 게임주 트래커")
st.markdown(
    f"<span style='color:#8b949e;font-size:13px'>"
    f"{datetime.today().strftime('%Y년 %m월 %d일')} 기준 · KRX 데이터 (T+2 지연)</span>",
    unsafe_allow_html=True
)
st.markdown("---")

if not selected_tickers:
    st.info("사이드바에서 종목을 선택해주세요.")
    st.stop()

# ───────────────────────────────────────────
# 전종목 데이터 로드 (캐시)
# ───────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_all(owner: str, repo: str, tickers: tuple) -> dict:
    return {t: get_df(owner, repo, t) for t in tickers}

with st.spinner("데이터 로딩 중..."):
    all_data = load_all(owner, repo, tuple(selected_tickers))

# 데이터 전혀 없으면 중단
loaded = [t for t, df in all_data.items() if not df.empty]
if not loaded:
    st.error(
        "데이터를 불러올 수 없습니다.\n\n"
        "1. GitHub 사용자명 / 레포명을 사이드바에서 확인하세요.\n"
        "2. `data/{ticker}_game.json` 파일이 레포에 있는지 확인하세요.\n"
        "3. `game_collector.py`를 먼저 실행해 데이터를 생성하세요.\n"
        "4. 레포가 Public인지 확인하세요."
    )
    st.stop()

# ───────────────────────────────────────────
# 탭 구성
# ───────────────────────────────────────────
tab_overview, tab_chart, tab_short, tab_compare = st.tabs([
    "📊 종목 요약", "📈 주가 & 공매도", "🔻 공매도 비교", "📐 상대 수익률"
])

# ══════════════════════════════════════════
# TAB 1 — 종목 요약
# ══════════════════════════════════════════
with tab_overview:
    rows = []
    for ticker in selected_tickers:
        df = all_data[ticker]
        if df.empty:
            continue
        latest = df.iloc[-1]
        prev   = df.iloc[-2] if len(df) > 1 else latest

        close      = float(latest["close"])
        prev_close = float(prev["close"])
        chg_pct    = (close - prev_close) / prev_close * 100 if prev_close else 0

        df_full = all_data[ticker]
        hi52 = float(df_full["close"].tail(252).max())
        lo52 = float(df_full["close"].tail(252).min())
        pos52 = (close - lo52) / (hi52 - lo52) * 100 if hi52 != lo52 else 50

        rows.append({
            "티커":        ticker,
            "종목명":      GAME_STOCKS[ticker]["name"],
            "시장":        GAME_STOCKS[ticker]["market"],
            "현재가":      close,
            "등락률(%)":   round(chg_pct, 2),
            "거래량":      int(latest["volume"]),
            "공매도잔고(만주)": float(latest.get("balance", 0)),
            "잔고변화(만주)":   float(latest.get("balance_chg", 0)),
            "잔고비율(%)":     float(latest.get("ratio", 0)),
            "52주위치(%)":     round(pos52, 1),
        })

    if not rows:
        st.warning("표시할 데이터가 없습니다.")
    else:
        summary = pd.DataFrame(rows)

        # KPI
        col1, col2, col3, col4 = st.columns(4)
        ups   = (summary["등락률(%)"] > 0).sum()
        downs = (summary["등락률(%)"] < 0).sum()
        avg_chg = summary["등락률(%)"].mean()
        avg_bal = summary["잔고비율(%)"].mean()

        col1.metric("추적 종목", f"{len(summary)}개")
        col2.metric("상승 / 하락", f"{ups} / {downs}")
        col3.metric("평균 등락률", f"{avg_chg:+.2f}%")
        col4.metric("평균 잔고비율", f"{avg_bal:.3f}%")

        st.markdown('<div class="section-header">종목별 현황</div>', unsafe_allow_html=True)

        def color_chg(val):
            if pd.isna(val): return ""
            c = "#3fb950" if val > 0 else "#f85149" if val < 0 else "#8b949e"
            return f"color:{c};font-weight:600"

        def color_bal_chg(val):
            if pd.isna(val): return ""
            c = "#f85149" if val > 0 else "#3fb950" if val < 0 else "#8b949e"
            return f"color:{c}"

        def color_ratio(val):
            if pd.isna(val): return ""
            c = "#f85149" if val > 1.0 else "#e3b341" if val > 0.5 else "#3fb950"
            return f"color:{c}"

        styled = (
            summary.style
            .applymap(color_chg,     subset=["등락률(%)"])
            .applymap(color_bal_chg, subset=["잔고변화(만주)"])
            .applymap(color_ratio,   subset=["잔고비율(%)"])
            .format({
                "현재가":          "{:,.0f}",
                "등락률(%)":       "{:+.2f}%",
                "거래량":          "{:,.0f}",
                "공매도잔고(만주)": "{:.1f}",
                "잔고변화(만주)":   "{:+.2f}",
                "잔고비율(%)":     "{:.3f}%",
                "52주위치(%)":     "{:.1f}%",
            })
            .hide(axis="index")
        )
        st.dataframe(styled, use_container_width=True, height=520)

        # 등락률 바차트
        st.markdown('<div class="section-header">등락률 비교</div>', unsafe_allow_html=True)
        fig_bar = go.Figure(go.Bar(
            x=summary["종목명"],
            y=summary["등락률(%)"],
            marker_color=["#3fb950" if v > 0 else "#f85149" if v < 0 else "#8b949e"
                          for v in summary["등락률(%)"]],
            text=[f"{v:+.2f}%" for v in summary["등락률(%)"]],
            textposition="outside",
        ))
        fig_bar.update_layout(
            paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
            font_color="#e6edf3", height=300,
            yaxis=dict(zeroline=True, zerolinecolor="#30363d", gridcolor="#21262d"),
            margin=dict(t=20, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # 공매도 잔고 바차트
        st.markdown('<div class="section-header">공매도 잔고 비율 비교</div>', unsafe_allow_html=True)
        fig_bal = go.Figure(go.Bar(
            x=summary["종목명"],
            y=summary["잔고비율(%)"],
            marker_color=["#f85149" if v > 1.0 else "#e3b341" if v > 0.5 else "#3fb950"
                          for v in summary["잔고비율(%)"]],
            text=[f"{v:.3f}%" for v in summary["잔고비율(%)"]],
            textposition="outside",
        ))
        fig_bal.update_layout(
            paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
            font_color="#e6edf3", height=300,
            yaxis=dict(gridcolor="#21262d", ticksuffix="%"),
            margin=dict(t=20, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig_bal, use_container_width=True)

# ══════════════════════════════════════════
# TAB 2 — 주가 & 공매도 (app.py 스타일)
# ══════════════════════════════════════════
with tab_chart:
    chart_ticker = st.selectbox(
        "종목 선택",
        options=selected_tickers,
        format_func=lambda x: f"{GAME_STOCKS[x]['name']} ({x})",
        key="chart_sel"
    )

    df = all_data[chart_ticker]
    if df.empty:
        st.warning("데이터 없음 — Actions가 아직 실행되지 않았을 수 있습니다.")
    else:
        meta = load_ticker(owner, repo, chart_ticker)
        updated_at = meta.get("updated_at", "-")
        st.caption(f"마지막 수집: {updated_at}  |  공매도 데이터: T+2 지연")

        d = slice_days(df, selected_period)

        # 상단 KPI (app.py 스타일)
        latest = d.iloc[-1]
        prev   = d.iloc[-2] if len(d) > 1 else latest
        close     = int(latest["close"])
        chg_pct   = (latest["close"] - prev["close"]) / prev["close"] * 100
        bal       = float(latest.get("balance", 0))
        bal_chg   = float(latest.get("balance_chg", 0))
        short_vol = float(latest.get("short_vol", 0))
        ratio     = float(latest.get("ratio", 0))

        c1, c2, c3, c4 = st.columns(4)
        chg_color = "#3fb950" if chg_pct >= 0 else "#f85149"
        bal_color = "#f85149" if bal_chg > 0 else "#3fb950"
        sv_color  = "#f85149" if short_vol >= 200 else "#e3b341" if short_vol >= 100 else "#3fb950"

        c1.markdown(f"""<div class="metric-card">
            <div class="metric-label">현재가</div>
            <div class="metric-value" style="color:#58a6ff">{close:,}원</div>
            <div style="font-size:12px;color:{chg_color}">{chg_pct:+.2f}%</div>
        </div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="metric-card">
            <div class="metric-label">공매도 잔고</div>
            <div class="metric-value" style="color:#f85149">{bal:.1f}만주</div>
            <div style="font-size:12px;color:{bal_color}">전일比 {bal_chg:+.2f}만주</div>
        </div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="metric-card">
            <div class="metric-label">당일 공매도</div>
            <div class="metric-value" style="color:{sv_color}">{short_vol:.0f}천주</div>
        </div>""", unsafe_allow_html=True)
        c4.markdown(f"""<div class="metric-card">
            <div class="metric-label">잔고 비율</div>
            <div class="metric-value">{ratio:.3f}%</div>
            <div style="font-size:11px;color:#8b949e">발행주식 대비</div>
        </div>""", unsafe_allow_html=True)

        # 차트 (app.py의 make_chart 구조 동일)
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            row_heights=[0.5, 0.25, 0.25],
            vertical_spacing=0.03,
            subplot_titles=("주가 & 공매도 잔고", "당일 공매도 (천주)", "거래량 (천주)"),
            specs=[[{"secondary_y": True}], [{"secondary_y": False}], [{"secondary_y": False}]],
        )

        # 주가
        if chart_type == "캔들스틱" and "open" in d.columns:
            fig.add_trace(go.Candlestick(
                x=d.index,
                open=d["open"], high=d["high"], low=d["low"], close=d["close"],
                increasing_line_color="#3fb950", decreasing_line_color="#f85149",
                name="주가",
            ), row=1, col=1, secondary_y=False)
        else:
            fig.add_trace(go.Scatter(
                x=d.index, y=d["close"],
                line=dict(color="#58a6ff", width=2), name="주가"
            ), row=1, col=1, secondary_y=False)

        # 이평선
        for ma_col, color, label in [("price_5ma","#ffd93d","5MA"),("price_20ma","#ff9f43","20MA")]:
            if ma_col in d.columns:
                fig.add_trace(go.Scatter(
                    x=d.index, y=d[ma_col],
                    line=dict(color=color, width=1, dash="dot"), name=label
                ), row=1, col=1, secondary_y=False)

        # 공매도 잔고 (우축)
        if "balance" in d.columns:
            fig.add_trace(go.Scatter(
                x=d.index, y=d["balance"],
                line=dict(color="#ff6b6b", width=2, dash="dash"), name="잔고(만주)"
            ), row=1, col=1, secondary_y=True)
            # 5MA 잔고
            if "bal_5ma" in d.columns:
                fig.add_trace(go.Scatter(
                    x=d.index, y=d["bal_5ma"],
                    line=dict(color="#ff6b6b", width=1, dash="dot"), name="잔고5MA", opacity=0.6
                ), row=1, col=1, secondary_y=True)

        # 당일 공매도 바
        if "short_vol" in d.columns:
            bar_colors = [
                "#ff4444" if v >= 200 else "#ffd93d" if v >= 100 else "rgba(78,205,196,0.5)"
                for v in d["short_vol"]
            ]
            fig.add_trace(go.Bar(
                x=d.index, y=d["short_vol"],
                marker_color=bar_colors, name="당일공매도", showlegend=False,
            ), row=2, col=1)

        # 거래량
        fig.add_trace(go.Bar(
            x=d.index, y=d["volume"] / 1000,
            marker_color="rgba(68,68,68,0.5)", name="거래량", showlegend=False,
        ), row=3, col=1)

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            font_color="#e6edf3", height=620,
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.02, x=0, font=dict(size=11)),
            margin=dict(l=10, r=60, t=40, b=10),
        )
        fig.update_yaxes(title_text="주가(원)",   tickformat=",",       row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="잔고(만주)", ticksuffix="만", showgrid=False, row=1, col=1, secondary_y=True)
        fig.update_yaxes(ticksuffix="천", row=2, col=1)
        fig.update_xaxes(tickformat="%m/%d", row=3, col=1)
        for i in range(1, 4):
            fig.update_xaxes(gridcolor="#21262d", row=i, col=1)
            fig.update_yaxes(gridcolor="#21262d", row=i, col=1)

        st.plotly_chart(fig, use_container_width=True)

        # 원시 데이터
        with st.expander("📋 원시 데이터 (최근 30일)"):
            show_cols = [c for c in ["close","volume","short_vol","balance","balance_chg","ratio"] if c in d.columns]
            show = d[show_cols].tail(30).copy()
            show.columns = [{"close":"종가","volume":"거래량","short_vol":"당일공매도(천주)",
                             "balance":"잔고(만주)","balance_chg":"잔고변화(만주)","ratio":"잔고비율(%)"}.get(c,c)
                            for c in show_cols]
            show.index = show.index.strftime("%Y-%m-%d")
            st.dataframe(show.sort_index(ascending=False), use_container_width=True)

# ══════════════════════════════════════════
# TAB 3 — 공매도 비교
# ══════════════════════════════════════════
with tab_short:
    st.markdown('<div class="section-header">공매도 잔고 추이 비교</div>', unsafe_allow_html=True)

    # 전종목 잔고 추이 (라인)
    fig_sl = go.Figure()
    for ticker in selected_tickers:
        df = all_data[ticker]
        if df.empty or "balance" not in df.columns:
            continue
        d = slice_days(df, selected_period)
        fig_sl.add_trace(go.Scatter(
            x=d.index, y=d["balance"],
            name=GAME_STOCKS[ticker]["name"], mode="lines", line=dict(width=1.5)
        ))
    fig_sl.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font_color="#e6edf3", height=350,
        xaxis=dict(gridcolor="#21262d"),
        yaxis=dict(gridcolor="#21262d", ticksuffix="만"),
        margin=dict(t=10, b=10),
        legend=dict(orientation="h"),
    )
    st.plotly_chart(fig_sl, use_container_width=True)

    # 최근 잔고비율 & 잔고변화 비교 바
    st.markdown('<div class="section-header">최근 잔고비율 & 전일 변화</div>', unsafe_allow_html=True)
    cmp_rows = []
    for ticker in selected_tickers:
        df = all_data[ticker]
        if df.empty:
            continue
        latest = df.iloc[-1]
        cmp_rows.append({
            "종목명":      GAME_STOCKS[ticker]["name"],
            "잔고비율(%)": float(latest.get("ratio", 0)),
            "잔고변화":    float(latest.get("balance_chg", 0)),
        })

    if cmp_rows:
        cmp_df = pd.DataFrame(cmp_rows)
        fig_cmp = make_subplots(rows=1, cols=2, subplot_titles=("잔고비율(%)", "전일 잔고변화(만주)"))
        fig_cmp.add_trace(go.Bar(
            x=cmp_df["종목명"], y=cmp_df["잔고비율(%)"],
            marker_color=["#f85149" if v > 1.0 else "#e3b341" if v > 0.5 else "#3fb950"
                          for v in cmp_df["잔고비율(%)"]],
            showlegend=False,
        ), row=1, col=1)
        fig_cmp.add_trace(go.Bar(
            x=cmp_df["종목명"], y=cmp_df["잔고변화"],
            marker_color=["#f85149" if v > 0 else "#3fb950" for v in cmp_df["잔고변화"]],
            showlegend=False,
        ), row=1, col=2)
        fig_cmp.update_layout(
            paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
            font_color="#e6edf3", height=320,
            margin=dict(t=30, b=10),
        )
        fig_cmp.update_xaxes(gridcolor="#21262d")
        fig_cmp.update_yaxes(gridcolor="#21262d")
        st.plotly_chart(fig_cmp, use_container_width=True)

# ══════════════════════════════════════════
# TAB 4 — 상대 수익률
# ══════════════════════════════════════════
with tab_compare:
    st.markdown('<div class="section-header">선택 종목 상대 수익률 비교</div>', unsafe_allow_html=True)

    fig_rel = go.Figure()
    for ticker in selected_tickers:
        df = all_data[ticker]
        if df.empty or len(df) < 2:
            continue
        d = slice_days(df, selected_period)
        if len(d) < 2:
            continue
        base = float(d["close"].iloc[0])
        rel  = (d["close"] / base - 1) * 100
        fig_rel.add_trace(go.Scatter(
            x=d.index, y=rel,
            name=GAME_STOCKS[ticker]["name"], mode="lines", line=dict(width=1.5)
        ))

    fig_rel.add_hline(y=0, line_dash="dot", line_color="#30363d")
    fig_rel.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font_color="#e6edf3", height=420,
        xaxis=dict(gridcolor="#21262d"),
        yaxis=dict(gridcolor="#21262d", ticksuffix="%"),
        margin=dict(t=10, b=10),
        legend=dict(orientation="h"),
    )
    st.plotly_chart(fig_rel, use_container_width=True)

    # 기간 수익률 테이블
    st.markdown('<div class="section-header">기간 수익률 요약</div>', unsafe_allow_html=True)
    perf_rows = []
    for ticker in selected_tickers:
        df = all_data[ticker]
        if df.empty:
            continue
        def period_ret(days):
            d = slice_days(df, days)
            if len(d) < 2: return None
            return (float(d["close"].iloc[-1]) / float(d["close"].iloc[0]) - 1) * 100

        perf_rows.append({
            "종목명": GAME_STOCKS[ticker]["name"],
            "1개월(%)": period_ret(30),
            "3개월(%)": period_ret(90),
            "6개월(%)": period_ret(180),
            "1년(%)":   period_ret(365),
        })

    if perf_rows:
        perf_df = pd.DataFrame(perf_rows)

        def color_ret(val):
            if pd.isna(val): return ""
            return f"color:#3fb950;font-weight:600" if val > 0 else f"color:#f85149;font-weight:600"

        styled_perf = (
            perf_df.style
            .applymap(color_ret, subset=["1개월(%)","3개월(%)","6개월(%)","1년(%)"])
            .format({c: lambda x: f"{x:+.1f}%" if pd.notna(x) else "-"
                     for c in ["1개월(%)","3개월(%)","6개월(%)","1년(%)"]})
            .hide(axis="index")
        )
        st.dataframe(styled_perf, use_container_width=True)
