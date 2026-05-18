import sqlite3
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

DB_PATH = "data/short_interest.db"

st.set_page_config(
    page_title="펄어비스 공매도 추적기",
    layout="wide"
)

st.title("펄어비스 공매도 추적기")

conn = sqlite3.connect(DB_PATH)

df = pd.read_sql(
    "SELECT * FROM pearlabyss_short",
    conn
)

conn.close()

df["날짜"] = pd.to_datetime(df["날짜"])

latest = df.iloc[-1]

# KPI
col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "현재가",
    f"{latest['close']:,.0f}원"
)

col2.metric(
    "공매도 비율",
    f"{latest['short_ratio']:.2f}%"
)

col3.metric(
    "잔고 비율",
    f"{latest['balance_ratio']:.2f}%"
)

col4.metric(
    "Z-Score",
    f"{latest['short_zscore']:.2f}"
)

st.divider()

# 차트 1
fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=df["날짜"],
        y=df["close"],
        name="주가"
    )
)

fig.add_trace(
    go.Scatter(
        x=df["날짜"],
        y=df["balance_ratio"],
        name="공매도잔고비율",
        yaxis="y2"
    )
)

fig.update_layout(
    title="주가 vs 공매도잔고",
    yaxis2=dict(
        overlaying="y",
        side="right"
    )
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# 공매도 비율
fig2 = go.Figure()

fig2.add_trace(
    go.Bar(
        x=df["날짜"],
        y=df["short_ratio"],
        name="공매도비율"
    )
)

st.plotly_chart(
    fig2,
    use_container_width=True
)

# 이상탐지
danger = df[df["short_zscore"] >= 3]

st.subheader("비정상 공매도 감지")

st.dataframe(
    danger[[
        "날짜",
        "close",
        "short_ratio",
        "short_zscore"
    ]]
)
