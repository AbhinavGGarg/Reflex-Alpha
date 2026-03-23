from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import List, Tuple

import requests


@dataclass
class StockQuote:
    symbol: str
    date: str
    time: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float


@dataclass
class StockHistory:
    symbol: str
    closes: List[float]
    volumes: List[float]


class StockDataClient:
    """Simple stock data client using Stooq CSV endpoints (no API key)."""

    def __init__(self, timeout: int = 12) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "ReflexAlphaTerminal/1.0",
                "Accept": "text/csv,text/plain,*/*",
            }
        )

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        clean = symbol.strip().upper()
        if not clean:
            return ""
        if clean.endswith(".US"):
            return clean
        return f"{clean}.US"

    def fetch_quote(self, symbol: str) -> StockQuote:
        normalized = self.normalize_symbol(symbol)
        url = f"https://stooq.com/q/l/?s={normalized.lower()}&f=sd2t2ohlcv&h&e=csv"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        rows = list(csv.DictReader(io.StringIO(response.text)))
        if not rows:
            raise ValueError(f"No quote rows returned for {symbol}")

        row = rows[0]
        if row.get("Close", "N/D") == "N/D":
            raise ValueError(f"No live quote available for {symbol}")

        return StockQuote(
            symbol=normalized,
            date=row.get("Date", ""),
            time=row.get("Time", ""),
            open_price=float(row.get("Open", 0.0)),
            high_price=float(row.get("High", 0.0)),
            low_price=float(row.get("Low", 0.0)),
            close_price=float(row.get("Close", 0.0)),
            volume=float(row.get("Volume", 0.0)),
        )

    def fetch_history(self, symbol: str, lookback_days: int = 120) -> StockHistory:
        normalized = self.normalize_symbol(symbol)
        url = f"https://stooq.com/q/d/l/?s={normalized.lower()}&i=d"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        reader = csv.DictReader(io.StringIO(response.text))
        closes: List[float] = []
        volumes: List[float] = []

        for row in reader:
            try:
                close_price = float(row.get("Close", "0"))
                volume = float(row.get("Volume", "0"))
            except ValueError:
                continue

            closes.append(close_price)
            volumes.append(volume)

        if len(closes) < 30:
            raise ValueError(f"Not enough history for {symbol}")

        return StockHistory(
            symbol=normalized,
            closes=closes[-lookback_days:],
            volumes=volumes[-lookback_days:],
        )


def parse_symbols(raw: str) -> List[str]:
    return [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]
