"""
connectors/jpmorgan.py
JPMorgan borrow rate connector.

Production:
  - JPM delivers via SFTP. Filename: JPM_BORROW_AVAIL_YYYYMMDD.txt
  - File arrives ~6:30 AM ET (earliest of the three).
  - JPM uses a fixed-width format (not delimited) in some agreements,
    CSV in others — config-driven.
  - JPM also has a Markets API for real-time locate requests (OAuth2 + JWT).

Config keys:
  sftp_host, sftp_user, sftp_key_path, sftp_remote_dir, local_dir,
  file_format ('csv' or 'fixed_width')
"""

import os
import pandas as pd
from datetime import date
from connectors.base import PrimeBrokerConnector


class JPMorganConnector(PrimeBrokerConnector):

    JPM_COLUMN_MAP = {
        "cusip_id":        "cusip",
        "mkt_ticker":      "ticker",
        "annual_rate_pct": "borrow_rate_pct",
        "avail_shares":    "availability",
    }

    def __init__(self, config: dict):
        super().__init__("JPMorgan", config)

    def fetch(self) -> str:
        """
        Production:
            JPM SFTP pull. If config file_format == 'fixed_width',
            use pd.read_fwf() with colspecs provided by JPM ops team.
            Otherwise pd.read_csv().
        """
        self.logger.info("  [SIM] JPMorgan SFTP fetch skipped — using simulated file.")
        return self._write_simulated_file()

    def normalize(self, filepath: str) -> pd.DataFrame:
        """
        JPM delivers rate as annual_rate_pct already in percent terms (same as GS).
        File format is CSV in simulation; fixed-width toggled via config in production.
        """
        file_format = self.config.get("file_format", "csv")

        if file_format == "fixed_width":
            # colspecs defined by JPM operations team documentation
            colspecs = self.config.get("colspecs", [(0,9),(10,20),(21,28),(29,38)])
            names    = ["cusip_id", "mkt_ticker", "annual_rate_pct", "avail_shares"]
            df = pd.read_fwf(filepath, colspecs=colspecs, names=names, dtype=str)
        else:
            df = pd.read_csv(filepath, dtype=str)

        df = df.rename(columns=self.JPM_COLUMN_MAP)
        df["borrow_rate_pct"] = pd.to_numeric(df["borrow_rate_pct"], errors="coerce")
        df["availability"]    = pd.to_numeric(df.get("availability", -1), errors="coerce").fillna(-1).astype(int)

        return df

    def _write_simulated_file(self) -> str:
        import random
        from modules.simulate_pb_data import SHORT_BOOK, base_rate

        rows = []
        for pos in SHORT_BOOK:
            rate = round(max(0.10, base_rate(pos["ticker"]) + random.uniform(-0.12, 0.22)), 2)
            rows.append({
                "cusip_id":        pos["cusip"],
                "mkt_ticker":      pos["ticker"],
                "annual_rate_pct": rate,
                "avail_shares":    random.randint(8000, 450000),
            })

        os.makedirs(self.config.get("local_dir", "data/inbound"), exist_ok=True)
        filepath = os.path.join(
            self.config.get("local_dir", "data/inbound"),
            f"JPM_BORROW_AVAIL_{date.today().strftime('%Y%m%d')}.txt"
        )
        pd.DataFrame(rows).to_csv(filepath, index=False)
        return filepath
