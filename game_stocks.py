"""
game_stocks.py  —  한국 게임주 트래커
흰 배경 / 라이트 테마 / GitHub Raw JSON 읽기
"""

import requests
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ───────────────────────────────────────────
# 상수
# ───────────────────────────────────────────
GITHUB_RAW = "https://raw.githubusercontent.com/{owner}/{repo}/main/data/{ticker}_game.json"

GAME_STOCKS = {
    "259960": {"name": "크래프톤",            "market": "KOSPI",  "mcap_tier": "대형"},
    "263750": {"name": "펄어비스",            "market": "KOSPI",  "mcap_tier": "대형"},
    "036570": {"name": "엔씨소프트",          "market": "KOSPI",  "mcap_tier": "대형"},
    "251270": {"name": "넷마블",              "market": "KOSPI",  "mcap_tier": "대형"},
    "462870": {"name": "시프트업",            "market": "KOSPI",  "mcap_tier": "대형"},
    "293490": {"name": "카카오게임즈",        "market": "KOSDAQ", "mcap_tier": "중형"},
    "095660": {"name": "네오위즈",            "market": "KOSDAQ", "mcap_tier": "중형"},
    "225570": {"name": "넥슨게임즈",          "market": "KOSDAQ", "mcap_tier": "중형"},
    "078340": {"name": "컴투스",              "market": "KOSDAQ", "mcap_tier": "중형"},
    "078630": {"name": "게임빌(컴투스홀딩스)","market": "KOSDAQ", "mcap_tier": "중형"},
    "069080": {"name": "웹젠",               "market": "KOSDAQ", "mcap_tier": "소형"},
    "194480": {"name": "데브시스터즈",        "market": "KOSDAQ", "mcap_tier": "소형"},
    "112040": {"name": "위메이드",            "market": "KOSDAQ", "mcap_tier": "소형"},
    "067000": {"name": "조이시티",            "market": "KOSDAQ", "mcap_tier": "소형"},
    "123420": {"name": "선데이토즈",          "market": "KOSDAQ", "mcap_tier": "소형"},
    "201060": {"name": "미투온",              "market": "KOSDAQ", "mcap_tier": "소형"},
}

