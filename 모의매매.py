"""
모의매매.py - 자동 모의 매매 시스템
- pykrx + Naver Finance로 실시간/장외 가격 조회 (NXT 포함)
- 매매 조건 자동 판단 및 체결
- 수수료/세금 반영 손익 계산
- 디스코드 알림
- GitHub Actions 10분 간격 실행
"""

import os
import json
import time
import datetime
import requests
import traceback
from pathlib import Path

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

PORTFOLIO_FILE   = DATA_DIR / "portfolio.json"
TRADES_FILE      = DATA_DIR / "trades.json"
WATCHLIST_FILE   = DATA_DIR / "watchlist.json"
SETTINGS_FILE    = DATA_DIR / "settings.json"

DISCORD_WEBHOOK  = os.environ.get("DISCORD_WEBHOOK", "")

# 기본 설정 (settings.json 없을 때 초기값)
DEFAULT_SETTINGS = {
    "initial_cash": 10_000_000,          # 초기 현금 (원)
    "fee_rate": 0.00015,                 # 매매 수수료 0.015%
    "tax_rate": 0.0018,                  # 증권거래세 0.18% (코스피)
    "use_nxt": True,                     # NXT 장외 거래 허용
    "nxt_fee_extra": 0.0001,             # NXT 추가 수수료 (0.01%)
    "max_position_ratio": 0.3,           # 종목당 최대 비중 30%
    "stop_loss_pct": -5.0,               # 손절 -5%
    "take_profit_pct": 10.0,             # 익절 +10%
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "ma_short": 5,
    "ma_long": 20,
}


# ─────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────
def load_json(path, default):
    if Path(path).exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def is_krx_open():
    """한국 장 시간 여부 (09:00~15:30, 평일)"""
    now = datetime.datetime.now()
    if now.weekday() >= 5:  # 토/일
        return False
    t = now.time()
    return datetime.time(9, 0) <= t <= datetime.time(15, 30)

def is_nxt_open():
    """NXT 장외 시간 여부 (08:00~09:00, 15:40~20:00, 평일)"""
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    morning = datetime.time(8, 0) <= t < datetime.time(9, 0)
    evening = datetime.time(15, 40) <= t <= datetime.time(20, 0)
    return morning or evening


# ─────────────────────────────────────────
# 가격 조회
# ─────────────────────────────────────────
def get_price_naver(ticker: str) -> dict:
    """
    Naver Finance API - 실시간 + NXT 장외 가격
    overMarketPriceInfo 포함
    """
    url = f"https://m.stock.naver.com/api/stock/{ticker}/integration"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        d = r.json()

        # 현재가
        current_price = int(d.get("dealTrendInfos", [{}])[0].get("closePrice", 0) or 0)
        if not current_price:
            current_price = int(d.get("stockEndQuoteInfos", {}).get("closePrice", 0) or 0)

        # NXT 장외가 (overMarketPriceInfo)
        nxt_price = 0
        nxt_change_rate = 0.0
        over_info = d.get("overMarketPriceInfo", {})
        if over_info:
            nxt_price = int(over_info.get("price", 0) or 0)
            nxt_change_rate = float(over_info.get("changeRate", 0) or 0)

        return {
            "ticker": ticker,
            "price": current_price,
            "nxt_price": nxt_price,
            "nxt_change_rate": nxt_change_rate,
            "source": "naver",
            "ts": now_str(),
        }
    except Exception as e:
        print(f"[WARN] Naver price fetch failed for {ticker}: {e}")
        return {"ticker": ticker, "price": 0, "nxt_price": 0, "source": "error", "ts": now_str()}

def get_price_pykrx(ticker: str) -> int:
    """pykrx로 당일 종가 조회 (장 마감 후 fallback)"""
    try:
        from pykrx import stock as krx
        today = datetime.datetime.now().strftime("%Y%m%d")
        df = krx.get_market_ohlcv_by_date(today, today, ticker)
        if not df.empty:
            return int(df["종가"].iloc[-1])
    except Exception as e:
        print(f"[WARN] pykrx price failed for {ticker}: {e}")
    return 0

def get_ohlcv_history(ticker: str, days: int = 60) -> list:
    """pykrx로 OHLCV 히스토리 (기술 지표 계산용)"""
    try:
        from pykrx import stock as krx
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=days * 2)  # 주말 여유
        df = krx.get_market_ohlcv_by_date(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), ticker
        )
        if df.empty:
            return []
        result = []
        for idx, row in df.iterrows():
            result.append({
                "date": str(idx.date()),
                "open": int(row["시가"]),
                "high": int(row["고가"]),
                "low": int(row["저가"]),
                "close": int(row["종가"]),
                "volume": int(row["거래량"]),
            })
        return result[-days:]
    except Exception as e:
        print(f"[WARN] OHLCV history failed for {ticker}: {e}")
        return []

