"""
Data downloader with parquet-based caching.
Hash-based cache keys ensure reproducibility across runs.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import List, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def _cache_key(stocks: List[str], start: str) -> str:
    """Deterministic cache key from stocks list + start date."""
    key_str = ",".join(sorted(stocks)) + "|" + start
    return hashlib.md5(key_str.encode()).hexdigest()[:12]


def download_prices(
    stocks: List[str],
    start: str,
    cache_dir: str = "data/cache",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Download adjusted close prices for given stocks.

    Parameters
    ----------
    stocks       : list of ticker symbols
    start        : start date string (YYYY-MM-DD)
    cache_dir    : directory to cache parquet files
    force_refresh: if True, ignore existing cache

    Returns
    -------
    pd.DataFrame  columns = stock tickers, index = Date
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    key = _cache_key(stocks, start)
    cache_file = cache_path / f"prices_{key}.parquet"

    if cache_file.exists() and not force_refresh:
        logger.info("Loading prices from cache: %s", cache_file)
        prices = pd.read_parquet(cache_file)
        if prices.empty:
            logger.warning("Cache file contains empty data, bypassing cache.")
        else:
            logger.info(
                "Cache hit — %d stocks, %d rows, %s to %s",
                len(prices.columns),
                len(prices),
                prices.index[0].date(),
                prices.index[-1].date(),
            )
            return prices

    logger.info("Downloading %d stocks from %s ...", len(stocks), start)
    data = yf.download(stocks, start=start, auto_adjust=True, progress=False)

    # yfinance ≥ 0.2.38 / 1.x always returns a MultiIndex (price_field, ticker).
    # Flatten it so downstream code gets a plain DataFrame with ticker names as columns.
    close = data["Close"]
    if isinstance(close.columns, pd.MultiIndex):
        close = close.droplevel(0, axis=1)          # drop the price-field level
    elif isinstance(close, pd.Series):
        # Single ticker downloaded as Series — wrap it back into a DataFrame
        close = close.to_frame(name=stocks[0])

    # Drop tickers that failed entirely (all NaNs)
    close = close.dropna(axis=1, how="all")
    
    prices: pd.DataFrame = close.dropna()

    if prices.empty:
        raise ValueError(f"No valid price data downloaded for stocks: {stocks}")

    prices.to_parquet(cache_file)
    logger.info(
        "Downloaded and cached — %d rows, %s to %s → %s",
        len(prices),
        prices.index[0].date(),
        prices.index[-1].date(),
        cache_file,
    )
    return prices


def load_prices(
    stocks: List[str],
    start: str,
    cache_dir: str = "data/cache",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Alias for download_prices. Preferred name for clarity."""
    return download_prices(stocks, start, cache_dir, force_refresh)
