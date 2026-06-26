"""
dashboard.py
Generates the GitHub Pages HTML dashboard — navy branding, consistent with portfolio style.
"""

import os

NAVY  = "#1B3A5C"
GOLD  = "#C9A84C"
WHITE = "#FFFFFF"
LIGHT = "#F4F6F9"
RED   = "#C0392B"
AMBER = "#E67E22"
GREEN = "#27AE60"
GRAY  = "#6C757D"

def urgency_color(urgency):
    return {"URGENT": RED, "WARNING": AMBER, "WATCH": GOLD}.get(urgency, GRAY)

def status_badge(status):
    color = RED if status == "HTB" else GREEN
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{status}</span>'

def generate_dashboard(as_of, pb_comp, htb_alerts, carry, total_carry, recalls, fails, threshold):
    os.makedirs(os.path.join(os.path.dirname(__file__), "docs"), exist_ok=True)

    # ── PB Comparison table ──
    pb_rows = ""
    for r in pb_comp:
        rates_str = " | ".join(f"{pb}: {rate:.2f}%" for pb, rate in r["rates"].items())
        savings_color = RED if r["spread_bps"] >= 50 else (AMBER if r["spread_bps"] >= 20 else GRAY)
        pb_rows += f"""
        <tr>
          <td><strong>{r['ticker']}</strong></td>
          <td>{r['sector']}</td>
          <td>{r['shares_short']:,}</td>
          <td style="color:{GREEN};font-weight:700">{r['best_pb']}<br><small>{r['best_rate_pct']:.2f}%</small></td>
          <td style="color:{RED}">{r['worst_pb']}<br><small>{r['worst_rate_pct']:.2f}%</small></td>
          <td style="color:{savings_color};font-weight:700">{r['spread_bps']} bps</td>
          <td style="color:{savings_color};font-weight:700">${r['est_annual_savings_usd']:,.0f}</td>
        </tr>"""

    # ── HTB Alerts ──
    htb_rows = ""
    if htb_alerts:
        for a in htb_alerts:
            flags = []
            if a["status_flip"]: flags.append(f'<span style="background:{RED};color:#fff;padding:2px 6px;border-radius:3px;font-size:10px">ETB→HTB</span>')
            if a["rate_spike"]:  flags.append(f'<span style="background:{AMBER};color:#fff;padding:2px 6px;border-radius:3px;font-size:10px">RATE SPIKE</span>')
            htb_rows += f"""
            <tr>
              <td><strong>{a['ticker']}</strong></td>
              <td>{a['prime_broker']}</td>
              <td>{a['prior_rate']:.2f}%</td>
              <td style="color:{RED};font-weight:700">{a['current_rate']:.2f}%</td>
              <td style="color:{RED};font-weight:700">+{a['change_bps']} bps</td>
              <td>{' '.join(flags)}</td>
            </tr>"""
    else:
        htb_rows = '<tr><td colspan="6" style="text-align:center;color:#6C757D;padding:20px">No alerts — all positions stable</td></tr>'

    # ── Cost of Carry ──
    carry_rows = ""
    for r in carry:
        bar_width = min(100, int(r['ann_borrow_cost_usd'] / (total_carry / 100 + 1)))
        carry_rows += f"""
        <tr>
          <td><strong>{r['ticker']}</strong></td>
          <td>{r['sector']}</td>
          <td>{r['shares_short']:,}</td>
          <td>{r['best_rate_pct']:.2f}%</td>
          <td>
            <div style="display:flex;align-items:center;gap:8px">
              <div style="background:{NAVY};height:8px;width:{bar_width}%;border-radius:4px;min-width:4px"></div>
              <span style="font-weight:700">${r['ann_borrow_cost_usd']:,.0f}</span>
            </div>
          </td>
        </tr>"""

    # ── Recall Risk ──
    recall_rows = ""
    for r in recalls:
        color = urgency_color(r["urgency"])
        recall_rows += f"""
        <tr>
          <td><strong>{r['ticker']}</strong></td>
          <td>{r['event_type']}</td>
          <td>{r['record_date']}</td>
          <td style="font-weight:700;color:{color}">{r['days_until_record']}d</td>
          <td><span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{r['urgency']}</span></td>
          <td>{r['shares_at_risk']:,}</td>
        </tr>"""

    # ── Fails ──
    fails_rows = ""
    for f in fails:
        breach_badge = f'<span style="background:{RED};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">⚠ RULE 204</span>' if f["rule_204_breach"] else '<span style="color:{GRAY}">—</span>'
        on_list = f'<span style="color:{RED}">Yes ({f["days_on_list"]}d)</span>' if f.get("days_on_list") else "No"
        fails_rows += f"""
        <tr>
          <td><strong>{f['ticker']}</strong></td>
          <td>{f['sale_type']}</td>
          <td>{f['fail_date']}</td>
          <td style="font-weight:700;color:{RED if f['age_days'] >= 3 else AMBER}">{f['age_days']}d</td>
          <td>{f['shares_failed']:,}</td>
          <td>{breach_badge}</td>
          <td>{on_list}</td>
        </tr>"""

    # ── KPI strip ──
    total_savings = sum(r["est_annual_savings_usd"] for r in pb_comp)
    htb_count = sum(1 for r in pb_comp for pb, rate in r["rates"].items() if rate > 1.0)
    rule204_count = sum(1 for f in fails if f["rule_204_breach"])
    urgent_recalls = sum(1 for r in recalls if r["urgency"] == "URGENT")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Short Ops Monitor | Joseph Yuschak</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: {LIGHT}; color: #222; }}
  header {{ background: {NAVY}; color: {WHITE}; padding: 28px 40px; }}
  header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }}
  header p {{ font-size: 13px; opacity: 0.7; margin-top: 4px; }}
  .kpi-strip {{ display: flex; gap: 16px; padding: 24px 40px; flex-wrap: wrap; }}
  .kpi {{ background: {WHITE}; border-radius: 8px; padding: 18px 24px; flex: 1; min-width: 160px;
           border-top: 4px solid {NAVY}; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  .kpi .val {{ font-size: 28px; font-weight: 800; color: {NAVY}; }}
  .kpi .lbl {{ font-size: 12px; color: {GRAY}; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .kpi.alert .val {{ color: {RED}; }}
  .kpi.gold  .val {{ color: {GOLD}; }}
  .section {{ margin: 0 40px 32px; }}
  .section h2 {{ font-size: 15px; font-weight: 700; color: {NAVY}; border-bottom: 2px solid {NAVY};
                 padding-bottom: 8px; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .card {{ background: {WHITE}; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); overflow: hidden; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: {NAVY}; color: {WHITE}; padding: 10px 14px; text-align: left; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #eef0f3; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8f9fc; }}
  .note {{ font-size: 11px; color: {GRAY}; margin-top: 8px; }}
  footer {{ text-align: center; padding: 24px; font-size: 12px; color: {GRAY}; }}
  footer a {{ color: {NAVY}; text-decoration: none; }}
</style>
</head>
<body>

<header>
  <h1>Short Ops Monitor</h1>
  <p>Prime Broker Rate Intelligence · HTB/ETB Surveillance · Recall Risk · Fails Tracker &nbsp;|&nbsp; As of {as_of} &nbsp;|&nbsp; <a href="https://github.com/yuschajp" style="color:{GOLD}">github.com/yuschajp</a></p>
</header>

<!-- KPI Strip -->
<div class="kpi-strip">
  <div class="kpi gold">
    <div class="val">${total_savings:,.0f}</div>
    <div class="lbl">Est. Annual PB Savings</div>
  </div>
  <div class="kpi {'alert' if htb_count > 0 else ''}">
    <div class="val">{htb_count}</div>
    <div class="lbl">HTB Rate Occurrences</div>
  </div>
  <div class="kpi {'alert' if urgent_recalls > 0 else ''}">
    <div class="val">{urgent_recalls}</div>
    <div class="lbl">Urgent Recall Alerts</div>
  </div>
  <div class="kpi {'alert' if rule204_count > 0 else ''}">
    <div class="val">{rule204_count}</div>
    <div class="lbl">Rule 204 Breaches</div>
  </div>
  <div class="kpi">
    <div class="val">${total_carry:,.0f}</div>
    <div class="lbl">Total Annual Carry Cost</div>
  </div>
</div>

<!-- PB Rate Comparison -->
<div class="section">
  <h2>Multi-PB Rate Comparison — Borrow Optimization</h2>
  <div class="card">
    <table>
      <thead><tr>
        <th>Ticker</th><th>Sector</th><th>Shares Short</th>
        <th>Best PB / Rate</th><th>Worst PB / Rate</th>
        <th>Spread (bps)</th><th>Est. Annual Savings</th>
      </tr></thead>
      <tbody>{pb_rows}</tbody>
    </table>
  </div>
  <p class="note">* Savings estimate uses $20 assumed avg price. Real implementation uses live price feed from Bloomberg/Refinitiv.</p>
</div>

<!-- HTB Alerts -->
<div class="section">
  <h2>HTB / ETB Overnight Alerts</h2>
  <div class="card">
    <table>
      <thead><tr>
        <th>Ticker</th><th>Prime Broker</th><th>Prior Rate</th>
        <th>Current Rate</th><th>Change</th><th>Flags</th>
      </tr></thead>
      <tbody>{htb_rows}</tbody>
    </table>
  </div>
</div>

<!-- Cost of Carry -->
<div class="section">
  <h2>Cost of Carry — Short Book Borrow Drag</h2>
  <div class="card">
    <table>
      <thead><tr>
        <th>Ticker</th><th>Sector</th><th>Shares Short</th>
        <th>Best Rate</th><th>Est. Annual Borrow Cost</th>
      </tr></thead>
      <tbody>{carry_rows}</tbody>
    </table>
  </div>
</div>

<!-- Recall Risk -->
<div class="section">
  <h2>Recall Risk — Upcoming Record Dates</h2>
  <div class="card">
    <table>
      <thead><tr>
        <th>Ticker</th><th>Event</th><th>Record Date</th>
        <th>Days Until</th><th>Urgency</th><th>Shares at Risk</th>
      </tr></thead>
      <tbody>{recall_rows}</tbody>
    </table>
  </div>
</div>

<!-- Fails & Rule 204 -->
<div class="section">
  <h2>Settlement Fails & Rule 204 Tracker</h2>
  <div class="card">
    <table>
      <thead><tr>
        <th>Ticker</th><th>Sale Type</th><th>Fail Date</th>
        <th>Age</th><th>Shares Failed</th><th>Rule 204</th><th>Threshold List</th>
      </tr></thead>
      <tbody>{fails_rows}</tbody>
    </table>
  </div>
  <p class="note">* Rule 204 breach = short sale fail aged 3+ business days. Threshold list = SEC persistent FTD registry.</p>
</div>

<footer>
  Built by <a href="https://joseph-yuschak.notion.site">Joseph Yuschak</a> &nbsp;·&nbsp;
  <a href="https://github.com/yuschajp/short_ops_monitor">GitHub</a> &nbsp;·&nbsp;
  Simulated PB data — production implementation uses live API feeds from prime brokers
</footer>

</body>
</html>"""

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_path = os.path.join(repo_root, "docs", "index.html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(html)