def get_effective_price(ticker: str, settings: dict) -> dict:
    """
    현재 유효 가격 결정:
    - 정규장 중: Naver 현재가
    - NXT 시간 + use_nxt=True: Naver NXT가
    - 그 외: pykrx 종가
    반환: {price, source, is_nxt, ts}
    """
    nav = get_price_naver(ticker)
    is_nxt_time = is_nxt_open() and settings.get("use_nxt", True)

    if is_krx_open() and nav["price"] > 0:
        return {"price": nav["price"], "source": "naver_realtime", "is_nxt": False, "ts": nav["ts"]}

    if is_nxt_time and nav["nxt_price"] > 0:
        return {"price": nav["nxt_price"], "source": "naver_nxt", "is_nxt": True, "ts": nav["ts"]}

    # fallback: pykrx 종가
    krx_price = get_price_pykrx(ticker)
    if krx_price > 0:
        return {"price": krx_price, "source": "pykrx_close", "is_nxt": False, "ts": now_str()}

    # 마지막 fallback: naver 현재가라도
    if nav["price"] > 0:
        return {"price": nav["price"], "source": "naver_fallback", "is_nxt": False, "ts": nav["ts"]}

    return {"price": 0, "source": "unavailable", "is_nxt": False, "ts": now_str()}


# ─────────────────────────────────────────
# 기술 지표
# ─────────────────────────────────────────
def calc_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)

def calc_ma(closes: list, period: int) -> float:
    if len(closes) < period:
        return 0.0
    return round(sum(closes[-period:]) / period, 2)

def get_indicators(ticker: str, settings: dict) -> dict:
    history = get_ohlcv_history(ticker, days=60)
    if not history:
        return {"rsi": 50, "ma_short": 0, "ma_long": 0, "price_history": []}
    closes = [h["close"] for h in history]
    rsi = calc_rsi(closes, settings["rsi_period"])
    ma_s = calc_ma(closes, settings["ma_short"])
    ma_l = calc_ma(closes, settings["ma_long"])
    return {
        "rsi": rsi,
        "ma_short": ma_s,
        "ma_long": ma_l,
        "price_history": history[-30:],  # 최근 30일
    }


# ─────────────────────────────────────────
# 매매 조건 판단
# ─────────────────────────────────────────
def should_buy(ticker: str, watchlist_item: dict, portfolio: dict, settings: dict) -> tuple[bool, str]:
    """
    매수 조건:
    1. 사용자 정의 조건 (watchlist_item에 strategy 포함)
    2. RSI 과매도 (<30)
    3. MA 골든크로스 (단기 > 장기)
    """
    strategy = watchlist_item.get("strategy", "rsi_ma")  # default: rsi+ma 복합
    cash = portfolio.get("cash", 0)
    total_value = portfolio_total_value(portfolio)
    max_invest = total_value * settings["max_position_ratio"]

    # 이미 보유 중이면 추가 매수 안 함 (단순 전략)
    positions = portfolio.get("positions", {})
    if ticker in positions and positions[ticker]["qty"] > 0:
        # 보유 중: 손절/익절만 체크
        return False, "already_holding"

    if cash < 100_000:
        return False, "insufficient_cash"

    ind = get_indicators(ticker, settings)
    rsi = ind["rsi"]
    ma_s = ind["ma_short"]
    ma_l = ind["ma_long"]

    reasons = []
    buy_signal = False

    if strategy in ("rsi", "rsi_ma"):
        if rsi < settings["rsi_oversold"]:
            reasons.append(f"RSI={rsi:.1f}(과매도)")
            buy_signal = True

    if strategy in ("ma", "rsi_ma"):
        if ma_s > ma_l > 0:
            reasons.append(f"골든크로스(MA{settings['ma_short']}={ma_s:.0f}>MA{settings['ma_long']}={ma_l:.0f})")
            if strategy == "rsi_ma":
                # rsi_ma 전략: 두 조건 모두 필요
                buy_signal = buy_signal and True
            else:
                buy_signal = True

    if strategy == "manual":
        return False, "manual_only"

    return buy_signal, " + ".join(reasons) if reasons else "no_signal"

