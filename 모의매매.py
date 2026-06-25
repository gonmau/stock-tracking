"""
모의매매.py - 자동 모의 매매 시스템 v2
- pykrx + Naver Finance 실시간/NXT 가격 조회
- 자동 전략: RSI, MA, RSI+MA 복합
- 수동 조건: 지정가 / 변동률(직전 대비 ±%) / 등락률(전일 대비 ±%)
- 수수료/세금 반영 손익 계산
- 5분 간격 GitHub Actions 실행
- 디스코드 알림
"""

import os, json, time, datetime, requests, traceback
from pathlib import Path

# ─────────────────────────────────────────
# 경로
# ─────────────────────────────────────────
DATA_DIR       = Path("data")
DATA_DIR.mkdir(exist_ok=True)
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
TRADES_FILE    = DATA_DIR / "trades.json"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
SETTINGS_FILE  = DATA_DIR / "settings.json"
PRICE_FILE     = DATA_DIR / "last_prices.json"   # 직전 실행 가격 저장

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

# ─────────────────────────────────────────
# 기본 설정
# ─────────────────────────────────────────
DEFAULT_SETTINGS = {
    "initial_cash":        10_000_000,
    "fee_rate":            0.00015,    # 수수료 0.015%
    "tax_rate":            0.0018,     # 증권거래세 0.18%
    "use_nxt":             True,
    "nxt_fee_extra":       0.0001,
    "max_position_ratio":  0.3,        # 종목당 최대 비중
    "buy_amount_ratio":    0.5,        # 1회 매수 현금 비율
    "stop_loss_pct":      -5.0,
    "take_profit_pct":    10.0,
    "rsi_period":         14,
    "rsi_oversold":       30,
    "rsi_overbought":     70,
    "ma_short":            5,
    "ma_long":            20,
}

# ─────────────────────────────────────────
# 감시종목 조건 스키마 예시
# ─────────────────────────────────────────
# {
#   "ticker": "263750",
#   "name": "펄어비스",
#   "active": true,
#   "strategy": "manual",          # rsi / ma / rsi_ma / manual
#
#   ── 수동 조건 (strategy=manual 또는 어떤 전략이든 함께 사용 가능) ──
#   "buy_conditions": [
#     {"type": "price_below",   "value": 22000},          # 현재가 ≤ 22000원
#     {"type": "price_above",   "value": 20000},          # 현재가 ≥ 20000원
#     {"type": "change_down",   "value": 3.0},            # 직전 실행 대비 -3% 이하 하락
#     {"type": "change_up",     "value": 3.0},            # 직전 실행 대비 +3% 이상 상승
#     {"type": "day_change_down","value": 5.0},           # 전일 종가 대비 -5% 이하
#     {"type": "day_change_up", "value": 5.0},            # 전일 종가 대비 +5% 이상
#   ],
#   "sell_conditions": [
#     {"type": "price_above",   "value": 25000},
#     {"type": "change_up",     "value": 2.0},
#     {"type": "day_change_up", "value": 8.0},
#   ],
#   "condition_logic": "OR"   # OR(하나라도) / AND(모두) - 기본 OR
# }


# ─────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────
def load_json(path, default):
    p = Path(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def is_krx_open():
    now = datetime.datetime.now()
    if now.weekday() >= 5: return False
    t = now.time()
    return datetime.time(9, 0) <= t <= datetime.time(15, 30)

def is_nxt_open():
    now = datetime.datetime.now()
    if now.weekday() >= 5: return False
    t = now.time()
    return (datetime.time(8, 0) <= t < datetime.time(9, 0)) or \
           (datetime.time(15, 40) <= t <= datetime.time(20, 0))


# ─────────────────────────────────────────
# 가격 조회
# ─────────────────────────────────────────
def get_price_naver(ticker: str) -> dict:
    url = f"https://m.stock.naver.com/api/stock/{ticker}/integration"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        r.raise_for_status()
        d = r.json()

        current = 0
        prev_close = 0  # 전일 종가

        # 현재가
        deal = d.get("dealTrendInfos", [])
        if deal:
            current = int(deal[0].get("closePrice", 0) or 0)

        # 전일 종가 (기준가)
        end_info = d.get("stockEndQuoteInfos", {})
        if not current:
            current = int(end_info.get("closePrice", 0) or 0)
        prev_close = int(end_info.get("basePrice", 0) or 0)

        # NXT 장외가
        nxt_price = 0
        over = d.get("overMarketPriceInfo", {})
        if over:
            nxt_price = int(over.get("price", 0) or 0)

        return {
            "ticker": ticker,
            "price": current,
            "prev_close": prev_close,
            "nxt_price": nxt_price,
            "ts": now_str(),
        }
    except Exception as e:
        print(f"[WARN] Naver {ticker}: {e}")
        return {"ticker": ticker, "price": 0, "prev_close": 0, "nxt_price": 0, "ts": now_str()}

def get_effective_price(ticker: str, settings: dict) -> dict:
    nav = get_price_naver(ticker)
    is_nxt_time = is_nxt_open() and settings.get("use_nxt", True)

    if is_krx_open() and nav["price"] > 0:
        return {**nav, "source": "realtime", "is_nxt": False}
    if is_nxt_time and nav["nxt_price"] > 0:
        return {**nav, "price": nav["nxt_price"], "source": "nxt", "is_nxt": True}
    if nav["price"] > 0:
        return {**nav, "source": "naver_close", "is_nxt": False}
    return {**nav, "price": 0, "source": "unavailable", "is_nxt": False}

def get_ohlcv(ticker: str, days: int = 60) -> list:
    try:
        from pykrx import stock as krx
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=days * 2)
        df = krx.get_market_ohlcv_by_date(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), ticker)
        if df.empty: return []
        return [{"date": str(i.date()), "close": int(r["종가"])}
                for i, r in df.iterrows()][-days:]
    except Exception as e:
        print(f"[WARN] OHLCV {ticker}: {e}")
        return []