# 주요 게임 출시 이벤트
GAME_EVENTS = [
    {"date": "2024-08-29", "ticker": "462870", "label": "시프트업 상장"},
    {"date": "2024-12-05", "ticker": "263750", "label": "크림슨데저트 공개"},
    {"date": "2025-03-20", "ticker": "263750", "label": "크림슨데저트 출시"},
    {"date": "2024-06-26", "ticker": "194480", "label": "쿠키런:모험의탑"},
    {"date": "2024-04-26", "ticker": "462870", "label": "스텔라블레이드 출시"},
]

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
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
    background: #f8f9fc;
    color: #1a1d23;
}
.stApp { background: #f8f9fc; }

/* 사이드바 */
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e2e6ed;
}
[data-testid="stSidebar"] * { color: #1a1d23 !important; }

/* 메트릭 카드 */
.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e6ed;
    border-left: 4px solid #4f7df3;
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,.05);
}
.kpi-label {
    font-size: 11px; font-weight: 600; color: #6b7280;
    text-transform: uppercase; letter-spacing: .07em; margin-bottom: 6px;
}
.kpi-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px; font-weight: 700; color: #1a1d23;
    line-height: 1.2;
}
.kpi-sub { font-size: 12px; margin-top: 4px; color: #6b7280; }

/* 섹션 헤더 */
.section-hdr {
    font-size: 13px; font-weight: 700; color: #4f7df3;
    text-transform: uppercase; letter-spacing: .09em;
    border-bottom: 2px solid #e2e6ed;
    padding-bottom: 7px; margin: 22px 0 14px;
}

/* 배지 */
.badge {
    display: inline-block; padding: 2px 9px; border-radius: 20px;
    font-size: 11px; font-weight: 600;
}
.badge-up   { background:#edfaf2; color:#16a34a; border:1px solid #bbf7d0; }
.badge-down { background:#fff1f2; color:#dc2626; border:1px solid #fecaca; }
.badge-flat { background:#f3f4f6; color:#6b7280; border:1px solid #e5e7eb; }

/* 탭 */
.stTabs [data-baseweb="tab-list"] { background: #ffffff; border-radius: 8px; padding: 4px; border: 1px solid #e2e6ed; }
.stTabs [data-baseweb="tab"] { color: #6b7280 !important; border-radius: 6px; }
.stTabs [aria-selected="true"] { background: #4f7df3 !important; color: #ffffff !important; }

/* 52주 바 */
.bar52-wrap { background:#e5e7eb; border-radius:4px; height:7px; margin-top:5px; }
.bar52-fill { background:#4f7df3; border-radius:4px; height:7px; }

/* 데이터프레임 */
[data-testid="stDataFrame"] { border: 1px solid #e2e6ed; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────
# 헬퍼
# ───────────────────────────────────────────
PLOT_LAYOUT = dict(
    paper_bgcolor="#ffffff", plot_bgcolor="#f8f9fc",
    font=dict(color="#1a1d23", family="Noto Sans KR"),
)
GRID = dict(gridcolor="#e2e6ed", showgrid=True)

def pcolor(v):
    return "#16a34a" if v > 0 else "#dc2626" if v < 0 else "#6b7280"

@st.cache_data(ttl=3600)
def load_ticker(owner, repo, ticker):
    url = GITHUB_RAW.format(owner=owner, repo=repo, ticker=ticker)
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def build_df(meta):
    df = pd.DataFrame(meta["records"])
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()

def get_df(owner, repo, ticker):
    meta = load_ticker(owner, repo, ticker)
    if "error" in meta or not meta.get("records"):
        return pd.DataFrame()
    return build_df(meta)

@st.cache_data(ttl=3600)
def load_index(owner, repo, name):
    """KOSPI/KOSDAQ 지수 JSON 로드 — data/index_kospi.json 등"""
    url = GITHUB_RAW.format(owner=owner, repo=repo, ticker=f"index_{name.lower()}")
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        meta = r.json()
        df = pd.DataFrame(meta["records"])
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date").sort_index()
    except Exception:
        return pd.DataFrame()

def slice_days(df, days):
    if df.empty: return df
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df[df.index >= cutoff]

def period_ret(df, days):
    d = slice_days(df, days)
    if len(d) < 2: return None
    return (float(d["close"].iloc[-1]) / float(d["close"].iloc[0]) - 1) * 100

# ───────────────────────────────────────────
# 사이드바
# ───────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎮 게임주 트래커")
    st.caption("한국 상장 게임주 종합 분석")
    st.divider()

    owner = st.text_input("GitHub 사용자명", value="gonmau")
    repo  = st.text_input("레포지터리명",    value="stock-tracking")
    st.divider()

    tier_filter = st.multiselect("규모 필터", ["대형", "중형", "소형"],
                                  default=["대형", "중형", "소형"])
    filtered_tickers = [t for t, v in GAME_STOCKS.items() if v["mcap_tier"] in tier_filter]

    selected_tickers = st.multiselect(
        "종목 선택",
        options=filtered_tickers,
        default=filtered_tickers[:8],
        format_func=lambda x: f"{GAME_STOCKS[x]['name']} ({x})",
    )

    period_map = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
    selected_period_label = st.selectbox("조회 기간", list(period_map.keys()), index=1)
    selected_period = period_map[selected_period_label]

    show_events = st.toggle("📌 게임 출시 이벤트 표시", value=True)
    chart_type  = st.radio("차트 유형", ["라인", "캔들스틱"], horizontal=True)
    st.divider()

    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"업데이트: {datetime.now().strftime('%H:%M:%S')}")

# ───────────────────────────────────────────
# 헤더
# ───────────────────────────────────────────
c_title, c_date = st.columns([3, 1])
with c_title:
    st.markdown("## 🎮 한국 게임주 트래커")
with c_date:
    st.markdown(
        f"<div style='text-align:right;padding-top:14px;color:#6b7280;font-size:13px'>"
        f"{datetime.today().strftime('%Y.%m.%d')} · KRX (T+2)</div>",
        unsafe_allow_html=True
    )

if not selected_tickers:
    st.info("사이드바에서 종목을 선택해주세요.")
    st.stop()

# ───────────────────────────────────────────
# 데이터 로드
# ───────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_all(owner, repo, tickers):
    return {t: get_df(owner, repo, t) for t in tickers}

with st.spinner("데이터 불러오는 중..."):
    all_data = load_all(owner, repo, tuple(selected_tickers))

loaded = [t for t, df in all_data.items() if not df.empty]
if not loaded:
    st.error("데이터 없음 — Actions가 아직 실행되지 않았거나 레포/경로를 확인하세요.")
    st.stop()

# ───────────────────────────────────────────
# 요약 테이블 계산
# ───────────────────────────────────────────
def build_summary():
    rows = []
    for t in selected_tickers:
        df = all_data[t]
        if df.empty: continue
        latest = df.iloc[-1]
        prev   = df.iloc[-2] if len(df) > 1 else latest
        close  = float(latest["close"])
        chg    = (close - float(prev["close"])) / float(prev["close"]) * 100 if float(prev["close"]) else 0
        hi52   = float(df["close"].tail(252).max())
        lo52   = float(df["close"].tail(252).min())
        pos52  = (close - lo52) / (hi52 - lo52) * 100 if hi52 != lo52 else 50
        rows.append({
            "ticker":   t,
            "종목명":   GAME_STOCKS[t]["name"],
            "시장":     GAME_STOCKS[t]["market"],
            "현재가":   close,
            "등락(%)":  round(chg, 2),
            "거래량":   int(latest["volume"]),
            "공매도잔고(만)": float(latest.get("balance", 0)),
            "잔고변화":      float(latest.get("balance_chg", 0)),
            "잔고비율(%)":   float(latest.get("ratio", 0)),
            "52주고":   hi52,
            "52주저":   lo52,
            "52주위치": round(pos52, 1),
            "1M(%)":    period_ret(df, 30),
            "3M(%)":    period_ret(df, 90),
            "1Y(%)":    period_ret(df, 365),
        })
    return pd.DataFrame(rows)

summary = build_summary()

# ───────────────────────────────────────────
# 상단 KPI 바 (전종목 집계)
# ───────────────────────────────────────────
ups   = (summary["등락(%)"] > 0).sum()
downs = (summary["등락(%)"] < 0).sum()
flat  = len(summary) - ups - downs
avg_chg  = summary["등락(%)"].mean()
avg_bal  = summary["잔고비율(%)"].mean()
top_gainer = summary.loc[summary["등락(%)"].idxmax(), "종목명"] if not summary.empty else "-"
top_loser  = summary.loc[summary["등락(%)"].idxmin(), "종목명"] if not summary.empty else "-"
top_short  = summary.loc[summary["잔고비율(%)"].idxmax(), "종목명"] if not summary.empty else "-"

k1, k2, k3, k4, k5 = st.columns(5)
kpis = [
    (k1, "상승 / 보합 / 하락", f"{ups} · {flat} · {downs}", None),
    (k2, "평균 등락률", f"{avg_chg:+.2f}%", pcolor(avg_chg)),
    (k3, "최고 상승", top_gainer, "#16a34a"),
    (k4, "최고 하락", top_loser,  "#dc2626"),
    (k5, "공매도 1위", top_short, "#f59e0b"),
]
for col, label, val, color in kpis:
    c = color or "#1a1d23"
    col.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color:{c};font-size:18px">{val}</div>
    </div>""", unsafe_allow_html=True)

st.divider()

# ───────────────────────────────────────────
# 탭
# ───────────────────────────────────────────
tab_ov, tab_chart, tab_short, tab_compare, tab_event = st.tabs([
    "📊 종목 요약", "📈 주가 & 공매도", "🔻 공매도 분석", "📐 수익률 비교", "🎮 이벤트"
])

# ══════════════════════════════════════════
# TAB 1 — 종목 요약
# ══════════════════════════════════════════
with tab_ov:
    # 52주 위치 포함 테이블
    st.markdown('<div class="section-hdr">종목별 현황</div>', unsafe_allow_html=True)

    def fmt_chg(v):
        if pd.isna(v): return "-"
        badge = "up" if v > 0 else "down" if v < 0 else "flat"
        return f'<span class="badge badge-{badge}">{v:+.2f}%</span>'

    def fmt_52(row):
        pos = row["52주위치"]
        hi, lo, cl = row["52주고"], row["52주저"], row["현재가"]
        return (f"<div style='font-size:11px;color:#6b7280'>{lo:,.0f} ─ {hi:,.0f}</div>"
                f"<div class='bar52-wrap'><div class='bar52-fill' style='width:{pos:.0f}%'></div></div>"
                f"<div style='font-size:11px;text-align:right;color:#4f7df3'>{pos:.0f}%</div>")

    # 컬러 포맷된 데이터프레임
    disp = summary[["종목명","시장","현재가","등락(%)","거래량",
                     "공매도잔고(만)","잔고변화","잔고비율(%)",
                     "1M(%)","3M(%)","1Y(%)","52주위치"]].copy()

    def color_v(val):
        if pd.isna(val): return ""
        return f"color:{pcolor(val)};font-weight:600"

    styled = (
        disp.style
        .applymap(color_v, subset=["등락(%)","잔고변화","1M(%)","3M(%)","1Y(%)"])
        .applymap(lambda v: f"color:{'#dc2626' if v>1.0 else '#f59e0b' if v>0.5 else '#16a34a'};font-weight:600",
                  subset=["잔고비율(%)"])
        .format({
            "현재가":         "{:,.0f}",
            "등락(%)":        "{:+.2f}%",
            "거래량":         "{:,.0f}",
            "공매도잔고(만)":  "{:.1f}",
            "잔고변화":       "{:+.2f}",
            "잔고비율(%)":    "{:.3f}%",
            "1M(%)":  lambda x: f"{x:+.1f}%" if pd.notna(x) else "-",
            "3M(%)":  lambda x: f"{x:+.1f}%" if pd.notna(x) else "-",
            "1Y(%)":  lambda x: f"{x:+.1f}%" if pd.notna(x) else "-",
            "52주위치": "{:.0f}%",
        })
        .hide(axis="index")
        .set_properties(**{"background-color": "#ffffff", "color": "#1a1d23", "font-size": "13px"})
        .set_table_styles([
            {"selector": "th", "props": [("background","#f3f4f6"),("color","#374151"),
                                          ("font-size","12px"),("font-weight","700"),
                                          ("padding","8px 12px"),("border-bottom","2px solid #e2e6ed")]},
            {"selector": "td", "props": [("padding","8px 12px"),("border-bottom","1px solid #f3f4f6")]},
        ])
    )
    st.dataframe(styled, use_container_width=True, height=500)

    # 등락률 + 잔고비율 듀얼 바
    st.markdown('<div class="section-hdr">등락률 & 공매도 잔고비율</div>', unsafe_allow_html=True)
    fig_dual = make_subplots(rows=1, cols=2,
        subplot_titles=("등락률 (%)", "공매도 잔고비율 (%)"),
        horizontal_spacing=0.08)

    fig_dual.add_trace(go.Bar(
        x=summary["종목명"], y=summary["등락(%)"],
        marker_color=[pcolor(v) for v in summary["등락(%)"]],
        text=[f"{v:+.2f}%" for v in summary["등락(%)"]],
        textposition="outside", showlegend=False,
    ), row=1, col=1)

    fig_dual.add_trace(go.Bar(
        x=summary["종목명"], y=summary["잔고비율(%)"],
        marker_color=["#dc2626" if v>1.0 else "#f59e0b" if v>0.5 else "#16a34a"
                      for v in summary["잔고비율(%)"]],
        text=[f"{v:.3f}%" for v in summary["잔고비율(%)"]],
        textposition="outside", showlegend=False,
    ), row=1, col=2)

    fig_dual.update_layout(**PLOT_LAYOUT, height=320, margin=dict(t=30,b=10,l=10,r=10))
    fig_dual.update_xaxes(**GRID)
    fig_dual.update_yaxes(**GRID)
    st.plotly_chart(fig_dual, use_container_width=True)

    # 52주 위치 게이지 바
    st.markdown('<div class="section-hdr">52주 가격 위치</div>', unsafe_allow_html=True)
    fig_52 = go.Figure()
    for _, row in summary.sort_values("52주위치", ascending=True).iterrows():
        pos = row["52주위치"]
        fig_52.add_trace(go.Bar(
            x=[pos], y=[row["종목명"]], orientation="h",
            marker_color="#4f7df3", showlegend=False,
            text=f"{pos:.0f}%  ({row['현재가']:,.0f}원)",
            textposition="inside" if pos > 20 else "outside",
            textfont=dict(color="#ffffff" if pos > 20 else "#1a1d23", size=11),
        ))
    fig_52.update_layout(
        **PLOT_LAYOUT,
        height=max(280, len(summary)*32+60),
        margin=dict(t=30, b=10, l=10, r=10),
        xaxis=dict(range=[0,100], ticksuffix="%", gridcolor="#e2e6ed", showgrid=True),
        yaxis=dict(gridcolor="#e2e6ed", showgrid=True),
    )
    st.plotly_chart(fig_52, use_container_width=True)

# ══════════════════════════════════════════
# TAB 2 — 주가 & 공매도
# ══════════════════════════════════════════
with tab_chart:
    chart_ticker = st.selectbox(
        "종목",
        options=selected_tickers,
        format_func=lambda x: f"{GAME_STOCKS[x]['name']} ({x})",
        key="chart_sel"
    )
    df = all_data[chart_ticker]

    if df.empty:
        st.warning("데이터 없음")
    else:
        meta  = load_ticker(owner, repo, chart_ticker)
        name  = GAME_STOCKS[chart_ticker]["name"]
        d     = slice_days(df, selected_period)
        lat   = d.iloc[-1]
        prv   = d.iloc[-2] if len(d)>1 else lat

        close   = int(lat["close"])
        chg_pct = (lat["close"]-prv["close"])/prv["close"]*100
        bal     = float(lat.get("balance",0))
        bal_chg = float(lat.get("balance_chg",0))
        sv      = float(lat.get("short_vol",0))
        ratio   = float(lat.get("ratio",0))

        # KPI 행
        k1,k2,k3,k4 = st.columns(4)
        for col, lbl, val, sub, acc in [
            (k1, "현재가",     f"{close:,}원",    f"{chg_pct:+.2f}%", "#4f7df3"),
            (k2, "공매도 잔고", f"{bal:.1f}만주",  f"전일比 {bal_chg:+.2f}만",
             "#dc2626" if bal_chg>0 else "#16a34a"),
            (k3, "당일 공매도", f"{sv:.0f}천주",   "기준: 200천주=위험", "#f59e0b"),
            (k4, "잔고 비율",  f"{ratio:.3f}%",   "발행주식 대비",       "#6b7280"),
        ]:
            col.markdown(f"""<div class="kpi-card" style="border-left-color:{acc}">
                <div class="kpi-label">{lbl}</div>
                <div class="kpi-value" style="color:{acc}">{val}</div>
                <div class="kpi-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

        # 차트
        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True,
            row_heights=[0.55, 0.22, 0.23],
            vertical_spacing=0.03,
            subplot_titles=(f"{name} 주가 & 공매도 잔고", "당일 공매도 (천주)", "거래량 (천주)"),
            specs=[[{"secondary_y":True}],[{"secondary_y":False}],[{"secondary_y":False}]],
        )

        if chart_type == "캔들스틱" and "open" in d.columns:
            fig.add_trace(go.Candlestick(
                x=d.index, open=d["open"], high=d["high"], low=d["low"], close=d["close"],
                increasing_line_color="#16a34a", decreasing_line_color="#dc2626",
                name="주가",
            ), row=1, col=1, secondary_y=False)
        else:
            fig.add_trace(go.Scatter(
                x=d.index, y=d["close"],
                line=dict(color="#4f7df3", width=2.5), name="주가", fill="tozeroy",
                fillcolor="rgba(79,125,243,0.06)",
            ), row=1, col=1, secondary_y=False)

        for ma_col, color, lbl in [("price_5ma","#f59e0b","5MA"),("price_20ma","#ef4444","20MA")]:
            if ma_col in d.columns:
                fig.add_trace(go.Scatter(
                    x=d.index, y=d[ma_col],
                    line=dict(color=color, width=1.2, dash="dot"), name=lbl,
                ), row=1, col=1, secondary_y=False)

        if "balance" in d.columns:
            fig.add_trace(go.Scatter(
                x=d.index, y=d["balance"],
                line=dict(color="#dc2626", width=2, dash="dash"), name="잔고(만주)",
            ), row=1, col=1, secondary_y=True)
            if "bal_5ma" in d.columns:
                fig.add_trace(go.Scatter(
                    x=d.index, y=d["bal_5ma"],
                    line=dict(color="#f87171", width=1, dash="dot"), name="잔고5MA", opacity=0.7,
                ), row=1, col=1, secondary_y=True)

        # 게임 이벤트 수직선
        if show_events:
            ticker_events = [e for e in GAME_EVENTS if e["ticker"] == chart_ticker]
            for ev in ticker_events:
                ev_dt = pd.Timestamp(ev["date"])
                if d.index.min() <= ev_dt <= d.index.max():
                    for row_n in [1, 2, 3]:
                        fig.add_vline(
                            x=ev_dt, line_width=1.5, line_dash="dot",
                            line_color="#7c3aed", row=row_n, col=1,
                        )
                    fig.add_annotation(
                        x=ev_dt, y=1, yref="paper", xref="x",
                        text=f"📌 {ev['label']}", showarrow=False,
                        font=dict(size=10, color="#7c3aed"),
                        bgcolor="rgba(255,255,255,0.85)",
                        bordercolor="#7c3aed", borderwidth=1,
                        yanchor="top",
                    )

        # 거래량 (이상 거래량 하이라이트)
        vol_avg = d["volume"].rolling(20).mean()
        vol_colors = [
            "#ef4444" if v > avg*2 else "#4f7df3"
            for v, avg in zip(d["volume"], vol_avg.fillna(d["volume"]))
        ]
        fig.add_trace(go.Bar(
            x=d.index, y=d["volume"]/1000,
            marker_color=vol_colors, name="거래량", showlegend=False,
        ), row=3, col=1)

        if "short_vol" in d.columns:
            sv_colors = [
                "#dc2626" if v>=200 else "#f59e0b" if v>=100 else "#86efac"
                for v in d["short_vol"]
            ]
            fig.add_trace(go.Bar(
                x=d.index, y=d["short_vol"],
                marker_color=sv_colors, name="당일공매도", showlegend=False,
            ), row=2, col=1)

        fig.update_layout(
            **PLOT_LAYOUT, height=650,
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.03, x=0, font=dict(size=11)),
            margin=dict(l=10, r=60, t=45, b=10),
        )
        for i in range(1,4):
            fig.update_xaxes(gridcolor="#e2e6ed", row=i, col=1)
            fig.update_yaxes(gridcolor="#e2e6ed", row=i, col=1)
        fig.update_yaxes(title_text="주가(원)", tickformat=",", row=1, col=1, secondary_y=False)
        fig.update_yaxes(title_text="잔고(만주)", showgrid=False, row=1, col=1, secondary_y=True)
        fig.update_xaxes(tickformat="%m/%d", row=3, col=1)

        st.plotly_chart(fig, use_container_width=True,
                        config={"toImageButtonOptions":{"width":1600,"height":900,"scale":2}})

        st.caption("🔴 거래량 빨간 막대 = 20일 평균 2배 이상 이상거래량 / 📌 보라 점선 = 게임 이벤트")

        with st.expander("📋 원시 데이터 (최근 30일)"):
            cols_show = [c for c in ["close","volume","short_vol","balance","balance_chg","ratio"] if c in d.columns]
            show = d[cols_show].tail(30).rename(columns={
                "close":"종가","volume":"거래량","short_vol":"당일공매도(천주)",
                "balance":"잔고(만주)","balance_chg":"잔고변화(만주)","ratio":"잔고비율(%)"})
            show.index = show.index.strftime("%Y-%m-%d")
            st.dataframe(show.sort_index(ascending=False), use_container_width=True)

# ══════════════════════════════════════════
# TAB 3 — 공매도 분석
# ══════════════════════════════════════════
with tab_short:
    st.markdown('<div class="section-hdr">공매도 잔고 추이 (전종목)</div>', unsafe_allow_html=True)

    fig_sl = go.Figure()
    for t in selected_tickers:
        df = all_data[t]
        if df.empty or "balance" not in df.columns: continue
        d = slice_days(df, selected_period)
        fig_sl.add_trace(go.Scatter(
            x=d.index, y=d["balance"],
            name=GAME_STOCKS[t]["name"], mode="lines", line=dict(width=1.8),
        ))
    fig_sl.update_layout(**PLOT_LAYOUT, height=350, margin=dict(t=30,b=10,l=10,r=10),
                          xaxis=dict(gridcolor="#e2e6ed"),
                          yaxis=dict(gridcolor="#e2e6ed", ticksuffix="만"),
                          legend=dict(orientation="h"))
    st.plotly_chart(fig_sl, use_container_width=True)

    # 잔고비율 & 전일변화 비교
    st.markdown('<div class="section-hdr">잔고비율 & 전일 변화 비교</div>', unsafe_allow_html=True)
    cmp_rows = []
    for t in selected_tickers:
        df = all_data[t]
        if df.empty: continue
        lat = df.iloc[-1]
        cmp_rows.append({
            "종목명":      GAME_STOCKS[t]["name"],
            "잔고비율(%)": float(lat.get("ratio",0)),
            "잔고변화(만)": float(lat.get("balance_chg",0)),
            "당일공매도":   float(lat.get("short_vol",0)),
        })
    if cmp_rows:
        cmp_df = pd.DataFrame(cmp_rows).sort_values("잔고비율(%)", ascending=False)
        fig_cmp = make_subplots(rows=1, cols=2,
            subplot_titles=("잔고비율 (%) — 높을수록 위험", "전일 잔고 변화 (만주)"),
            horizontal_spacing=0.1)
        fig_cmp.add_trace(go.Bar(
            x=cmp_df["종목명"], y=cmp_df["잔고비율(%)"],
            marker_color=["#dc2626" if v>1.0 else "#f59e0b" if v>0.5 else "#16a34a"
                          for v in cmp_df["잔고비율(%)"]],
            text=[f"{v:.3f}%" for v in cmp_df["잔고비율(%)"]],
            textposition="outside", showlegend=False,
        ), row=1, col=1)
        fig_cmp.add_trace(go.Bar(
            x=cmp_df["종목명"], y=cmp_df["잔고변화(만)"],
            marker_color=["#dc2626" if v>0 else "#16a34a" for v in cmp_df["잔고변화(만)"]],
            text=[f"{v:+.2f}" for v in cmp_df["잔고변화(만)"]],
            textposition="outside", showlegend=False,
        ), row=1, col=2)
        fig_cmp.update_layout(**PLOT_LAYOUT, height=340, margin=dict(t=30,b=10,l=10,r=10))
        fig_cmp.update_xaxes(gridcolor="#e2e6ed")
        fig_cmp.update_yaxes(gridcolor="#e2e6ed")
        st.plotly_chart(fig_cmp, use_container_width=True)

        # 공매도 위험도 테이블
        st.markdown('<div class="section-hdr">공매도 위험도 요약</div>', unsafe_allow_html=True)
        cmp_df["위험도"] = cmp_df["잔고비율(%)"].apply(
            lambda v: "🔴 위험" if v>1.0 else "🟡 주의" if v>0.5 else "🟢 안전"
        )
        cmp_df["방향"] = cmp_df["잔고변화(만)"].apply(
            lambda v: "▲ 증가" if v>0.5 else "▼ 감소" if v<-0.5 else "→ 보합"
        )
        st.dataframe(
            cmp_df[["종목명","잔고비율(%)","잔고변화(만)","당일공매도","위험도","방향"]]
            .reset_index(drop=True),
            use_container_width=True,
        )

# ══════════════════════════════════════════
# TAB 4 — 수익률 비교
# ══════════════════════════════════════════
with tab_compare:
    st.markdown('<div class="section-hdr">선택 기간 상대 수익률 (vs KOSPI/KOSDAQ)</div>', unsafe_allow_html=True)

    # 지수 로드
    idx_kospi  = load_index(owner, repo, "KOSPI")
    idx_kosdaq = load_index(owner, repo, "KOSDAQ")

    fig_rel = go.Figure()

    # KOSPI / KOSDAQ 기준선 (굵은 점선)
    for idx_df, idx_name, idx_color in [
        (idx_kospi,  "KOSPI",  "#6b7280"),
        (idx_kosdaq, "KOSDAQ", "#9ca3af"),
    ]:
        if idx_df.empty: continue
        d_idx = slice_days(idx_df, selected_period)
        if len(d_idx) < 2: continue
        base_idx = float(d_idx["close"].iloc[0])
        rel_idx  = (d_idx["close"] / base_idx - 1) * 100
        fig_rel.add_trace(go.Scatter(
            x=d_idx.index, y=rel_idx,
            name=idx_name, mode="lines",
            line=dict(color=idx_color, width=2, dash="dash"),
        ))

    # 종목별 수익률
    for t in selected_tickers:
        df = all_data[t]
        if df.empty or len(df)<2: continue
        d = slice_days(df, selected_period)
        if len(d)<2: continue
        base = float(d["close"].iloc[0])
        rel  = (d["close"]/base - 1)*100
        fig_rel.add_trace(go.Scatter(
            x=d.index, y=rel,
            name=GAME_STOCKS[t]["name"], mode="lines", line=dict(width=1.8),
        ))

    fig_rel.add_hline(y=0, line_dash="dot", line_color="#9ca3af", line_width=1)
    fig_rel.update_layout(**PLOT_LAYOUT, height=460, margin=dict(t=30,b=10,l=10,r=10),
                           xaxis=dict(gridcolor="#e2e6ed"),
                           yaxis=dict(gridcolor="#e2e6ed", ticksuffix="%"),
                           legend=dict(orientation="h"))
    st.plotly_chart(fig_rel, use_container_width=True)

    # 지수 대비 초과수익률 테이블
    if not idx_kospi.empty:
        st.markdown('<div class="section-hdr">지수 대비 초과수익률 (KOSPI 기준)</div>', unsafe_allow_html=True)
        def excess_ret(df, days):
            ret = period_ret(df, days)
            idx_d = slice_days(idx_kospi, days)
            if ret is None or len(idx_d) < 2: return None
            idx_ret = (float(idx_d["close"].iloc[-1]) / float(idx_d["close"].iloc[0]) - 1) * 100
            return ret - idx_ret

        exc_rows = []
        for t in selected_tickers:
            df = all_data[t]
            if df.empty: continue
            exc_rows.append({
                "종목명":    GAME_STOCKS[t]["name"],
                "1M 초과(%)":  excess_ret(df, 30),
                "3M 초과(%)":  excess_ret(df, 90),
                "6M 초과(%)":  excess_ret(df, 180),
                "1Y 초과(%)":  excess_ret(df, 365),
            })
        if exc_rows:
            exc_df = pd.DataFrame(exc_rows)
            exc_cols = ["1M 초과(%)","3M 초과(%)","6M 초과(%)","1Y 초과(%)"]
            styled_exc = (
                exc_df.style
                .applymap(lambda v: color_v(v) if pd.notna(v) else "", subset=exc_cols)
                .format({c: lambda x: f"{x:+.1f}%" if pd.notna(x) else "-" for c in exc_cols})
                .hide(axis="index")
                .set_properties(**{"background-color":"#ffffff","font-size":"13px"})
                .set_table_styles([
                    {"selector":"th","props":[("background","#f3f4f6"),("font-weight","700"),("padding","8px 12px")]},
                    {"selector":"td","props":[("padding","8px 12px"),("border-bottom","1px solid #f3f4f6")]},
                ])
            )
            st.dataframe(styled_exc, use_container_width=True)

    # 기간별 수익률 히트맵
    st.markdown('<div class="section-hdr">기간별 수익률 히트맵</div>', unsafe_allow_html=True)
    heat_rows, heat_names = [], []
    for t in selected_tickers:
        df = all_data[t]
        if df.empty: continue
        heat_names.append(GAME_STOCKS[t]["name"])
        heat_rows.append([
            period_ret(df, 5),
            period_ret(df, 20),
            period_ret(df, 60),
            period_ret(df, 120),
            period_ret(df, 250),
        ])
    if heat_rows:
        z = [[v if v is not None else 0 for v in row] for row in heat_rows]
        text = [[f"{v:+.1f}%" if v is not None else "-" for v in row] for row in heat_rows]
        fig_hm = go.Figure(go.Heatmap(
            z=z, x=["1주","1개월","3개월","6개월","1년"],
            y=heat_names, colorscale="RdYlGn",
            text=text, texttemplate="%{text}",
            zmid=0, colorbar=dict(title="%"),
        ))
        fig_hm.update_layout(**PLOT_LAYOUT, height=max(280, len(heat_names)*36+80), margin=dict(t=30,b=10,l=10,r=10))
        st.plotly_chart(fig_hm, use_container_width=True)

    # 기간 수익률 테이블
    st.markdown('<div class="section-hdr">수익률 상세</div>', unsafe_allow_html=True)
    perf_rows = []
    for t in selected_tickers:
        df = all_data[t]
        if df.empty: continue
        perf_rows.append({
            "종목명":  GAME_STOCKS[t]["name"],
            "1주(%)":  period_ret(df, 5),
            "1M(%)":   period_ret(df, 30),
            "3M(%)":   period_ret(df, 90),
            "6M(%)":   period_ret(df, 180),
            "1Y(%)":   period_ret(df, 365),
        })
    if perf_rows:
        perf_df = pd.DataFrame(perf_rows)
        ret_cols = ["1주(%)","1M(%)","3M(%)","6M(%)","1Y(%)"]
        styled_p = (
            perf_df.style
            .applymap(lambda v: color_v(v) if pd.notna(v) else "", subset=ret_cols)
            .format({c: lambda x: f"{x:+.1f}%" if pd.notna(x) else "-" for c in ret_cols})
            .hide(axis="index")
            .set_properties(**{"background-color":"#ffffff","color":"#1a1d23","font-size":"13px"})
            .set_table_styles([
                {"selector":"th","props":[("background","#f3f4f6"),("color","#374151"),
                                           ("font-weight","700"),("padding","8px 12px")]},
                {"selector":"td","props":[("padding","8px 12px"),("border-bottom","1px solid #f3f4f6")]},
            ])
        )
        st.dataframe(styled_p, use_container_width=True)

# ══════════════════════════════════════════
# TAB 5 — 게임 이벤트
# ══════════════════════════════════════════
with tab_event:
    st.markdown('<div class="section-hdr">주요 게임 이벤트 & 주가 반응</div>', unsafe_allow_html=True)

    ev_ticker = st.selectbox(
        "종목",
        options=[t for t in selected_tickers
                 if any(e["ticker"]==t for e in GAME_EVENTS)],
        format_func=lambda x: f"{GAME_STOCKS[x]['name']} ({x})",
        key="ev_sel"
    ) if any(e["ticker"] in selected_tickers for e in GAME_EVENTS) else None

    if ev_ticker:
        df = all_data[ev_ticker]
        if not df.empty:
            d = slice_days(df, 365)
            fig_ev = go.Figure()
            fig_ev.add_trace(go.Scatter(
                x=d.index, y=d["close"],
                line=dict(color="#4f7df3", width=2), name="주가", fill="tozeroy",
                fillcolor="rgba(79,125,243,0.06)",
            ))
            ticker_events = [e for e in GAME_EVENTS if e["ticker"]==ev_ticker]
            for ev in ticker_events:
                ev_dt = pd.Timestamp(ev["date"])
                if d.index.min() <= ev_dt <= d.index.max():
                    fig_ev.add_vline(
                        x=ev_dt, line_width=2, line_dash="dash", line_color="#7c3aed",
                    )
                    ev_price = float(df.loc[df.index>=ev_dt, "close"].iloc[0]) if any(df.index>=ev_dt) else None
                    fig_ev.add_annotation(
                        x=ev_dt, y=ev_price or d["close"].mean(),
                        text=f"📌 {ev['label']}", showarrow=True,
                        arrowhead=2, arrowcolor="#7c3aed",
                        font=dict(size=11, color="#7c3aed"),
                        bgcolor="rgba(255,255,255,0.9)",
                        bordercolor="#7c3aed", borderwidth=1,
                        ay=-40,
                    )
            fig_ev.update_layout(**PLOT_LAYOUT, height=400, margin=dict(t=30,b=10,l=10,r=10),
                                  xaxis=dict(gridcolor="#e2e6ed"),
                                  yaxis=dict(gridcolor="#e2e6ed", tickformat=",", title="주가(원)"))
            st.plotly_chart(fig_ev, use_container_width=True)

            # 이벤트 전후 수익률 계산
            st.markdown('<div class="section-hdr">이벤트 전후 수익률</div>', unsafe_allow_html=True)
            ev_rows = []
            for ev in ticker_events:
                ev_dt = pd.Timestamp(ev["date"])
                before = df[df.index < ev_dt]
                after  = df[df.index >= ev_dt]
                if before.empty or after.empty: continue
                p0 = float(before.iloc[-1]["close"])
                def ret_after(days):
                    tgt = after[after.index <= ev_dt + pd.Timedelta(days=days)]
                    return (float(tgt.iloc[-1]["close"])/p0-1)*100 if not tgt.empty else None
                ev_rows.append({
                    "이벤트":   ev["label"],
                    "날짜":     ev["date"],
                    "이벤트 당일가": f"{float(after.iloc[0]['close']):,.0f}원",
                    "+1주(%)":  ret_after(7),
                    "+1개월(%)": ret_after(30),
                    "+3개월(%)": ret_after(90),
                })
            if ev_rows:
                ev_df = pd.DataFrame(ev_rows)
                ret_cols_ev = ["+1주(%)","+1개월(%)","+3개월(%)"]
                styled_ev = (
                    ev_df.style
                    .applymap(lambda v: color_v(v) if pd.notna(v) else "", subset=ret_cols_ev)
                    .format({c: lambda x: f"{x:+.1f}%" if pd.notna(x) else "-" for c in ret_cols_ev})
                    .hide(axis="index")
                )
                st.dataframe(styled_ev, use_container_width=True)
    else:
        st.info("선택된 종목 중 등록된 이벤트가 없습니다. 사이드바에서 펄어비스, 시프트업, 데브시스터즈를 추가해보세요.")

    st.markdown('<div class="section-hdr">전체 이벤트 목록</div>', unsafe_allow_html=True)
    ev_list = pd.DataFrame(GAME_EVENTS)
    ev_list["종목명"] = ev_list["ticker"].map(lambda t: GAME_STOCKS.get(t,{}).get("name",t))
    st.dataframe(ev_list[["date","종목명","label"]].rename(
        columns={"date":"날짜","label":"이벤트"}), use_container_width=True)
