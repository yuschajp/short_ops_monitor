"""
connectors/base.py
Abstract base class for all prime broker data connectors.
Each PB connector inherits this and implements fetch() and normalize().
"""

import os
import logging
from abc import ABC, abstractmethod
from datetime import date
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)


class PrimeBrokerConnector(ABC):
    """
    Base class for prime broker SFTP/API connectors.

    Production subclasses implement:
      - fetch()      → pulls raw file from PB SFTP or API
      - normalize()  → maps PB-specific schema to standard schema
      - run()        → orchestrates fetch + normalize + validate + return
    """

    # Standard output schema all connectors must produce
    STANDARD_COLUMNS = [
        "report_date",     # str YYYY-MM-DD
        "cusip",           # 9-char CUSIP
        "ticker",          # exchange ticker
        "prime_broker",    # connector name
        "borrow_rate_pct", # annualized borrow rate as float (e.g. 1.25 = 1.25%)
        "status",          # 'HTB' or 'ETB'
        "availability",    # shares available to borrow (int, -1 if not provided)
    ]

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(name)
        self.as_of = date.today().isoformat()

    @abstractmethod
    def fetch(self) -> str:
        """Pull raw data from source. Returns local filepath of downloaded file."""
        pass

    @abstractmethod
    def normalize(self, filepath: str) -> pd.DataFrame:
        """Map raw PB file to standard schema. Returns normalized DataFrame."""
        pass

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Shared validation applied to every connector's output.
        Drops rows with missing CUSIP or invalid rates.
        """
        before = len(df)
        df = df.dropna(subset=["cusip", "borrow_rate_pct"])
        df = df[df["borrow_rate_pct"] >= 0]
        df["status"] = df["borrow_rate_pct"].apply(
            lambda r: "HTB" if r > 1.0 else "ETB"
        )
        df["report_date"] = self.as_of
        df["prime_broker"] = self.name
        after = len(df)
        if before != after:
            self.logger.warning(f"Dropped {before - after} invalid rows during validation.")
        return df[self.STANDARD_COLUMNS]

    def run(self) -> pd.DataFrame:
        """Full pipeline: fetch → normalize → validate."""
        self.logger.info(f"Starting feed pull for {self.name}")
        filepath = self.fetch()
        df = self.normalize(filepath)
        df = self.validate(df)
        self.logger.info(f"  {len(df)} records loaded from {self.name}")
        return df
