"""
db.py
SQLite data layer for short ops monitor.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "short_ops.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS borrow_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date TEXT,
            cusip TEXT,
            ticker TEXT,
            sector TEXT,
            shares_short INTEGER,
            prime_broker TEXT,
            borrow_rate_pct REAL,
            status TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS recall_risk (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            cusip TEXT,
            event_type TEXT,
            record_date TEXT,
            days_until_record INTEGER,
            urgency TEXT,
            shares_at_risk INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settlement_fails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            cusip TEXT,
            fail_date TEXT,
            shares_failed INTEGER,
            sale_type TEXT,
            age_days INTEGER,
            rule_204_breach INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS threshold_securities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            cusip TEXT,
            days_on_list INTEGER
        )
    """)

    conn.commit()
    conn.close()

def insert_borrow_rates(records):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM borrow_rates")
    c.executemany("""
        INSERT INTO borrow_rates (report_date, cusip, ticker, sector, shares_short, prime_broker, borrow_rate_pct, status)
        VALUES (:report_date, :cusip, :ticker, :sector, :shares_short, :prime_broker, :borrow_rate_pct, :status)
    """, records)
    conn.commit()
    conn.close()

def insert_recalls(records):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM recall_risk")
    c.executemany("""
        INSERT INTO recall_risk (ticker, cusip, event_type, record_date, days_until_record, urgency, shares_at_risk)
        VALUES (:ticker, :cusip, :event_type, :record_date, :days_until_record, :urgency, :shares_at_risk)
    """, records)
    conn.commit()
    conn.close()

def insert_fails(records):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM settlement_fails")
    c.executemany("""
        INSERT INTO settlement_fails (ticker, cusip, fail_date, shares_failed, sale_type, age_days, rule_204_breach)
        VALUES (:ticker, :cusip, :fail_date, :shares_failed, :sale_type, :age_days, :rule_204_breach)
    """, records)
    conn.commit()
    conn.close()

def insert_threshold(records):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM threshold_securities")
    c.executemany("""
        INSERT INTO threshold_securities (ticker, cusip, days_on_list)
        VALUES (:ticker, :cusip, :days_on_list)
    """, records)
    conn.commit()
    conn.close()

def query(sql, params=()):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(sql, params)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
