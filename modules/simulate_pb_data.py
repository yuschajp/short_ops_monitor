"""
simulate_pb_data.py
Simulates prime broker borrow rate feeds for 3 brokers across a short book.
In production, these would be API calls or SFTP file ingests from GS, MS, JPM.
"""

import random
import sqlite3
from datetime import date, timedelta

PRIME_BROKERS = ["Goldman", "Morgan Stanley", "JPMorgan"]

SHORT_BOOK = [
    {"cusip": "037833100", "ticker": "AAPL",  "sector": "Technology",    "shares_short": 50000},
    {"cusip": "594918104", "ticker": "MSFT",  "sector": "Technology",    "shares_short": 30000},
    {"cusip": "023135106", "ticker": "AMZN",  "sector": "Consumer",      "shares_short": 20000},
    {"cusip": "30303M102", "ticker": "META",  "sector": "Technology",    "shares_short": 45000},
    {"cusip": "88160R101", "ticker": "TSLA",  "sector": "Automotive",    "shares_short": 60000},
    {"cusip": "067901108", "ticker": "BA",    "sector": "Industrials",   "shares_short": 25000},
    {"cusip": "126650100", "ticker": "CVS",   "sector": "Healthcare",    "shares_short": 40000},
    {"cusip": "191216100", "ticker": "KO",    "sector": "Consumer",      "shares_short": 55000},
    {"cusip": "742718109", "ticker": "PFE",   "sector": "Healthcare",    "shares_short": 35000},
    {"cusip": "857477103", "ticker": "SPCE",  "sector": "Aerospace",     "shares_short": 80000},
    {"cusip": "00165C104", "ticker": "AMC",   "sector": "Entertainment", "shares_short": 120000},
    {"cusip": "64110W102", "ticker": "NKLA",  "sector": "Automotive",    "shares_short": 95000},
    {"cusip": "G8878P103", "ticker": "TPVG",  "sector": "Financials",    "shares_short": 28000},
    {"cusip": "92826C839", "ticker": "VIAV",  "sector": "Technology",    "shares_short": 33000},
    {"cusip": "45781M879", "ticker": "INFA",  "sector": "Technology",    "shares_short": 18000},
]

# Simulate realistic borrow rates by ticker characteristic
def base_rate(ticker):
    htb_names = {"TSLA": 2.5, "AMC": 18.0, "NKLA": 22.0, "SPCE": 12.0, "BA": 1.8}
    return htb_names.get(ticker, round(random.uniform(0.25, 1.5), 2))

def generate_pb_rates(as_of_date: date, days_back: int = 30):
    """Generate historical + today's borrow rates for all PBs."""
    records = []
    for d in range(days_back, -1, -1):
        report_date = as_of_date - timedelta(days=d)
        if report_date.weekday() >= 5:
            continue  # skip weekends
        for pos in SHORT_BOOK:
            base = base_rate(pos["ticker"])
            for pb in PRIME_BROKERS:
                # Each PB quotes slightly differently
                variance = random.uniform(-0.15, 0.25)
                rate = round(max(0.10, base + variance), 2)
                status = "HTB" if rate > 1.0 else "ETB"
                records.append({
                    "report_date": report_date.isoformat(),
                    "cusip": pos["cusip"],
                    "ticker": pos["ticker"],
                    "sector": pos["sector"],
                    "shares_short": pos["shares_short"],
                    "prime_broker": pb,
                    "borrow_rate_pct": rate,
                    "status": status,
                })
    return records

def generate_recalls(as_of_date: date):
    """Simulate upcoming dividend record dates creating recall risk."""
    recalls = []
    recall_candidates = [
        {"ticker": "AAPL",  "cusip": "037833100", "record_date": (as_of_date + timedelta(days=5)).isoformat(),  "event": "Quarterly Dividend"},
        {"ticker": "KO",    "cusip": "191216100", "record_date": (as_of_date + timedelta(days=3)).isoformat(),  "event": "Quarterly Dividend"},
        {"ticker": "PFE",   "cusip": "742718109", "record_date": (as_of_date + timedelta(days=8)).isoformat(),  "event": "Quarterly Dividend"},
        {"ticker": "META",  "cusip": "30303M102", "record_date": (as_of_date + timedelta(days=12)).isoformat(), "event": "Proxy Vote"},
        {"ticker": "MSFT",  "cusip": "594918104", "record_date": (as_of_date + timedelta(days=2)).isoformat(),  "event": "Quarterly Dividend"},
    ]
    for r in recall_candidates:
        days_until = (date.fromisoformat(r["record_date"]) - as_of_date).days
        urgency = "URGENT" if days_until <= 3 else ("WARNING" if days_until <= 7 else "WATCH")
        pos = next((p for p in SHORT_BOOK if p["ticker"] == r["ticker"]), None)
        recalls.append({
            "ticker": r["ticker"],
            "cusip": r["cusip"],
            "event_type": r["event"],
            "record_date": r["record_date"],
            "days_until_record": days_until,
            "urgency": urgency,
            "shares_at_risk": pos["shares_short"] if pos else 0,
        })
    return recalls

def generate_fails(as_of_date: date):
    """Simulate open settlement fails."""
    fails = [
        {"ticker": "AMC",  "cusip": "00165C104", "fail_date": (as_of_date - timedelta(days=3)).isoformat(), "shares_failed": 15000, "sale_type": "SHORT"},
        {"ticker": "NKLA", "cusip": "64110W102", "fail_date": (as_of_date - timedelta(days=1)).isoformat(), "shares_failed": 8000,  "sale_type": "SHORT"},
        {"ticker": "SPCE", "cusip": "857477103", "fail_date": (as_of_date - timedelta(days=2)).isoformat(), "shares_failed": 5000,  "sale_type": "SHORT"},
        {"ticker": "BA",   "cusip": "067901108", "fail_date": (as_of_date - timedelta(days=1)).isoformat(), "shares_failed": 2000,  "sale_type": "LONG"},
    ]
    enriched = []
    for f in fails:
        fail_dt = date.fromisoformat(f["fail_date"])
        age = (as_of_date - fail_dt).days
        rule_204 = f["sale_type"] == "SHORT" and age >= 3
        enriched.append({**f, "age_days": age, "rule_204_breach": rule_204})
    return enriched

def generate_threshold_list():
    """Simulate SEC Threshold Securities List (published daily)."""
    return [
        {"ticker": "AMC",  "cusip": "00165C104", "days_on_list": 12},
        {"ticker": "NKLA", "cusip": "64110W102", "days_on_list": 7},
        {"ticker": "SPCE", "cusip": "857477103", "days_on_list": 3},
    ]
