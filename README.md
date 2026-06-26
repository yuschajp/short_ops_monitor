# Short Ops Monitor

**Python-powered prime broker intelligence and short book surveillance for equity long/short funds.**

[![Dashboard](https://img.shields.io/badge/Live%20Dashboard-GitHub%20Pages-1B3A5C)](https://yuschajp.github.io/short_ops_monitor/)

---

## What This Does

Institutional equity L/S funds manage a short book across multiple prime brokers (Goldman, Morgan Stanley, JPMorgan). The operational overhead is significant: borrow rates change daily, hard-to-borrow status flips overnight, dividend record dates trigger recalls, and settlement fails carry regulatory deadlines under SEC Rule 204.

This tool automates the morning ops workflow across four surveillance modules:

### 1. Multi-PB Rate Comparison Engine
- Pulls borrow rates for every short position from all prime brokers simultaneously
- Identifies the cheapest borrow per name and flags optimization opportunities
- Estimates annualized dollar savings from switching to the best-rate broker
- **Direct P&L impact**: 50 bps of borrow cost savings on a $500M short book = $2.5M/year

### 2. HTB / ETB Overnight Monitor
- Detects any overnight ETB → HTB status flip
- Flags rate spikes of 25%+ between sessions
- Surfaces alerts by severity for the morning ops review

### 3. Recall Risk Tracker
- Cross-references short positions against upcoming dividend record dates and proxy vote events
- Urgency tiers: URGENT (≤3 days), WARNING (≤7 days), WATCH (≤14 days)
- Prevents surprise recalls — ops team and PMs have lead time to act

### 4. Settlement Fails & Rule 204 Tracker
- Monitors open settlement fails by age and sale type
- Flags Rule 204 breaches (short sale fails aged 3+ business days)
- Cross-references positions against the SEC Threshold Securities List

---

## Architecture

```
short_ops_monitor/
├── run.py                    # Main entry point
├── modules/
│   ├── simulate_pb_data.py   # Simulated PB feeds (replace with live API calls)
│   ├── db.py                 # SQLite data layer
│   ├── analytics.py          # Core calculation modules
│   └── dashboard.py          # HTML dashboard generator
├── data/
│   └── short_ops.db          # SQLite database (auto-generated)
└── docs/
    └── index.html            # GitHub Pages dashboard (auto-generated)
```

---

## Production API Integration

The simulation layer (`simulate_pb_data.py`) is designed to be swapped out for live feeds:

| Data Source | Provider | Integration Method |
|---|---|---|
| Borrow rates | Goldman Sachs, MS, JPMorgan | PB locate APIs / SFTP file feeds |
| Corporate actions | Bloomberg BPIPE, Refinitiv | API subscription |
| Short book positions | OMS (Advent Geneva, Enfusion) | API or end-of-day file |
| Settlement fails | DTCC / prime broker | Daily DTC file |
| Threshold securities | SEC.gov | Public daily download |

---

## Usage

```bash
git clone https://github.com/yuschajp/short_ops_monitor.git
cd short_ops_monitor
python run.py
# → Console summary + docs/index.html dashboard
```

No dependencies beyond the Python standard library (`sqlite3`, `datetime`, `os`, `random`).

---

## Skills Demonstrated

- **Multi-source data reconciliation** across prime broker feeds
- **Regulatory awareness**: SEC Rule 204, Threshold Securities List, FTD tracking
- **P&L-linked ops**: Borrow cost optimization with quantified savings estimates
- **SQL analytics**: SQLite for queryable, production-style data storage
- **Automation mindset**: Workflow designed to replace daily manual spreadsheet processes

---

*Built by [Joseph Yuschak](https://joseph-yuschak.notion.site) · [GitHub Portfolio](https://github.com/yuschajp)*
