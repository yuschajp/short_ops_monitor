"""
connectors/datawarehouse.py
Data warehouse connector — pulls live short book from fund OMS/DW.

Designed for SQL Server-based data warehouses (Millennium MIK pattern,
Schonfeld, or any fund running Advent Geneva / Enfusion with a DW layer).

Production dependencies:
  pip install pyodbc pandas sqlalchemy

Config keys:
  dw_host, dw_port, dw_name, dw_user, dw_pass,
  fund_id, positions_table, driver ('ODBC Driver 17 for SQL Server')
"""

import logging
import pandas as pd
from datetime import date

logger = logging.getLogger("DataWarehouse")


# ── Standard position schema output ──────────────────────────────────────────
POSITION_COLUMNS = [
    "cusip",        # 9-char CUSIP
    "ticker",       # exchange ticker
    "sector",       # GICS sector
    "shares_short", # net short quantity (positive integer)
]


def get_short_book(config: dict) -> list[dict]:
    """
    Pull today's short book from the fund data warehouse.

    Production:
        Connects to SQL Server via pyodbc/SQLAlchemy.
        Queries the OMS positions table for net short positions as of today.
        Returns list of dicts matching POSITION_COLUMNS schema.

    Simulation:
        Returns the hardcoded SHORT_BOOK from simulate_pb_data.py.
        Swap the try block below for production.
    """
    try:
        # ── Production path ───────────────────────────────────────────────
        # Uncomment when DW credentials are available:
        #
        # from sqlalchemy import create_engine, text
        #
        # engine = create_engine(
        #     f"mssql+pyodbc://{config['dw_user']}:{config['dw_pass']}"
        #     f"@{config['dw_host']}:{config.get('dw_port', 1433)}"
        #     f"/{config['dw_name']}?driver={config.get('driver','ODBC+Driver+17+for+SQL+Server')}"
        # )
        #
        # query = text("""
        #     SELECT
        #         p.cusip,
        #         p.ticker,
        #         s.gics_sector      AS sector,
        #         ABS(SUM(p.quantity)) AS shares_short
        #     FROM {positions_table} p
        #     LEFT JOIN ref_security s ON p.cusip = s.cusip
        #     WHERE p.fund_id   = :fund_id
        #       AND p.side      = 'SHORT'
        #       AND p.as_of_dt  = CAST(GETDATE() AS DATE)
        #     GROUP BY p.cusip, p.ticker, s.gics_sector
        #     HAVING SUM(p.quantity) < 0
        #     ORDER BY ABS(SUM(p.quantity)) DESC
        # """.format(positions_table=config.get("positions_table", "dbo.oms_positions")))
        #
        # with engine.connect() as conn:
        #     df = pd.read_sql(query, conn, params={"fund_id": config["fund_id"]})
        # return df[POSITION_COLUMNS].to_dict("records")

        raise NotImplementedError("DW not configured — falling back to simulation.")

    except Exception as e:
        logger.warning(f"DW connection unavailable ({e}) — using simulated short book.")
        return _simulated_short_book()


def get_corporate_actions(config: dict, tickers: list[str], days_ahead: int = 14) -> list[dict]:
    """
    Pull upcoming corporate actions (dividends, proxy votes) for short book tickers.

    Production:
        Query the fund's corporate actions feed table — typically populated nightly
        from Bloomberg BPIPE or Refinitiv Elektron via an existing ETL job.

    Simulation:
        Returns hardcoded events from simulate_pb_data.py.
    """
    try:
        raise NotImplementedError("Corp actions DW feed not configured.")

    except Exception as e:
        logger.warning(f"Corp actions unavailable ({e}) — using simulated data.")
        from modules.simulate_pb_data import generate_recalls
        return generate_recalls(date.today())


def get_settlement_fails(config: dict) -> list[dict]:
    """
    Pull open settlement fails from the fund DW or prime broker fails file.

    Production:
        PB delivers a daily fails file via SFTP (same drop as borrow rates).
        ETL loads it into dbo.settlement_fails by 7:00 AM.
        Query returns all open fails as of today.

    Simulation:
        Returns hardcoded fails from simulate_pb_data.py.
    """
    try:
        raise NotImplementedError("Fails DW feed not configured.")

    except Exception as e:
        logger.warning(f"Fails feed unavailable ({e}) — using simulated data.")
        from modules.simulate_pb_data import generate_fails
        return generate_fails(date.today())


def get_threshold_securities(config: dict) -> list[dict]:
    """
    Fetch SEC Threshold Securities List.
    This is a live public feed — production-ready today.
    Falls back to simulation if the SEC site is unreachable.
    """
    try:
        import requests
        from io import StringIO

        # SEC publishes threshold list daily as a pipe-delimited text file
        # One file per exchange: NYSE, NASDAQ, OTC
        urls = {
            "NYSE":   "https://www.sec.gov/foia/docs/threshold-securities/NYSE.txt",
            "NASDAQ": "https://www.sec.gov/foia/docs/threshold-securities/NASDAQ.txt",
            "OTC":    "https://www.sec.gov/foia/docs/threshold-securities/OTC.txt",
        }

        records = []
        for exchange, url in urls.items():
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            lines = resp.text.strip().split("\n")
            # Format: Date|CUSIP|Symbol|Company Name|Reg SHO Threshold Flag|Rule 4320 Flag
            for line in lines[1:]:  # skip header
                parts = line.split("|")
                if len(parts) >= 3:
                    records.append({
                        "cusip":        parts[1].strip(),
                        "ticker":       parts[2].strip(),
                        "days_on_list": 1,  # DW would track rolling count; SEC file is daily snapshot
                        "exchange":     exchange,
                    })
        if records:
            logger.info(f"  SEC Threshold List: {len(records)} securities loaded.")
            return records
        raise ValueError("Empty threshold list response.")

    except Exception as e:
        logger.warning(f"SEC threshold list unavailable ({e}) — using simulated data.")
        from modules.simulate_pb_data import generate_threshold_list
        return generate_threshold_list()


# ── Simulation fallback ───────────────────────────────────────────────────────
def _simulated_short_book() -> list[dict]:
    from modules.simulate_pb_data import SHORT_BOOK
    return [
        {
            "cusip":        p["cusip"],
            "ticker":       p["ticker"],
            "sector":       p["sector"],
            "shares_short": p["shares_short"],
        }
        for p in SHORT_BOOK
    ]
