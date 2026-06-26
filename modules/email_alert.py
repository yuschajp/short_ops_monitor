"""
modules/email_alert.py
Sends a daily morning ops alert email via Gmail SMTP.

Setup:
  export ALERT_FROM=you@gmail.com
  export ALERT_APP_PASS=xxxx-xxxx-xxxx-xxxx   # Gmail App Password
  export ALERT_TO=cfo@fund.com,pm@fund.com     # comma-separated recipients

Never hardcode credentials — always pull from environment variables.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

logger = logging.getLogger("EmailAlert")

NAVY  = "#1B3A5C"
RED   = "#C0392B"
AMBER = "#E67E22"
GREEN = "#27AE60"
GOLD  = "#C9A84C"
GRAY  = "#6C757D"


def urgency_color(urgency):
    return {"URGENT": RED, "WARNING": AMBER, "WATCH": GOLD}.get(urgency, GRAY)


def build_html(as_of, pb_comp, htb_alerts, carry, total_carry, recalls, fails):
    """Build the HTML email body — concise morning brief format."""

    # ── KPI row ──────────────────────────────────────────────────────────────
    total_savings  = sum(r["est_annual_savings_usd"] for r in pb_comp)
    rule204_count  = sum(1 for f in fails if f["rule_204_breach"])
    urgent_recalls = sum(1 for r in recalls if r["urgency"] == "URGENT")
    htb_count      = len(htb_alerts)

    def kpi(label, value, color=NAVY):
        return f"""
        <td style="text-align:center;padding:12px 20px;border-right:1px solid #e0e4ea">
          <div style="font-size:22px;font-weight:800;color:{color}">{value}</div>
          <div style="font-size:10px;color:{GRAY};text-transform:uppercase;letter-spacing:0.5px;margin-top:2px">{label}</div>
        </td>"""

    kpi_row = f"""
    <table width="100%" style="border:1px solid #e0e4ea;border-radius:6px;border-collapse:collapse;margin-bottom:24px">
      <tr>
        {kpi("Est. PB Savings/yr", f"${total_savings:,.0f}", GOLD)}
        {kpi("HTB Alerts", htb_count, RED if htb_count > 0 else NAVY)}
        {kpi("Urgent Recalls", urgent_recalls, RED if urgent_recalls > 0 else NAVY)}
        {kpi("Rule 204 Breaches", rule204_count, RED if rule204_count > 0 else NAVY)}
        {kpi("Total Carry Cost/yr", f"${total_carry:,.0f}", NAVY)}
      </tr>
    </table>"""

    # ── HTB Alerts section ────────────────────────────────────────────────────
    if htb_alerts:
        htb_rows = ""
        for a in htb_alerts[:8]:
            flags = []
            if a["status_flip"]: flags.append(f'<span style="background:{RED};color:#fff;padding:1px 6px;border-radius:3px;font-size:10px">ETB→HTB</span>')
            if a["rate_spike"]:  flags.append(f'<span style="background:{AMBER};color:#fff;padding:1px 6px;border-radius:3px;font-size:10px">SPIKE</span>')
            htb_rows += f"""
            <tr style="border-bottom:1px solid #f0f2f5">
              <td style="padding:8px 12px;font-weight:700">{a['ticker']}</td>
              <td style="padding:8px 12px;color:{GRAY}">{a['prime_broker']}</td>
              <td style="padding:8px 12px">{a['prior_rate']:.2f}% → <strong style="color:{RED}">{a['current_rate']:.2f}%</strong></td>
              <td style="padding:8px 12px;color:{RED};font-weight:700">+{a['change_bps']} bps</td>
              <td style="padding:8px 12px">{'  '.join(flags)}</td>
            </tr>"""
        htb_section = f"""
        <h3 style="color:{NAVY};font-size:13px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 10px">
          ⚠ HTB / ETB Alerts ({len(htb_alerts)})
        </h3>
        <table width="100%" style="border-collapse:collapse;font-size:13px;margin-bottom:24px">
          <thead><tr style="background:{NAVY};color:#fff">
            <th style="padding:8px 12px;text-align:left;font-size:11px">Ticker</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px">Prime Broker</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px">Rate Change</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px">Delta</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px">Flags</th>
          </tr></thead>
          <tbody>{htb_rows}</tbody>
        </table>"""
    else:
        htb_section = f"""
        <div style="background:#f0faf4;border-left:4px solid {GREEN};padding:12px 16px;margin-bottom:24px;font-size:13px">
          ✓ <strong>No HTB alerts</strong> — all positions stable overnight
        </div>"""

    # ── Recall Risk section ───────────────────────────────────────────────────
    recall_rows = ""
    for r in recalls:
        color = urgency_color(r["urgency"])
        recall_rows += f"""
        <tr style="border-bottom:1px solid #f0f2f5">
          <td style="padding:8px 12px;font-weight:700">{r['ticker']}</td>
          <td style="padding:8px 12px;color:{GRAY}">{r['event_type']}</td>
          <td style="padding:8px 12px">{r['record_date']}</td>
          <td style="padding:8px 12px;font-weight:700;color:{color}">{r['days_until_record']}d</td>
          <td style="padding:8px 12px">
            <span style="background:{color};color:#fff;padding:2px 8px;border-radius:3px;font-size:10px;font-weight:700">{r['urgency']}</span>
          </td>
          <td style="padding:8px 12px;color:{GRAY}">{r['shares_at_risk']:,}</td>
        </tr>"""

    recall_section = f"""
    <h3 style="color:{NAVY};font-size:13px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 10px">
      📅 Recall Risk — Upcoming Record Dates
    </h3>
    <table width="100%" style="border-collapse:collapse;font-size:13px;margin-bottom:24px">
      <thead><tr style="background:{NAVY};color:#fff">
        <th style="padding:8px 12px;text-align:left;font-size:11px">Ticker</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Event</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Record Date</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Days Until</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Urgency</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Shares at Risk</th>
      </tr></thead>
      <tbody>{recall_rows}</tbody>
    </table>"""

    # ── Fails section ─────────────────────────────────────────────────────────
    fails_rows = ""
    for f in fails:
        breach = f'<span style="background:{RED};color:#fff;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:700">⚠ RULE 204</span>' if f["rule_204_breach"] else "—"
        age_color = RED if f["age_days"] >= 3 else (AMBER if f["age_days"] >= 2 else GRAY)
        fails_rows += f"""
        <tr style="border-bottom:1px solid #f0f2f5">
          <td style="padding:8px 12px;font-weight:700">{f['ticker']}</td>
          <td style="padding:8px 12px;color:{GRAY}">{f['sale_type']}</td>
          <td style="padding:8px 12px;font-weight:700;color:{age_color}">{f['age_days']}d</td>
          <td style="padding:8px 12px">{f['shares_failed']:,}</td>
          <td style="padding:8px 12px">{breach}</td>
        </tr>"""

    fails_section = f"""
    <h3 style="color:{NAVY};font-size:13px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 10px">
      📋 Settlement Fails & Rule 204
    </h3>
    <table width="100%" style="border-collapse:collapse;font-size:13px;margin-bottom:24px">
      <thead><tr style="background:{NAVY};color:#fff">
        <th style="padding:8px 12px;text-align:left;font-size:11px">Ticker</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Type</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Age</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Shares</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Status</th>
      </tr></thead>
      <tbody>{fails_rows}</tbody>
    </table>"""

    # ── Top PB savings ────────────────────────────────────────────────────────
    pb_rows = ""
    for r in pb_comp[:5]:
        pb_rows += f"""
        <tr style="border-bottom:1px solid #f0f2f5">
          <td style="padding:8px 12px;font-weight:700">{r['ticker']}</td>
          <td style="padding:8px 12px;color:{GREEN}">{r['best_pb']} ({r['best_rate_pct']:.2f}%)</td>
          <td style="padding:8px 12px;color:{RED}">{r['worst_pb']} ({r['worst_rate_pct']:.2f}%)</td>
          <td style="padding:8px 12px;font-weight:700;color:{NAVY}">{r['spread_bps']} bps</td>
          <td style="padding:8px 12px;font-weight:700;color:{GOLD}">${r['est_annual_savings_usd']:,.0f}</td>
        </tr>"""

    pb_section = f"""
    <h3 style="color:{NAVY};font-size:13px;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 10px">
      💰 Top PB Rate Optimization Opportunities
    </h3>
    <table width="100%" style="border-collapse:collapse;font-size:13px;margin-bottom:24px">
      <thead><tr style="background:{NAVY};color:#fff">
        <th style="padding:8px 12px;text-align:left;font-size:11px">Ticker</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Best PB</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Worst PB</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Spread</th>
        <th style="padding:8px 12px;text-align:left;font-size:11px">Est. Annual Savings</th>
      </tr></thead>
      <tbody>{pb_rows}</tbody>
    </table>"""

    # ── Full email ────────────────────────────────────────────────────────────
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <div style="max-width:680px;margin:24px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08)">

    <!-- Header -->
    <div style="background:{NAVY};padding:24px 28px">
      <div style="color:#fff;font-size:18px;font-weight:700">Short Ops Morning Brief</div>
      <div style="color:rgba(255,255,255,0.6);font-size:12px;margin-top:4px">{as_of} &nbsp;·&nbsp; Generated by Short Ops Monitor</div>
    </div>

    <!-- Body -->
    <div style="padding:24px 28px">
      {kpi_row}
      {htb_section}
      {recall_section}
      {fails_section}
      {pb_section}
    </div>

    <!-- Footer -->
    <div style="background:#f8f9fc;padding:14px 28px;border-top:1px solid #e0e4ea;font-size:11px;color:{GRAY}">
      Short Ops Monitor &nbsp;·&nbsp;
      <a href="https://yuschajp.github.io/short_ops_monitor/" style="color:{NAVY}">Live Dashboard</a> &nbsp;·&nbsp;
      <a href="https://github.com/yuschajp/short_ops_monitor" style="color:{NAVY}">GitHub</a>
    </div>
  </div>
</body>
</html>"""


