"""
analytics.py
Core analytics: PB rate comparison, HTB monitor, cost of carry, recall risk, fails tracker.
"""

from modules.db import query

# ── 1. MULTI-PB RATE COMPARISON ─────────────────────────────────────────────

def pb_rate_comparison(as_of_date: str):
    """
    For each ticker in the short book, compare borrow rates across all PBs.
    Returns best PB, worst PB, spread in bps, and estimated annual savings.
    """
    rows = query("""
        SELECT ticker, sector, shares_short, prime_broker, borrow_rate_pct
        FROM borrow_rates
        WHERE report_date = ?
    """, (as_of_date,))

    tickers = {}
    for r in rows:
        t = r["ticker"]
        if t not in tickers:
            tickers[t] = {
                "sector": r["sector"],
                "shares_short": r["shares_short"],
                "rates": {}
            }
        tickers[t]["rates"][r["prime_broker"]] = r["borrow_rate_pct"]

    results = []
    for ticker, data in tickers.items():
        rates = data["rates"]
        if not rates:
            continue
        best_pb   = min(rates, key=rates.get)
        worst_pb  = max(rates, key=rates.get)
        best_rate = rates[best_pb]
        worst_rate = rates[worst_pb]
        spread_bps = round((worst_rate - best_rate) * 100, 1)

        # Annual savings estimate: spread * shares * assumed $20 avg price / 100
        # Realistic placeholder — real calc needs market price feed
        est_annual_savings = round(spread_bps / 100 * data["shares_short"] * 20 / 100, 0)

        results.append({
            "ticker": ticker,
            "sector": data["sector"],
            "shares_short": data["shares_short"],
            "best_pb": best_pb,
            "best_rate_pct": best_rate,
            "worst_pb": worst_pb,
            "worst_rate_pct": worst_rate,
            "spread_bps": spread_bps,
            "est_annual_savings_usd": est_annual_savings,
            "rates": rates,
        })

    results.sort(key=lambda x: x["spread_bps"], reverse=True)
    return results

# ── 2. HTB / ETB MONITOR ────────────────────────────────────────────────────

def htb_etb_monitor(as_of_date: str, prior_date: str):
    """
    Flags any overnight ETB → HTB flips and rate spikes (25%+).
    """
    today = query("""
        SELECT ticker, prime_broker, borrow_rate_pct, status
        FROM borrow_rates WHERE report_date = ?
    """, (as_of_date,))

    prior = query("""
        SELECT ticker, prime_broker, borrow_rate_pct, status
        FROM borrow_rates WHERE report_date = ?
    """, (prior_date,))

    prior_map = {(r["ticker"], r["prime_broker"]): r for r in prior}

    alerts = []
    for r in today:
        key = (r["ticker"], r["prime_broker"])
        p = prior_map.get(key)
        if not p:
            continue

        status_flip = p["status"] == "ETB" and r["status"] == "HTB"
        rate_spike  = r["borrow_rate_pct"] > p["borrow_rate_pct"] * 1.25

        if status_flip or rate_spike:
            alerts.append({
                "ticker": r["ticker"],
                "prime_broker": r["prime_broker"],
                "prior_rate": p["borrow_rate_pct"],
                "current_rate": r["borrow_rate_pct"],
                "prior_status": p["status"],
                "current_status": r["status"],
                "status_flip": status_flip,
                "rate_spike": rate_spike,
                "change_bps": round((r["borrow_rate_pct"] - p["borrow_rate_pct"]) * 100, 1),
            })

    alerts.sort(key=lambda x: x["change_bps"], reverse=True)
    return alerts

# ── 3. COST OF CARRY ────────────────────────────────────────────────────────

def cost_of_carry(as_of_date: str, assumed_price: float = 20.0):
    """
    Computes estimated annualized borrow cost per position using best available PB rate.
    """
    rows = query("""
        SELECT ticker, sector, shares_short, MIN(borrow_rate_pct) as best_rate
        FROM borrow_rates
        WHERE report_date = ?
        GROUP BY ticker, sector, shares_short
    """, (as_of_date,))

    results = []
    total_cost = 0
    for r in rows:
        ann_cost = round(r["best_rate"] / 100 * r["shares_short"] * assumed_price, 0)
        total_cost += ann_cost
        results.append({
            "ticker": r["ticker"],
            "sector": r["sector"],
            "shares_short": r["shares_short"],
            "best_rate_pct": r["best_rate"],
            "ann_borrow_cost_usd": ann_cost,
        })

    results.sort(key=lambda x: x["ann_borrow_cost_usd"], reverse=True)
    return results, round(total_cost, 0)

# ── 4. RECALL RISK ──────────────────────────────────────────────────────────

def recall_risk_report():
    return query("""
        SELECT ticker, event_type, record_date, days_until_record, urgency, shares_at_risk
        FROM recall_risk
        ORDER BY days_until_record ASC
    """)

# ── 5. FAILS & RULE 204 ─────────────────────────────────────────────────────

def fails_report():
    fails = query("""
        SELECT f.ticker, f.cusip, f.fail_date, f.shares_failed, f.sale_type,
               f.age_days, f.rule_204_breach,
               t.days_on_list
        FROM settlement_fails f
        LEFT JOIN threshold_securities t ON f.cusip = t.cusip
        ORDER BY f.age_days DESC
    """)
    return fails

def threshold_report():
    return query("""
        SELECT ticker, cusip, days_on_list
        FROM threshold_securities
        ORDER BY days_on_list DESC
    """)

# ── 6. HISTORICAL RATE TREND ─────────────────────────────────────────────────

def borrow_rate_history(tickers: list = None, days: int = 30):
    """
    Returns daily best borrow rate (across all PBs) per ticker for the past N days.
    Used to power the trend chart on the dashboard.
    """
    if tickers:
        placeholders = ",".join("?" * len(tickers))
        rows = query(f"""
            SELECT report_date, ticker, MIN(borrow_rate_pct) as best_rate
            FROM borrow_rates
            WHERE ticker IN ({placeholders})
            GROUP BY report_date, ticker
            ORDER BY report_date ASC
        """, tuple(tickers))
    else:
        rows = query("""
            SELECT report_date, ticker, MIN(borrow_rate_pct) as best_rate
            FROM borrow_rates
            GROUP BY report_date, ticker
            ORDER BY report_date ASC
        """)
    return rows
