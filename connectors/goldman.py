"""
connectors/goldman.py
Goldman Sachs borrow rate connector.

Production:
  - GS delivers a daily pipe-delimited borrow file via SFTP to a fund-specific drop folder.
  - File arrives ~6:45 AM ET. Filename format: GS_BORROW_YYYYMMDD.txt
  - Alternate: GS Marquee API (OAuth2) for intraday locate requests.

Config keys:
  sftp_host, sftp_user, sftp_key_path, sftp_remote_dir, local_dir
"""

import os
import pandas as pd
from datetime import date
from connectors.base import PrimeBrokerConnector


class GoldmanConnector(PrimeBrokerConnector):

    # GS column mapping → standard schema
    # Actual GS file headers vary by agreement; these reflect typical field names.
    GS_COLUMN_MAP = {
        "CUSIP":          "cusip",
        "TICKER":         "ticker",
        "BORROW_RATE":    "borrow_rate_pct",   # annualized %, e.g. 1.25
        "AVAIL_QTY":      "availability",
        "HTB_FLAG":       "_htb_flag",          # GS provides 'Y'/'N' directly
    }

    def __init__(self, config: dict):
        super().__init__("Goldman", config)

    def fetch(self) -> str:
        """
        Pull today's borrow file from GS SFTP drop.
        Returns local path of downloaded file.

        Production:
            import paramiko
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                self.config["sftp_host"],
                username=self.config["sftp_user"],
                key_filename=self.config["sftp_key_path"]
            )
            sftp = ssh.open_sftp()
            remote = f"{self.config['sftp_remote_dir']}/GS_BORROW_{date.today().strftime('%Y%m%d')}.txt"
            local  = os.path.join(self.config["local_dir"], os.path.basename(remote))
            sftp.get(remote, local)
            sftp.close(); ssh.close()
            return local
        """
        # ── Simulation mode ──────────────────────────────────────────────────
        self.logger.info("  [SIM] Goldman SFTP fetch skipped — using simulated file.")
        return self._write_simulated_file()

    def normalize(self, filepath: str) -> pd.DataFrame:
        """
        GS file is pipe-delimited with a header row.
        Rates are expressed as annualized percentages (1.25 = 1.25%).
        """
        df = pd.read_csv(filepath, delimiter="|", dtype=str)
        df = df.rename(columns=self.GS_COLUMN_MAP)

        # GS provides HTB_FLAG 'Y'/'N' — we derive status from rate for consistency
        df["borrow_rate_pct"] = pd.to_numeric(df["borrow_rate_pct"], errors="coerce")
        df["availability"]    = pd.to_numeric(df.get("availability", -1), errors="coerce").fillna(-1).astype(int)

        return df

    # ── Simulation helper ─────────────────────────────────────────────────────
    def _write_simulated_file(self) -> str:
        import random, tempfile
        from modules.simulate_pb_data import SHORT_BOOK, base_rate

        rows = []
        for pos in SHORT_BOOK:
            rate = round(max(0.10, base_rate(pos["ticker"]) + random.uniform(-0.10, 0.20)), 2)
            rows.append({
                "CUSIP":       pos["cusip"],
                "TICKER":      pos["ticker"],
                "BORROW_RATE": rate,
                "AVAIL_QTY":   random.randint(10000, 500000),
                "HTB_FLAG":    "Y" if rate > 1.0 else "N",
            })

        os.makedirs(self.config.get("local_dir", "data/inbound"), exist_ok=True)
        filepath = os.path.join(
            self.config.get("local_dir", "data/inbound"),
            f"GS_BORROW_{date.today().strftime('%Y%m%d')}.txt"
        )
        pd.DataFrame(rows).to_csv(filepath, sep="|", index=False)
        return filepath