def send_alert(as_of, pb_comp, htb_alerts, carry, total_carry, recalls, fails):
    """
    Send the morning brief email via Gmail SMTP.
    Reads credentials from environment variables — never hardcoded.
    """
    from_addr  = os.getenv("ALERT_FROM")
    app_pass   = os.getenv("ALERT_APP_PASS")
    to_raw     = os.getenv("ALERT_TO", from_addr)

    if not from_addr or not app_pass:
        logger.warning("ALERT_FROM or ALERT_APP_PASS not set — skipping email.")
        return False

    to_addrs = [t.strip() for t in to_raw.split(",")]

    # Subject line escalates if there are urgent items
    rule204  = sum(1 for f in fails if f["rule_204_breach"])
    urgent   = sum(1 for r in recalls if r["urgency"] == "URGENT")
    prefix   = "🔴 ACTION REQUIRED" if (rule204 > 0 or urgent > 0) else "📊 Daily Brief"
    subject  = f"{prefix} | Short Ops Monitor | {as_of}"

    html_body = build_html(as_of, pb_comp, htb_alerts, carry, total_carry, recalls, fails)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = ", ".join(to_addrs)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_addr, app_pass)
            server.sendmail(from_addr, to_addrs, msg.as_string())
        logger.info(f"  Email sent → {to_addrs}")
        return True
    except Exception as e:
        logger.error(f"  Email failed: {e}")
        return False