def should_sell(ticker: str, position: dict, current_price: int, settings: dict) -> tuple[bool, str]:
    """
    매도 조건:
    1. 손절 (stop_loss_pct)
    2. 익절 (take_profit_pct)
    3. RSI 과매수 (>70)
    4. MA 데드크로스
    """
    avg_cost = position.get("avg_cost", 0)
    if avg_cost == 0:
        return False, "no_position"

    pnl_pct = (current_price - avg_cost) / avg_cost * 100

    # 손절
    if pnl_pct <= settings["stop_loss_pct"]:
        return True, f"손절({pnl_pct:.2f}% ≤ {settings['stop_loss_pct']}%)"

    # 익절
    if pnl_pct >= settings["take_profit_pct"]:
        return True, f"익절({pnl_pct:.2f}% ≥ {settings['take_profit_pct']}%)"

    # 기술적 매도 (캐시된 지표 사용)
    if "_indicators" in position:
        ind = position["_indicators"]
        rsi = ind.get("rsi", 50)
        ma_s = ind.get("ma_short", 0)
        ma_l = ind.get("ma_long", 0)

        if rsi > settings["rsi_overbought"]:
            return True, f"RSI={rsi:.1f}(과매수)"

        if ma_s < ma_l and ma_l > 0:
            return True, f"데드크로스(MA{settings['ma_short']}={ma_s:.0f}<MA{settings['ma_long']}={ma_l:.0f})"

    return False, f"보유중({pnl_pct:.2f}%)"


# ─────────────────────────────────────────
# 손익 계산 (수수료/세금 포함)
# ─────────────────────────────────────────
def calc_buy_cost(price: int, qty: int, settings: dict, is_nxt: bool = False) -> dict:
    gross = price * qty
    fee_rate = settings["fee_rate"] + (settings["nxt_fee_extra"] if is_nxt else 0)
    fee = round(gross * fee_rate)
    total = gross + fee
    return {"gross": gross, "fee": fee, "tax": 0, "total": total}

def calc_sell_proceeds(price: int, qty: int, settings: dict, is_nxt: bool = False) -> dict:
    gross = price * qty
    fee_rate = settings["fee_rate"] + (settings["nxt_fee_extra"] if is_nxt else 0)
    fee = round(gross * fee_rate)
    tax = round(gross * settings["tax_rate"])
    total = gross - fee - tax
    return {"gross": gross, "fee": fee, "tax": tax, "total": total}

def portfolio_total_value(portfolio: dict) -> float:
    cash = portfolio.get("cash", 0)
    pos_value = sum(
        p.get("qty", 0) * p.get("last_price", p.get("avg_cost", 0))
        for p in portfolio.get("positions", {}).values()
    )
    return cash + pos_value


# ─────────────────────────────────────────
# 포트폴리오 초기화
# ─────────────────────────────────────────
def init_portfolio(settings: dict) -> dict:
    return {
        "cash": settings["initial_cash"],
        "positions": {},
        "created_at": now_str(),
        "last_updated": now_str(),
    }


# ─────────────────────────────────────────
# 디스코드 알림
# ─────────────────────────────────────────
def discord_notify(msg: str):
    if not DISCORD_WEBHOOK:
        print(f"[Discord] {msg}")
        return
    try:
        payload = {"content": msg, "username": "모의매매봇"}
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"[WARN] Discord notify failed: {e}")


