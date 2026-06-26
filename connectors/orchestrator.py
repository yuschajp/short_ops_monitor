"""
connectors/orchestrator.py
Runs all PB connectors in parallel, merges output into the standard schema,
and loads into the database.

This replaces simulate_pb_data.py in production.
Toggle SIM_MODE = False and populate config.py with real credentials to go live.
"""

import os
import sys
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.goldman       import GoldmanConnector
from connectors.morgan_stanley import MorganStanleyConnector
from connectors.jpmorgan      import JPMorganConnector
from connectors.datawarehouse import (
    get_short_book, get_corporate_actions,
    get_settlement_fails, get_threshold_securities
)
from modules.db import (
    init_db, insert_borrow_rates, insert_recalls,
    insert_fails, insert_threshold
)

logger = logging.getLogger("Orchestrator")

# ── Config ────────────────────────────────────────────────────────────────────
# Production: populate from environment variables or a secrets manager (AWS SSM, etc.)
# Never commit credentials to git.

CONNECTOR_CONFIG = {
    "Goldman": {
        "sftp_host":       os.getenv("GS_SFTP_HOST",    "sftp.gs.com"),
        "sftp_user":       os.getenv("GS_SFTP_USER",    "fund_user"),
        "sftp_key_path":   os.getenv("GS_SFTP_KEY",     "~/.ssh/gs_sftp_rsa"),
        "sftp_remote_dir": os.getenv("GS_SFTP_DIR",     "/borrow/outbound"),
        "local_dir":       "data/inbound",
    },
    "Morgan Stanley": {
        "sftp_host":       os.getenv("MS_SFTP_HOST",    "sftp.morganstanley.com"),
        "sftp_user":       os.getenv("MS_SFTP_USER",    "fund_user"),
        "sftp_key_path":   os.getenv("MS_SFTP_KEY",     "~/.ssh/ms_sftp_rsa"),
        "sftp_remote_dir": os.getenv("MS_SFTP_DIR",     "/sbl/rates"),
        "local_dir":       "data/inbound",
    },
    "JPMorgan": {
        "sftp_host":       os.getenv("JPM_SFTP_HOST",   "sftp.jpmorgan.com"),
        "sftp_user":       os.getenv("JPM_SFTP_USER",   "fund_user"),
        "sftp_key_path":   os.getenv("JPM_SFTP_KEY",    "~/.ssh/jpm_sftp_rsa"),
        "sftp_remote_dir": os.getenv("JPM_SFTP_DIR",    "/borrow/daily"),
        "local_dir":       "data/inbound",
        "file_format":     "csv",
    },
}

DW_CONFIG = {
    "dw_host":          os.getenv("DW_HOST",      "dw-prod.fund.internal"),
    "dw_port":          os.getenv("DW_PORT",      "1433"),
    "dw_name":          os.getenv("DW_NAME",      "FundDW"),
    "dw_user":          os.getenv("DW_USER",      "ops_readonly"),
    "dw_pass":          os.getenv("DW_PASS",      ""),
    "fund_id":          os.getenv("FUND_ID",      "FUND01"),
    "positions_table":  "dbo.oms_positions",
    "driver":           "ODBC Driver 17 for SQL Server",
}


def run_pb_connectors() -> list[dict]:
    """
    Run all three PB connectors in parallel via ThreadPoolExecutor.
    Returns merged list of borrow rate records in standard schema.
    """
    connectors = [
        GoldmanConnector(CONNECTOR_CONFIG["Goldman"]),
        MorganStanleyConnector(CONNECTOR_CONFIG["Morgan Stanley"]),
        JPMorganConnector(CONNECTOR_CONFIG["JPMorgan"]),
    ]

    all_records = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(c.run): c.name for c in connectors}
        for future in as_completed(futures):
            pb_name = futures[future]
            try:
                df = future.result()
                all_records.extend(df.to_dict("records"))
                logger.info(f"  ✓ {pb_name}: {len(df)} records")
            except Exception as e:
                logger.error(f"  ✗ {pb_name} failed: {e}")

    return all_records


def run_all(short_book_override: list[dict] = None) -> dict:
    """
    Full orchestration run:
      1. Pull short book from DW (or use override for testing)
      2. Pull borrow rates from all 3 PBs in parallel
      3. Pull corporate actions, fails, threshold list
      4. Load everything into SQLite

    Returns dict of record counts for logging.
    """
    os.makedirs("data/inbound", exist_ok=True)
    init_db()

    logger.info("── Short Book ──────────────────────────────────")
    short_book = short_book_override or get_short_book(DW_CONFIG)
    logger.info(f"  {len(short_book)} positions loaded")

    logger.info("── PB Borrow Rates ─────────────────────────────")
    borrow_records = run_pb_connectors()

    # Enrich with shares_short from short book
    short_map = {p["cusip"]: p for p in short_book}
    for r in borrow_records:
        pos = short_map.get(r.get("cusip"), {})
        r["sector"]       = pos.get("sector", "Unknown")
        r["shares_short"] = pos.get("shares_short", 0)

    insert_borrow_rates(borrow_records)
    logger.info(f"  {len(borrow_records)} borrow rate records inserted")

    logger.info("── Corporate Actions ───────────────────────────")
    tickers = [p["ticker"] for p in short_book]
    recalls = get_corporate_actions(DW_CONFIG, tickers)
    insert_recalls(recalls)
    logger.info(f"  {len(recalls)} recall risk records inserted")

    logger.info("── Settlement Fails ────────────────────────────")
    fails = get_settlement_fails(DW_CONFIG)
    insert_fails(fails)
    logger.info(f"  {len(fails)} fail records inserted")

    logger.info("── Threshold Securities ────────────────────────")
    threshold = get_threshold_securities(DW_CONFIG)
    insert_threshold(threshold)
    logger.info(f"  {len(threshold)} threshold securities inserted")

    return {
        "short_book":    len(short_book),
        "borrow_rates":  len(borrow_records),
        "recalls":       len(recalls),
        "fails":         len(fails),
        "threshold":     len(threshold),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    counts = run_all()
    print("\nLoad complete:", counts)
