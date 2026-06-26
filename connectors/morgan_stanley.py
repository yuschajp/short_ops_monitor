"""
connectors/morgan_stanley.py
Morgan Stanley borrow rate connector.

Production:
  - MS delivers via SFTP. Filename: MS_SBL_RATES_YYYYMMDD.csv
  - File arrives ~7:00 AM ET.
  - MS expresses rates as basis points (125 = 1.25%) — requires conversion.
  - MS also provides a separate hard-to-borrow list file: MS_HTB_YYYYMMDD.csv

Config keys:
  sftp_host, sftp_user, sftp_key_path, sftp_remote_dir, local_dir
"""

import os
import pandas as pd
from datetime import date
from connectors.base import PrimeBrokerConnector


class MorganStanleyConnector(PrimeBrokerConnector):

    # MS uses different field names and expresses rates in BASIS POINTS
    MS_COLUMN_MAP = {
        "Cusip":          "cusip",
        "Symbol":         "ticker",
        "RateBps":        "_rate_bps",     # basis points — must divide by 100
        "SharesAvail":    "availability",
    }

    def __init__(self, config: dict):
        super().__init__("Morgan Stanley", config)

    def fetch(self) -> str:
        """
        Production:
            Pull MS_SBL_RATES_YYYYMMDD.csv from MS SFTP.
            MS sometimes delivers two files: rates + HTB override list.
            If HTB list present, merge it after normalize().
        """
        self.logger.info("  [SIM] Morgan Stanley SFTP fetch skipped — using simulated file.")
        return self._write_simulated_file()

    def normalize(self, filepath: str) -> pd.DataFrame:
        """
        MS key difference: rates are in BASIS POINTS, not percent.
        125 bps → 1.25% annualized. Divide by 100.
        """
        df = pd.read_csv(filepath, dtype=str)
        df = df.rename(columns=self.MS_COLUMN_MAP)

        # Convert bps → percent
        df["borrow_rate_pct"] = pd.to_numeric(df["_rate_bps"], errors="coerce") / 100
        df["availability"]    = pd.to_numeric(df.get("availability", -1), errors="coerce").fillna(-1).astype(int)

        return df

    def _write_simulated_file(self) -> str:
        import random
        from modules.simulate_pb_data import SHORT_BOOK, base_rate

        rows = []
        for pos in SHORT_BOOK:
            rate_pct = round(max(0.10, base_rate(pos["ticker"]) + random.uniform(-0.15, 0.25)), 2)
            rows.append({
                "Cusip":       pos["cusip"],
                "Symbol":      pos["ticker"],
                "RateBps":     int(rate_pct * 100),   # store as bps in the simulated file
                "SharesAvail": random.randint(5000, 400000),
            })

        os.makedirs(self.config.get("local_dir", "data/inbound"), exist_ok=True)
        filepath = os.path.join(
            self.config.get("local_dir", "data/inbound"),
            f"MS_SBL_RATES_{date.today().strftime('%Y%m%d')}.csv"
        )
        pd.DataFrame(rows).to_csv(filepath, index=False)
        return filepath
