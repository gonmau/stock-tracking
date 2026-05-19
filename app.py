"""
app.py  —  펄어비스 공매도 추적 대시보드
Streamlit Cloud에서 실행
data/263750.json을 GitHub에서 직접 읽음
"""

import json
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────────
GITHUB_RAW = (
    "https://raw.githubusercontent.com/"
    "{owner}/{repo}/main/data/263750.json"
)
TOTAL_SHARES = 64_250_000

THRESHOLDS = {
    "danger":  200,
    "warning": 150,
    "neutral": 100,
    "squeeze":  80,
    "daily_attack": 200,
    "daily_watch":  100,
}

st.set_page_config(
    page_title="펄어비스 공매도 트래커",
    page_icon="📉",
    layout="wide",
)

st.markdown("""
<style>
.metric-card {
    background: #1a1a2e;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 8px;
}
.metric-label { font-size: 12px; color: #888; margin-bottom: 4px; }
.metric-value { font-size: 24px; font-weight: 600; }
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: .5px;
}
.badge-red    { background:#3d1515; color:#ff6b6b; border:1px solid #ff6b6b44; }
.badge-yellow { background:#2d2500; color:#ffd93d; border:1px solid #ffd93d44; }
.badge-cyan   { background:#00282d; color:#4ecdc4; border:1px solid #4ecdc444; }
.badge-green  { background:#0d2b1a; color:#6bcf7f; border:1px solid #6bcf7f44; }
.signal-row {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 0; border-bottom: 1px solid #222;
    font-size: 14px;
}
.signal-row:last-child { border-bottom: none; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_data(owner: str, repo: str):
    url = GITHUB_RAW.format(owner=owner, repo=repo)
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(ttl=60)
def get_realtime_price():
    try:
        url = "https://m.stock.naver.com/api/stock/263750/basic"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        data = r.json()
        return int(data["closePrice"].replace(",", ""))
    except:
        pass
    return None

def build_df(meta: dict) -> pd.DataFrame:
    df = pd.DataFrame(meta["records"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df


def analyze(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest
    T      = THRESHOLDS

    bal = latest["balance"]
    chg = latest["balance_chg"]
    sv  = latest["short_vol"]
    cl  = latest["close"]

    if bal >= T["danger"]:
        risk = ("DANGER", "red", "공매도 공세 지속 — 신규 매수 자제")
    elif bal >= T["warning"]:
        risk = ("WARNING", "yellow", "주의 구간 — 잔고 감소 확인 후 진입")
    elif bal <= T["squeeze"]:
        risk = ("SQUEEZE", "green", "숏스퀴즈 구간 — 반등 가능성 ↑")
    else:
        risk = ("NEUTRAL", "cyan", "중립 — 펀더멘털 기반 접근 가능")

    if sv >= T["daily_attack"]:
        daily = ("ATTACK 🔴", "red", f"{sv:.0f}천주 — 공격적 공매도")
    elif sv >= T["daily_watch"]:
        daily = ("WATCH 🟡", "yellow", f"{sv:.0f}천주 — 증가 주의")
    else:
        daily = ("CALM 🟢", "green", f"{sv:.0f}천주 — 정상")

    if chg >= 20:
        direction = ("구축 중 ▲", "red")
    elif chg >= 5:
        direction = ("증가 ↑", "yellow")
    elif chg <= -20:
        direction = ("청산 중 ▼", "green")
    elif chg <= -5:
        direction = ("감소 ↓", "cyan")
    else:
        direction = ("보합 →", "white")

    signals = []
    peak = df["balance"].rolling(10).max().iloc[-1]
    if bal < peak * 0.85:
        signals.append(f"잔고 10일 최고({peak:.1f}만) 대비 {(1-bal/peak)*100:.0f}% 감소 — 상환 진행 중")
    price_chg_pct = (cl - prev["close"]) / prev["close"] * 100
    if chg < -5 and price_chg_pct > 1:
        signals.append(f"잔고 감소 + 주가 +{price_chg_pct:.1f}% — 숏커버 반등 신호")
    p5   = latest["price_5ma"]
    p20  = latest["price_20ma"]
    pp5  = prev["price_5ma"]
    pp20 = prev["price_20ma"]
    if p5 > p20 and pp5 <= pp20:
        signals.append("5MA > 20MA 골든크로스 — 추세 전환 신호")
    if latest["ratio"] < 1.5:
        signals.append(f"잔고비율 {latest['ratio']:.2f}% — 숏스퀴즈 압력 낮음")

    return {
        "close": cl, "bal": bal, "chg": chg, "sv": sv,
        "ratio": latest["ratio"], "risk": risk, "daily": daily,
        "direction": direction, "signals": signals,
        "price_chg": price_chg_pct, "p5": p5, "p20": p20,
    }


def make_chart(df: pd.DataFrame, days: int) -> go.Figure:
    d = df.tail(days)
    T = THRESHOLDS

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.45, 0.3, 0.25],
        vertical_spacing=0.03,
        subplot_titles=("주가 & 공매도 잔고", "당일 공매도 수량 (천주)", "거래량 (천주)"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}], [{"secondary_y": False}]],
    )

    # 주가
    fig.add_trace(go.Scatter(
        x=d.index, y=d["close"],
        name="주가", line=dict(color="#4da6ff", width=2),
    ), row=1, col=1, secondary_y=False)

    # 이평선
    fig.add_trace(go.Scatter(
        x=d.index, y=d["price_5ma"],
        name="5MA", line=dict(color="#ffd93d", width=1, dash="dot"),
    ), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(
        x=d.index, y=d["price_20ma"],
        name="20MA", line=dict(color="#ff9f43", width=1, dash="dot"),
    ), row=1, col=1, secondary_y=False)

    # 공매도 잔고 (우축)
    fig.add_trace(go.Scatter(
        x=d.index, y=d["balance"],
        name="잔고(만주)", line=dict(color="#ff6b6b", width=2, dash="dash"),
    ), row=1, col=1, secondary_y=True)

    # 위험 구간 참고선 (우축)
    for level, color, label in [
        (T["danger"],  "#ff6b6b", f"위험({T['danger']}만)"),
        (T["warning"], "#ffd93d", f"주의({T['warning']}만)"),
        (T["squeeze"], "#6bcf7f", f"스퀴즈({T['squeeze']}만)"),
    ]:
        fig.add_trace(go.Scatter(
            x=[d.index[0], d.index[-1]],
            y=[level, level],
            mode="lines",
            line=dict(color=color, width=1, dash="dot"),
            name=label,
            opacity=0.6,
        ), row=1, col=1, secondary_y=True)

    # 당일 공매도 바
    bar_colors = [
        "#ff4444" if v >= T["daily_attack"] else
        "#ffd93d" if v >= T["daily_watch"] else
        "rgba(78,205,196,0.5)"
        for v in d["short_vol"]
    ]
    fig.add_trace(go.Bar(
        x=d.index, y=d["short_vol"],
        name="당일공매도", marker_color=bar_colors, marker_line_width=0,
    ), row=2, col=1)

    # 거래량
    fig.add_trace(go.Bar(
        x=d.index, y=d["volume"] / 1000,
        name="거래량", marker_color="rgba(68,68,68,0.5)", marker_line_width=0,
    ), row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        height=620,
        showlegend=True,
        legend=dict(orientation="h", y=1.02, x=0, font=dict(size=11)),
        margin=dict(l=10, r=60, t=40, b=10),
    )
    fig.update_yaxes(title_text="주가(원)", tickformat=",",   row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="잔고(만주)", ticksuffix="만", showgrid=False, row=1, col=1, secondary_y=True)
    fig.update_yaxes(ticksuffix="천", row=2, col=1)
    fig.update_xaxes(tickformat="%m/%d", row=3, col=1)

    return fig


def badge(label: str, color: str) -> str:
    return f'<span class="badge badge-{color}">{label}</span>'


def main():
    st.title("📉 펄어비스(263750) 공매도 트래커")

    with st.sidebar:
        st.header("⚙️ 설정")
        owner = st.text_input("GitHub 사용자명", value="gonmau")
        repo  = st.text_input("레포지터리명",   value="stock-tracking")
        days  = st.slider("차트 표시 기간(일)", 30, 365, 120)
        st.markdown("---")
        st.caption("데이터 출처: KRX (pykrx)")
        st.caption("매일 오전 8시(UTC) 자동 수집")
        if st.button("🔄 새로고침"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("데이터 로드 중..."):
        meta = load_data(owner, repo)

    if "error" in meta:
        st.error(f"데이터 로드 실패: {meta['error']}")
        st.info(
            "1. GitHub 사용자명 / 레포명을 사이드바에서 확인하세요.\n"
            "2. `data/263750.json`이 레포에 있는지 확인하세요.\n"
            "3. 레포가 Public인지 확인하세요."
        )
        return

    df = build_df(meta)
    r  = analyze(df)
    realtime = get_realtime_price()
    if realtime:
        r["close"] = realtime

    st.caption(f"마지막 업데이트: {meta.get('updated_at', '-')}  |  현재가: 실시간  |  공매도 데이터: 최신 기준 T+2 지연 (약 3~4영업일 전)")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">현재가</div>
            <div class="metric-value" style="color:#4da6ff">{r['close']:,}원</div>
            <div style="font-size:12px;color:{'#6bcf7f' if r['price_chg']>=0 else '#ff6b6b'}">
                {r['price_chg']:+.2f}%</div>
        </div>""", unsafe_allow_html=True)

    with col2:
        bal_color = (
            "#ff6b6b" if r['bal'] >= THRESHOLDS["danger"] else
            "#ffd93d" if r['bal'] >= THRESHOLDS["warning"] else
            "#6bcf7f" if r['bal'] <= THRESHOLDS["squeeze"] else "#4ecdc4"
        )
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">공매도 잔고</div>
            <div class="metric-value" style="color:{bal_color}">{r['bal']:.1f}만주</div>
            <div style="font-size:12px;color:{'#ff6b6b' if r['chg']>0 else '#6bcf7f'}">
                전일比 {r['chg']:+.1f}만주</div>
        </div>""", unsafe_allow_html=True)

    with col3:
        sv_color = (
            "#ff6b6b" if r['sv'] >= THRESHOLDS["daily_attack"] else
            "#ffd93d" if r['sv'] >= THRESHOLDS["daily_watch"] else "#6bcf7f"
        )
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">당일 공매도</div>
            <div class="metric-value" style="color:{sv_color}">{r['sv']:.0f}천주</div>
        </div>""", unsafe_allow_html=True)

    with col4:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">잔고 비율</div>
            <div class="metric-value">{r['ratio']:.2f}%</div>
            <div style="font-size:11px;color:#888">발행주식 대비</div>
        </div>""", unsafe_allow_html=True)

    with col5:
        risk_colors = {"DANGER":"red","WARNING":"yellow","NEUTRAL":"cyan","SQUEEZE":"green"}
        rc = risk_colors.get(r['risk'][0], "cyan")
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">위험도</div>
            <div style="margin:6px 0">{badge(r['risk'][0], rc)}</div>
            <div style="font-size:11px;color:#888">{r['risk'][2]}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    left, right = st.columns([1, 3])

    with left:
        st.subheader("신호 분석")
        risk_colors = {"DANGER":"red","WARNING":"yellow","NEUTRAL":"cyan","SQUEEZE":"green"}
        rc = risk_colors.get(r['risk'][0], "cyan")

        st.markdown(f"""<div class="signal-row">
            <span style="color:#888;min-width:80px">위험도</span>
            {badge(r['risk'][0], rc)}
        </div>""", unsafe_allow_html=True)

        dc = "red" if "ATTACK" in r['daily'][0] else "yellow" if "WATCH" in r['daily'][0] else "green"
        st.markdown(f"""<div class="signal-row">
            <span style="color:#888;min-width:80px">당일공매도</span>
            {badge(r['daily'][0], dc)}
        </div>""", unsafe_allow_html=True)

        dirc = r['direction'][1]
        st.markdown(f"""<div class="signal-row">
            <span style="color:#888;min-width:80px">잔고 방향</span>
            {badge(r['direction'][0], dirc if dirc in ['red','yellow','cyan','green'] else 'cyan')}
        </div>""", unsafe_allow_html=True)

        ma_sig = "골든크로스 🟢" if r['p5'] > r['p20'] else "데드크로스 🔴"
        ma_c   = "green" if r['p5'] > r['p20'] else "red"
        st.markdown(f"""<div class="signal-row">
            <span style="color:#888;min-width:80px">이평선</span>
            {badge(ma_sig, ma_c)}
        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**🎯 역이용 신호**")
        if r['signals']:
            for sig in r['signals']:
                st.success(f"✓ {sig}", icon=None)
        else:
            st.caption("현재 역이용 조건 미충족")

        st.markdown("---")
        st.markdown("**📌 구간 기준**")
        st.markdown("""
| 잔고 | 신호 |
|------|------|
| 200만↑ | 🔴 위험 |
| 150~200만 | 🟡 주의 |
| 80~150만 | 🔵 중립 |
| 80만↓ | 🟢 스퀴즈 |
""")

    with right:
        fig = make_chart(df, days)
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 원시 데이터 (최근 30일)"):
        show = df.tail(30)[[
            "close", "volume", "short_vol", "balance", "balance_chg", "ratio"
        ]].copy()
        show.columns = ["종가", "거래량", "당일공매도(천주)", "잔고(만주)", "잔고변화(만주)", "잔고비율(%)"]
        show.index = show.index.strftime("%Y-%m-%d")
        st.dataframe(show.sort_index(ascending=False), use_container_width=True)


if __name__ == "__main__":
    main()