# ─────────────────────────────────────────
# 기술 지표
# ─────────────────────────────────────────
def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return 50.0
    gains = [max(closes[i]-closes[i-1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i-1]-closes[i], 0) for i in range(1, len(closes))]
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0: return 100.0
    return round(100 - 100 / (1 + ag / al), 2)

def calc_ma(closes, period):
    if len(closes) < period: return 0.0
    return round(sum(closes[-period:]) / period, 2)

def get_indicators(ticker, settings):
    hist = get_ohlcv(ticker, 60)
    if not hist:
        return {"rsi": 50, "ma_short": 0, "ma_long": 0}
    closes = [h["close"] for h in hist]
    return {
        "rsi": calc_rsi(closes, settings["rsi_period"]),
        "ma_short": calc_ma(closes, settings["ma_short"]),
        "ma_long": calc_ma(closes, settings["ma_long"]),
    }


# ─────────────────────────────────────────
# 수동 조건 판단
# ─────────────────────────────────────────
def check_conditions(conditions: list, logic: str,
                     current_price: int, prev_price: int, prev_close: int) -> tuple[bool, list]:
    """
    conditions: watchlist의 buy_conditions / sell_conditions
    logic: "OR" | "AND"
    prev_price: 직전 실행 시 가격 (last_prices.json)
    prev_close: 전일 종가 (Naver API)
    반환: (충족여부, 충족된 조건 설명 리스트)
    """
    if not conditions:
        return False, []

    matched = []
    for cond in conditions:
        t = cond.get("type", "")
        v = float(cond.get("value", 0))
        hit = False
        desc = ""

        if t == "price_below" and current_price > 0:
            hit = current_price <= v
            desc = f"현재가({current_price:,}) ≤ 지정가({int(v):,})"

        elif t == "price_above" and current_price > 0:
            hit = current_price >= v
            desc = f"현재가({current_price:,}) ≥ 지정가({int(v):,})"

        elif t == "change_down" and prev_price > 0:
            chg = (current_price - prev_price) / prev_price * 100
            hit = chg <= -abs(v)
            desc = f"직전대비 {chg:+.2f}% (기준 -{abs(v):.1f}%)"

        elif t == "change_up" and prev_price > 0:
            chg = (current_price - prev_price) / prev_price * 100
            hit = chg >= abs(v)
            desc = f"직전대비 {chg:+.2f}% (기준 +{abs(v):.1f}%)"

        elif t == "day_change_down" and prev_close > 0:
            chg = (current_price - prev_close) / prev_close * 100
            hit = chg <= -abs(v)
            desc = f"전일대비 {chg:+.2f}% (기준 -{abs(v):.1f}%)"

        elif t == "day_change_up" and prev_close > 0:
            chg = (current_price - prev_close) / prev_close * 100
            hit = chg >= abs(v)
            desc = f"전일대비 {chg:+.2f}% (기준 +{abs(v):.1f}%)"

        if hit:
            matched.append(desc)

    if logic == "AND":
        satisfied = len(matched) == len(conditions)
    else:  # OR
        satisfied = len(matched) > 0

    return satisfied, matched


