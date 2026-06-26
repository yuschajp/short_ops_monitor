"""
run.py
Main entry point. Orchestrates data load → analytics → dashboard.

Modes:
  python run.py           → uses connector orchestrator (sim mode by default)
  python run.py --sim     → forces raw simulation (bypasses connectors entirely)
"""

import sys
import os
import logging
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("run")

from modules.analytics import (
    pb_rate_comparison, htb_etb_monitor, cost_of_carry,
    recall_risk_report, fails_report, threshold_report
)
from modules.dashboard import generate_dashboard

def get_last_business_day(d):
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

def main():
    today     = date.today()
    prior     = get_last_business_day(today)
    as_of     = today.isoformat()
    prior_str = prior.isoformat()

    force_sim = "--sim" in sys.argv

    print(f"\nShort Ops Monitor | {as_of}")
    print("=" * 52)

    if force_sim:
        # Raw simulation — no connectors
        from modules.simulate_pb_data import (
            generate_pb_rates, generate_recalls, generate_fails, generate_threshold_list
        )
        from modules.db import init_db, insert_borrow_rates, insert_recalls, insert_fails, insert_threshold
        print("Mode: SIMULATION (--sim flag)\n")
        init_db()
        insert_borrow_rates(generate_pb_rates(today, days_back=30))
        insert_recalls(generate_recalls(today))
        insert_fails(generate_fails(today))
        insert_threshold(generate_threshold_list())
    else:
        # Connector orchestrator (sim mode inside connectors until DW creds set)
        from connectors.orchestrator import run_all
        print("Mode: CONNECTOR ORCHESTRATOR (sim fallback active)\n")
        counts = run_all()
        print(f"\n  Loaded: {counts}\n")

    # ── Analytics ──────────────────────────────────────────────────────────
    pb_comp        = pb_rate_comparison(as_of)
    htb_alerts     = htb_etb_monitor(as_of, prior_str)
    carry, total   = cost_of_carry(as_of)
    recalls        = recall_risk_report()
    fails          = fails_report()
    threshold      = threshold_report()

    # ── Console summary ────────────────────────────────────────────────────
    print(f"PB RATE COMPARISON — Top 5 Savings Opportunities:")
    for r in pb_comp[:5]:
        print(f"  {r['ticker']:6} | Best: {r['best_pb']:15} {r['best_rate_pct']:.2f}% | "
              f"Spread: {r['spread_bps']} bps | Est. Savings: ${r['est_annual_savings_usd']:,.0f}/yr")

    print(f"\nHTB/ETB ALERTS ({len(htb_alerts)} flagged):")
    for a in htb_alerts[:5]:
        print(f"  {a['ticker']:6} | {a['prime_broker']:15} | "
              f"{a['prior_status']} → {a['current_status']} | +{a['change_bps']} bps")

    print(f"\nCOST OF CARRY — Total Est. Annual Borrow Cost: ${total:,.0f}")
    for r in carry[:5]:
        print(f"  {r['ticker']:6} | {r['best_rate_pct']:.2f}% | ${r['ann_borrow_cost_usd']:,.0f}/yr")

    print(f"\nRECALL RISK ({len(recalls)} positions):")
    for r in recalls:
        print(f"  [{r['urgency']:7}] {r['ticker']:6} | {r['event_type']:20} | "
              f"Record: {r['record_date']} ({r['days_until_record']}d)")

    print(f"\nSETTLEMENT FAILS ({len(fails)}):")
    for f in fails:
        breach = "⚠ RULE 204 BREACH" if f["rule_204_breach"] else ""
        print(f"  {f['ticker']:6} | {f['sale_type']} | Age: {f['age_days']}d | "
              f"{f['shares_failed']:,} shares {breach}")

    # ── Dashboard ──────────────────────────────────────────────────────────
    print("\nGenerating dashboard...")
    generate_dashboard(as_of, pb_comp, htb_alerts, carry, total, recalls, fails, threshold)
    print("  Dashboard written to docs/index.html\n")

if __name__ == "__main__":
    main()