# ─────────────────────────────────────────
# 매매 실행
# ─────────────────────────────────────────
def execute_buy(ticker: str, price: int, reason: str,
                portfolio: dict, trades: list, settings: dict,
                is_nxt: bool = False, ticker_name: str = ""):
    total_value = portfolio_total_value(portfolio)
    max_invest = total_value * settings["max_position_ratio"]
    invest = min(portfolio["cash"] * 0.5, max_invest)  # 현금 50% 또는 max_position 중 작은 값
    invest = max(invest, 100_000)  # 최소 10만원
    qty = int(invest // price)

    if qty <= 0:
        print(f"[SKIP] {ticker} 매수 수량 0 (invest={invest:,}, price={price:,})")
        return False

    cost = calc_buy_cost(price, qty, settings, is_nxt)
    if cost["total"] > portfolio["cash"]:
        qty = int((portfolio["cash"] * 0.99) // (price * (1 + settings["fee_rate"])))
        if qty <= 0:
            return False
        cost = calc_buy_cost(price, qty, settings, is_nxt)

    portfolio["cash"] -= cost["total"]

    pos = portfolio["positions"].get(ticker, {"qty": 0, "avg_cost": 0, "total_cost": 0})
    new_total_cost = pos["total_cost"] + cost["total"]
    new_qty = pos["qty"] + qty
    portfolio["positions"][ticker] = {
        "qty": new_qty,
        "avg_cost": round(new_total_cost / new_qty),
        "total_cost": new_total_cost,
        "last_price": price,
        "name": ticker_name or ticker,
    }

    trade = {
        "id": f"{ticker}_{int(time.time())}",
        "ticker": ticker,
        "name": ticker_name or ticker,
        "type": "BUY",
        "price": price,
        "qty": qty,
        "gross": cost["gross"],
        "fee": cost["fee"],
        "tax": 0,
        "net": cost["total"],
        "reason": reason,
        "is_nxt": is_nxt,
        "ts": now_str(),
    }
    trades.append(trade)

    nxt_tag = " [NXT]" if is_nxt else ""
    msg = (
        f"📈 **모의매매 매수{nxt_tag}**\n"
        f"종목: {ticker_name or ticker} ({ticker})\n"
        f"가격: {price:,}원 × {qty}주 = {cost['gross']:,}원\n"
        f"수수료: {cost['fee']:,}원 | 총비용: {cost['total']:,}원\n"
        f"사유: {reason}\n"
        f"잔여 현금: {portfolio['cash']:,.0f}원"
    )
    discord_notify(msg)
    print(f"[BUY] {ticker} {qty}주 @ {price:,} | {reason}")
    return True

def execute_sell(ticker: str, price: int, reason: str,
                 portfolio: dict, trades: list, settings: dict,
                 is_nxt: bool = False):
    pos = portfolio["positions"].get(ticker)
    if not pos or pos["qty"] <= 0:
        return False

    qty = pos["qty"]
    proceeds = calc_sell_proceeds(price, qty, settings, is_nxt)
    avg_cost = pos["avg_cost"]
    realized_pnl = proceeds["total"] - pos["total_cost"]
    pnl_pct = realized_pnl / pos["total_cost"] * 100

    portfolio["cash"] += proceeds["total"]
    del portfolio["positions"][ticker]

    trade = {
        "id": f"{ticker}_{int(time.time())}",
        "ticker": ticker,
        "name": pos.get("name", ticker),
        "type": "SELL",
        "price": price,
        "qty": qty,
        "gross": proceeds["gross"],
        "fee": proceeds["fee"],
        "tax": proceeds["tax"],
        "net": proceeds["total"],
        "realized_pnl": realized_pnl,
        "pnl_pct": round(pnl_pct, 2),
        "reason": reason,
        "is_nxt": is_nxt,
        "ts": now_str(),
    }
    trades.append(trade)

    emoji = "✅" if realized_pnl >= 0 else "🔴"
    nxt_tag = " [NXT]" if is_nxt else ""
    msg = (
        f"{emoji} **모의매매 매도{nxt_tag}**\n"
        f"종목: {pos.get('name', ticker)} ({ticker})\n"
        f"가격: {price:,}원 × {qty}주 = {proceeds['gross']:,}원\n"
        f"수수료: {proceeds['fee']:,}원 | 세금: {proceeds['tax']:,}원\n"
        f"실현 손익: {realized_pnl:+,.0f}원 ({pnl_pct:+.2f}%)\n"
        f"사유: {reason}\n"
        f"잔여 현금: {portfolio['cash']:,.0f}원"
    )
    discord_notify(msg)
    print(f"[SELL] {ticker} {qty}주 @ {price:,} | pnl={realized_pnl:+,.0f} | {reason}")
    return True


# ─────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────
def run():
    print(f"========== 모의매매 실행: {now_str()} ==========")

    settings  = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    # 누락된 설정 키 기본값으로 보완
    for k, v in DEFAULT_SETTINGS.items():
        settings.setdefault(k, v)

    portfolio = load_json(PORTFOLIO_FILE, None)
    if portfolio is None:
        portfolio = init_portfolio(settings)
        print("[INFO] 포트폴리오 초기화")

    trades   = load_json(TRADES_FILE, [])
    watchlist = load_json(WATCHLIST_FILE, [])

    if not watchlist:
        print("[INFO] 감시 종목 없음. watchlist.json 추가 필요")
        # 대시보드에서 추가 가능하므로 종료하지 않고 계속

    open_krx = is_krx_open()
    open_nxt = is_nxt_open() and settings.get("use_nxt", True)

    if not open_krx and not open_nxt:
        print("[INFO] 장 닫힘 (정규장 + NXT 모두 비활성). 종료")
        # 마지막 가격만 업데이트하고 저장
        for ticker, pos in portfolio["positions"].items():
            pi = get_effective_price(ticker, settings)
            if pi["price"] > 0:
                pos["last_price"] = pi["price"]
        portfolio["last_updated"] = now_str()
        save_json(PORTFOLIO_FILE, portfolio)
        save_json(TRADES_FILE, trades)
        _write_summary(portfolio, trades, settings)
        return

    print(f"[INFO] 정규장={open_krx}, NXT={open_nxt}")

    for item in watchlist:
        ticker = item.get("ticker", "").strip()
        ticker_name = item.get("name", ticker)
        if not ticker:
            continue
        if not item.get("active", True):
            continue

        print(f"\n--- {ticker_name}({ticker}) ---")

        # 가격 조회
        pi = get_effective_price(ticker, settings)
        current_price = pi["price"]
        is_nxt = pi["is_nxt"]

        if current_price == 0:
            print(f"[WARN] {ticker} 가격 조회 실패, 건너뜀")
            continue

        print(f"  가격: {current_price:,}원 (소스={pi['source']}, NXT={is_nxt})")

        # NXT 허용 여부 재확인
        if is_nxt and not settings.get("use_nxt", True):
            print(f"  NXT 비활성화, 건너뜀")
            continue

        # 기술 지표
        ind = get_indicators(ticker, settings)
        print(f"  RSI={ind['rsi']:.1f}, MA{settings['ma_short']}={ind['ma_short']:.0f}, MA{settings['ma_long']}={ind['ma_long']:.0f}")

        # 포지션 업데이트
        if ticker in portfolio["positions"]:
            portfolio["positions"][ticker]["last_price"] = current_price
            portfolio["positions"][ticker]["_indicators"] = ind

        # 매도 조건 체크
        if ticker in portfolio["positions"] and portfolio["positions"][ticker]["qty"] > 0:
            sell_flag, sell_reason = should_sell(ticker, portfolio["positions"][ticker], current_price, settings)
            if sell_flag:
                execute_sell(ticker, current_price, sell_reason, portfolio, trades, settings, is_nxt)
                continue  # 매도 후 매수 판단 불필요

        # 매수 조건 체크
        buy_flag, buy_reason = should_buy(ticker, item, portfolio, settings)
        if buy_flag:
            execute_buy(ticker, current_price, buy_reason, portfolio, trades, settings, is_nxt, ticker_name)

    # 저장
    portfolio["last_updated"] = now_str()
    save_json(PORTFOLIO_FILE, portfolio)
    save_json(TRADES_FILE, trades)
    _write_summary(portfolio, trades, settings)
    print("\n[INFO] 저장 완료")


def _write_summary(portfolio: dict, trades: list, settings: dict):
    """대시보드용 summary.json 생성"""
    total_value = portfolio_total_value(portfolio)
    initial = settings["initial_cash"]
    total_pnl = total_value - initial
    total_pnl_pct = total_pnl / initial * 100

    realized = sum(t.get("realized_pnl", 0) for t in trades if t["type"] == "SELL")

    positions_out = []
    for ticker, pos in portfolio.get("positions", {}).items():
        last_p = pos.get("last_price", pos["avg_cost"])
        unreal = (last_p - pos["avg_cost"]) * pos["qty"]
        unreal_pct = (last_p - pos["avg_cost"]) / pos["avg_cost"] * 100
        positions_out.append({
            "ticker": ticker,
            "name": pos.get("name", ticker),
            "qty": pos["qty"],
            "avg_cost": pos["avg_cost"],
            "last_price": last_p,
            "market_value": last_p * pos["qty"],
            "unrealized_pnl": round(unreal),
            "unrealized_pnl_pct": round(unreal_pct, 2),
        })

    summary = {
        "last_updated": now_str(),
        "cash": portfolio["cash"],
        "total_value": round(total_value),
        "initial_cash": initial,
        "total_pnl": round(total_pnl),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "realized_pnl": round(realized),
        "positions": positions_out,
        "trade_count": len(trades),
        "settings": {
            k: settings[k] for k in
            ["fee_rate", "tax_rate", "stop_loss_pct", "take_profit_pct",
             "use_nxt", "max_position_ratio"]
        },
    }
    save_json(DATA_DIR / "summary.json", summary)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        discord_notify(f"⚠️ 모의매매 오류 발생\n```\n{traceback.format_exc()[-500:]}\n```")
        raise