# ─────────────────────────────────────────
# 자동 전략 판단
# ─────────────────────────────────────────
def auto_buy_signal(strategy: str, ind: dict, settings: dict) -> tuple[bool, str]:
    if strategy == "rsi":
        ok = ind["rsi"] < settings["rsi_oversold"]
        return ok, f"RSI={ind['rsi']:.1f}(과매도<{settings['rsi_oversold']})"

    if strategy == "ma":
        ok = ind["ma_short"] > ind["ma_long"] > 0
        return ok, f"골든크로스(MA{settings['ma_short']}={ind['ma_short']:.0f}>MA{settings['ma_long']}={ind['ma_long']:.0f})"

    if strategy == "rsi_ma":
        rsi_ok = ind["rsi"] < settings["rsi_oversold"]
        ma_ok  = ind["ma_short"] > ind["ma_long"] > 0
        ok = rsi_ok and ma_ok
        parts = []
        if rsi_ok: parts.append(f"RSI={ind['rsi']:.1f}")
        if ma_ok:  parts.append(f"골든크로스")
        return ok, " + ".join(parts)

    return False, ""

def auto_sell_signal(strategy: str, ind: dict, settings: dict) -> tuple[bool, str]:
    if strategy == "rsi":
        ok = ind["rsi"] > settings["rsi_overbought"]
        return ok, f"RSI={ind['rsi']:.1f}(과매수>{settings['rsi_overbought']})"

    if strategy in ("ma", "rsi_ma"):
        ok = 0 < ind["ma_short"] < ind["ma_long"]
        return ok, f"데드크로스(MA{settings['ma_short']}={ind['ma_short']:.0f}<MA{settings['ma_long']}={ind['ma_long']:.0f})"

    return False, ""


# ─────────────────────────────────────────
# 손익 계산
# ─────────────────────────────────────────
def calc_buy_cost(price, qty, settings, is_nxt=False):
    gross = price * qty
    fee = round(gross * (settings["fee_rate"] + (settings["nxt_fee_extra"] if is_nxt else 0)))
    return {"gross": gross, "fee": fee, "tax": 0, "total": gross + fee}

def calc_sell_proceeds(price, qty, settings, is_nxt=False):
    gross = price * qty
    fee = round(gross * (settings["fee_rate"] + (settings["nxt_fee_extra"] if is_nxt else 0)))
    tax = round(gross * settings["tax_rate"])
    return {"gross": gross, "fee": fee, "tax": tax, "total": gross - fee - tax}

def portfolio_total_value(portfolio):
    return portfolio.get("cash", 0) + sum(
        p.get("qty", 0) * p.get("last_price", p.get("avg_cost", 0))
        for p in portfolio.get("positions", {}).values()
    )


# ─────────────────────────────────────────
# 디스코드
# ─────────────────────────────────────────
def discord_notify(msg: str):
    if not DISCORD_WEBHOOK:
        print(f"[Discord] {msg}")
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg, "username": "모의매매봇"}, timeout=5)
    except Exception as e:
        print(f"[WARN] Discord: {e}")


# ─────────────────────────────────────────
# 매매 실행
# ─────────────────────────────────────────
def execute_buy(ticker, price, reason, portfolio, trades, settings,
                is_nxt=False, name=""):
    tv = portfolio_total_value(portfolio)
    max_inv = tv * settings["max_position_ratio"]
    invest  = min(portfolio["cash"] * settings["buy_amount_ratio"], max_inv)
    qty = int(invest // price)
    if qty <= 0: return False

    cost = calc_buy_cost(price, qty, settings, is_nxt)
    if cost["total"] > portfolio["cash"]:
        qty = int(portfolio["cash"] * 0.99 // (price * (1 + settings["fee_rate"])))
        if qty <= 0: return False
        cost = calc_buy_cost(price, qty, settings, is_nxt)

    portfolio["cash"] -= cost["total"]
    pos = portfolio["positions"].get(ticker, {"qty": 0, "avg_cost": 0, "total_cost": 0})
    new_qty  = pos["qty"] + qty
    new_cost = pos["total_cost"] + cost["total"]
    portfolio["positions"][ticker] = {
        "qty": new_qty, "avg_cost": round(new_cost / new_qty),
        "total_cost": new_cost, "last_price": price, "name": name or ticker,
    }

    trades.append({
        "id": f"{ticker}_{int(time.time())}", "ticker": ticker, "name": name or ticker,
        "type": "BUY", "price": price, "qty": qty,
        "gross": cost["gross"], "fee": cost["fee"], "tax": 0, "net": cost["total"],
        "reason": reason, "is_nxt": is_nxt, "ts": now_str(),
    })

    nxt = " [NXT]" if is_nxt else ""
    discord_notify(
        f"📈 **모의매매 매수{nxt}**\n"
        f"종목: {name or ticker} ({ticker})\n"
        f"가격: {price:,}원 × {qty}주 = {cost['gross']:,}원\n"
        f"수수료: {cost['fee']:,}원 | 총비용: {cost['total']:,}원\n"
        f"사유: {reason}\n"
        f"잔여현금: {portfolio['cash']:,.0f}원"
    )
    print(f"[BUY]  {ticker} {qty}주 @ {price:,} | {reason}")
    return True

def execute_sell(ticker, price, reason, portfolio, trades, settings, is_nxt=False):
    pos = portfolio["positions"].get(ticker)
    if not pos or pos["qty"] <= 0: return False

    qty = pos["qty"]
    proc = calc_sell_proceeds(price, qty, settings, is_nxt)
    pnl  = proc["total"] - pos["total_cost"]
    pct  = pnl / pos["total_cost"] * 100

    portfolio["cash"] += proc["total"]
    del portfolio["positions"][ticker]

    trades.append({
        "id": f"{ticker}_{int(time.time())}", "ticker": ticker, "name": pos.get("name", ticker),
        "type": "SELL", "price": price, "qty": qty,
        "gross": proc["gross"], "fee": proc["fee"], "tax": proc["tax"], "net": proc["total"],
        "realized_pnl": round(pnl), "pnl_pct": round(pct, 2),
        "reason": reason, "is_nxt": is_nxt, "ts": now_str(),
    })

    emoji = "✅" if pnl >= 0 else "🔴"
    nxt = " [NXT]" if is_nxt else ""
    discord_notify(
        f"{emoji} **모의매매 매도{nxt}**\n"
        f"종목: {pos.get('name', ticker)} ({ticker})\n"
        f"가격: {price:,}원 × {qty}주 = {proc['gross']:,}원\n"
        f"수수료: {proc['fee']:,}원 | 세금: {proc['tax']:,}원\n"
        f"실현손익: {pnl:+,.0f}원 ({pct:+.2f}%)\n"
        f"사유: {reason}\n"
        f"잔여현금: {portfolio['cash']:,.0f}원"
    )
    print(f"[SELL] {ticker} {qty}주 @ {price:,} | pnl={pnl:+,.0f} | {reason}")
    return True


# ─────────────────────────────────────────
# summary.json 생성
# ─────────────────────────────────────────
def write_summary(portfolio, trades, settings):
    tv = portfolio_total_value(portfolio)
    initial = settings["initial_cash"]
    realized = sum(t.get("realized_pnl", 0) for t in trades if t["type"] == "SELL")

    positions_out = []
    for ticker, pos in portfolio.get("positions", {}).items():
        lp = pos.get("last_price", pos["avg_cost"])
        unreal = (lp - pos["avg_cost"]) * pos["qty"]
        positions_out.append({
            "ticker": ticker, "name": pos.get("name", ticker),
            "qty": pos["qty"], "avg_cost": pos["avg_cost"],
            "last_price": lp, "market_value": lp * pos["qty"],
            "unrealized_pnl": round(unreal),
            "unrealized_pnl_pct": round((lp - pos["avg_cost"]) / pos["avg_cost"] * 100, 2),
        })

    save_json(DATA_DIR / "summary.json", {
        "last_updated": now_str(),
        "cash": round(portfolio["cash"]),
        "total_value": round(tv),
        "initial_cash": initial,
        "total_pnl": round(tv - initial),
        "total_pnl_pct": round((tv - initial) / initial * 100, 2),
        "realized_pnl": round(realized),
        "positions": positions_out,
        "trade_count": len(trades),
        "settings": {k: settings[k] for k in DEFAULT_SETTINGS},
    })


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
def run():
    print(f"===== 모의매매 v2 실행: {now_str()} =====")

    settings  = {**DEFAULT_SETTINGS, **load_json(SETTINGS_FILE, {})}
    portfolio = load_json(PORTFOLIO_FILE, None) or \
                {"cash": settings["initial_cash"], "positions": {}, "created_at": now_str()}
    trades    = load_json(TRADES_FILE, [])
    watchlist = load_json(WATCHLIST_FILE, [])
    last_prices = load_json(PRICE_FILE, {})   # {ticker: {price, ts}}

    open_krx = is_krx_open()
    open_nxt = is_nxt_open() and settings.get("use_nxt", True)

    if not open_krx and not open_nxt:
        print("[INFO] 장 마감 (정규장 + NXT 모두 비활성). 가격만 업데이트.")
        for ticker, pos in portfolio.get("positions", {}).items():
            pi = get_effective_price(ticker, settings)
            if pi["price"] > 0:
                pos["last_price"] = pi["price"]
        portfolio["last_updated"] = now_str()
        save_json(PORTFOLIO_FILE, portfolio)
        write_summary(portfolio, trades, settings)
        return

    print(f"[INFO] 정규장={open_krx} | NXT={open_nxt}")

    new_last_prices = dict(last_prices)

    for item in watchlist:
        ticker   = item.get("ticker", "").strip()
        name     = item.get("name", ticker)
        strategy = item.get("strategy", "rsi_ma")
        logic    = item.get("condition_logic", "OR").upper()

        if not ticker or not item.get("active", True):
            continue

        print(f"\n--- {name}({ticker}) | 전략={strategy} ---")

        # 가격 조회
        pi = get_effective_price(ticker, settings)
        price = pi["price"]
        if price == 0:
            print(f"  [WARN] 가격 조회 실패")
            continue

        prev_price  = last_prices.get(ticker, {}).get("price", 0)
        prev_close  = pi.get("prev_close", 0)
        is_nxt      = pi.get("is_nxt", False)

        # 직전 대비 변동률 계산
        chg_from_prev = (price - prev_price) / prev_price * 100 if prev_price else 0
        chg_from_day  = (price - prev_close) / prev_close * 100 if prev_close else 0
        print(f"  가격: {price:,}원 | 직전대비: {chg_from_prev:+.2f}% | 전일대비: {chg_from_day:+.2f}% | NXT={is_nxt}")

        # 가격 저장 (이번 실행분)
        new_last_prices[ticker] = {"price": price, "ts": now_str()}

        # 포지션 현재가 업데이트
        if ticker in portfolio["positions"]:
            portfolio["positions"][ticker]["last_price"] = price

        # ── 매도 판단 ──
        pos = portfolio["positions"].get(ticker)
        if pos and pos["qty"] > 0:
            avg_cost = pos["avg_cost"]
            pnl_pct  = (price - avg_cost) / avg_cost * 100

            sell_reason = None

            # 1) 손절/익절 (항상 최우선)
            if pnl_pct <= settings["stop_loss_pct"]:
                sell_reason = f"손절({pnl_pct:.2f}%)"
            elif pnl_pct >= settings["take_profit_pct"]:
                sell_reason = f"익절({pnl_pct:.2f}%)"

            # 2) 수동 매도 조건
            if not sell_reason and item.get("sell_conditions"):
                ok, matched = check_conditions(
                    item["sell_conditions"], logic, price, prev_price, prev_close)
                if ok:
                    sell_reason = "수동조건: " + " / ".join(matched)

            # 3) 자동 전략 매도
            if not sell_reason and strategy != "manual":
                ind = get_indicators(ticker, settings)
                ok, sig = auto_sell_signal(strategy, ind, settings)
                if ok:
                    sell_reason = f"[{strategy.upper()}] {sig}"

            if sell_reason:
                execute_sell(ticker, price, sell_reason, portfolio, trades, settings, is_nxt)
                continue

            print(f"  보유중 ({pnl_pct:+.2f}%) — 매도 조건 미충족")
            continue  # 이미 보유 중이면 매수 판단 불필요

        # ── 매수 판단 ──
        if portfolio["cash"] < 100_000:
            print(f"  현금 부족 ({portfolio['cash']:,.0f}원)")
            continue

        buy_reason = None

        # 1) 수동 매수 조건
        if item.get("buy_conditions"):
            ok, matched = check_conditions(
                item["buy_conditions"], logic, price, prev_price, prev_close)
            if ok:
                buy_reason = "수동조건: " + " / ".join(matched)

        # 2) 자동 전략 매수 (수동 조건이 없거나 수동이 아닐 때)
        if not buy_reason and strategy != "manual":
            ind = get_indicators(ticker, settings)
            ok, sig = auto_buy_signal(strategy, ind, settings)
            if ok:
                buy_reason = f"[{strategy.upper()}] {sig}"

        if buy_reason:
            execute_buy(ticker, price, buy_reason, portfolio, trades,
                        settings, is_nxt, name)
        else:
            print(f"  매수 조건 미충족")

    # 저장
    portfolio["last_updated"] = now_str()
    save_json(PORTFOLIO_FILE, portfolio)
    save_json(TRADES_FILE, trades)
    save_json(PRICE_FILE, new_last_prices)
    write_summary(portfolio, trades, settings)
    print("\n[INFO] 저장 완료")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        discord_notify(f"⚠️ 모의매매 오류\n```\n{traceback.format_exc()[-500:]}\n```")
        raise
