"""
=============================================================================
STEP 1: DATA INGESTION
=============================================================================

WHAT DATA WE NEED AND WHY:
- timestamp: ordering events in time (fundamental to any time-series strategy)
- price: the market's current estimate of event probability (0 to 1 on Polymarket)
- volume: how much is being traded — high volume = conviction, low = noise
- wallet_id: WHO is trading — some wallets are consistently profitable ("smart money")

WHY THESE FOUR?
Price alone tells you "what happened." Volume tells you "how much conviction."
Wallet tells you "who believes this." Together they let you build signals that
separate informed trading from noise.

FOR THE MVP:
We simulate realistic data with known statistical properties. This lets us:
1. Develop and test the full pipeline without API rate limits
2. Control the signal-to-noise ratio (so we know if our model CAN work)
3. Swap in real data later without changing downstream code

The simulation uses geometric Brownian motion (standard for price processes)
with volume correlated to price moves (realistic: big moves attract volume).
"""

import numpy as np
import pandas as pd
import json
from typing import Any
import requests
from monitoring import get_logger
from config import (
    NUM_TIMESTAMPS, NUM_WALLETS, PRICE_START,
    PRICE_VOLATILITY
)

logger = get_logger("DataIngestion")

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"


def generate_simulated_data(
    num_timestamps: int = NUM_TIMESTAMPS,
    num_wallets: int = NUM_WALLETS,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic Polymarket-like trade data.
    
    The price follows geometric Brownian motion:
        price[t] = price[t-1] * exp(drift + volatility * noise)
    
    This is the standard model for financial prices because:
    - Prices can't go negative
    - Returns are roughly normally distributed
    - It captures trending + mean-reverting behavior via drift
    
    Volume is correlated with absolute price changes (realistic behavior:
    big moves attract more trading activity).
    """
    np.random.seed(seed)
    logger.info(f"Generating {num_timestamps} timestamps, {num_wallets} wallets")

    # --- Price generation (mean-reverting process) ---
    # Use Ornstein-Uhlenbeck process: reverts to 0.50 (fair odds)
    # This ensures both up and down moves throughout the series
    prices = np.zeros(num_timestamps)
    prices[0] = PRICE_START
    mean_reversion_speed = 0.02  # How fast price reverts to mean

    for t in range(1, num_timestamps):
        noise = np.random.normal(0, PRICE_VOLATILITY)
        drift = mean_reversion_speed * (PRICE_START - prices[t - 1])
        prices[t] = prices[t - 1] + drift + noise

    # Clip to [0.05, 0.95] — Polymarket prices are probabilities
    prices = np.clip(prices, 0.05, 0.95)

    # Compute returns for volume correlation
    returns = np.diff(prices) / prices[:-1]
    returns = np.insert(returns, 0, 0.0)

    # --- Volume generation (correlated with price moves) ---
    base_volume = np.random.exponential(1000, num_timestamps)
    # Volume spikes when price moves are large
    move_magnitude = np.abs(returns) / (PRICE_VOLATILITY + 1e-9)
    volume = base_volume * (1 + move_magnitude)

    # --- Wallet assignment (some wallets trade more = realistic power law) ---
    wallet_ids = [f"wallet_{i:03d}" for i in range(num_wallets)]
    # Power-law distribution: few wallets dominate volume
    wallet_weights = np.random.pareto(1.5, num_wallets)
    wallet_weights /= wallet_weights.sum()
    assigned_wallets = np.random.choice(wallet_ids, size=num_timestamps, p=wallet_weights)

    # --- Assemble DataFrame ---
    df = pd.DataFrame({
        "timestamp": np.arange(num_timestamps),
        "price": prices,
        "volume": volume,
        "wallet_id": assigned_wallets,
    })

    logger.info(
        f"Data generated: shape={df.shape}, "
        f"price_range=[{df['price'].min():.4f}, {df['price'].max():.4f}], "
        f"avg_volume={df['volume'].mean():.1f}"
    )

    return df


def _parse_token_ids(clob_token_ids: Any) -> list[str]:
    """
    Parse the CLOB token id list from Gamma market payload.
    Gamma returns this field as a JSON-encoded string.
    """
    if clob_token_ids is None:
        return []

    if isinstance(clob_token_ids, list):
        return [str(token) for token in clob_token_ids if token is not None]

    if isinstance(clob_token_ids, str):
        try:
            parsed = json.loads(clob_token_ids)
            if isinstance(parsed, list):
                return [str(token) for token in parsed if token is not None]
        except json.JSONDecodeError:
            return []

    return []


def _market_volume(market: dict[str, Any]) -> float:
    """
    Extract sortable volume for market ranking when slug is not provided.
    """
    for key in ("volumeNum", "volume", "volume24hr"):
        value = market.get(key)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _select_market(session: requests.Session, market_slug: str | None) -> dict[str, Any]:
    """
    Resolve target market from slug, otherwise choose the most liquid active market.
    """
    if market_slug:
        resp = session.get(
            f"{GAMMA_API_BASE}/markets",
            params={"slug": market_slug},
            timeout=15,
        )
        resp.raise_for_status()
        markets = resp.json() or []
        if markets:
            return markets[0]
        raise RuntimeError(f"No market found for slug: {market_slug}")

    resp = session.get(
        f"{GAMMA_API_BASE}/markets",
        params={"limit": 200},
        timeout=15,
    )
    resp.raise_for_status()
    markets = resp.json() or []

    candidates = [
        market
        for market in markets
        if market.get("active", False) and _parse_token_ids(market.get("clobTokenIds"))
    ]
    if not candidates:
        raise RuntimeError("No active markets with CLOB tokens were found")

    candidates.sort(key=_market_volume, reverse=True)
    return candidates[0]


def _extract_wallet_id(trade: dict[str, Any]) -> str:
    """
    Pick a wallet identifier from whichever key is present in trade payload.
    """
    for key in (
        "proxyWallet",
        "makerAddress",
        "maker",
        "trader",
        "wallet",
        "owner",
        "user",
    ):
        value = trade.get(key)
        if value:
            return str(value)
    return "unknown_wallet"


def _normalize_trades(trades: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Convert raw Polymarket trade objects into the pipeline schema.
    """
    rows: list[dict[str, Any]] = []
    for trade in trades:
        timestamp_raw = trade.get("timestamp")
        price_raw = trade.get("price")
        size_raw = trade.get("size")

        if timestamp_raw is None or price_raw is None or size_raw is None:
            continue

        try:
            timestamp = float(timestamp_raw)
            if timestamp > 1e12:
                timestamp /= 1000.0
            price = float(price_raw)
            volume = abs(float(size_raw))
        except (TypeError, ValueError):
            continue

        rows.append(
            {
                "timestamp": int(timestamp),
                "price": price,
                "volume": volume,
                "wallet_id": _extract_wallet_id(trade),
            }
        )

    if not rows:
        raise RuntimeError("Trades endpoint returned no usable rows")

    df = pd.DataFrame(rows)
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    df["price"] = df["price"].clip(lower=0.0, upper=1.0)
    df = df[df["volume"] > 0]
    df = df.sort_values("timestamp").drop_duplicates().reset_index(drop=True)

    if len(df) < 200:
        raise RuntimeError(
            f"Insufficient live data for training ({len(df)} rows). Increase max_trades."
        )

    return df


def fetch_real_polymarket_data(
    market_slug: str | None = None,
    max_trades: int = 5000,
    allow_simulated_fallback: bool = False,
) -> pd.DataFrame:
    """
    Fetch live Polymarket trade data and map it to the training schema.

    Output schema:
      timestamp (unix seconds), price (0..1), volume (trade size), wallet_id

    If no slug is passed, the most liquid active market is selected automatically.
    """
    logger.info(
        "Fetching live Polymarket data "
        f"(slug={market_slug or 'auto'}, max_trades={max_trades})"
    )

    try:
        with requests.Session() as session:
            market = _select_market(session, market_slug=market_slug)
            token_ids = _parse_token_ids(market.get("clobTokenIds"))
            if not token_ids:
                raise RuntimeError("Selected market does not expose CLOB token ids")

            token_id = token_ids[0]
            logger.info(
                "Resolved market: "
                f"question={market.get('question', 'unknown')} | "
                f"slug={market.get('slug', 'unknown')} | token={token_id}"
            )

            trade_resp = session.get(
                f"{DATA_API_BASE}/trades",
                params={"market": token_id, "limit": max_trades},
                timeout=20,
            )
            trade_resp.raise_for_status()
            trades = trade_resp.json()

            if not isinstance(trades, list) or not trades:
                raise RuntimeError("No trades returned from Polymarket data API")

            df = _normalize_trades(trades)

            logger.info(
                f"Live data fetched: shape={df.shape}, "
                f"price_range=[{df['price'].min():.4f}, {df['price'].max():.4f}], "
                f"avg_volume={df['volume'].mean():.4f}, "
                f"wallets={df['wallet_id'].nunique()}"
            )
            return df

    except Exception as e:
        if allow_simulated_fallback:
            logger.warning(f"Live API fetch failed ({e}), falling back to simulated data")
            return generate_simulated_data()
        raise RuntimeError(f"Live Polymarket ingestion failed: {e}") from e


if __name__ == "__main__":
    # Quick sanity check
    df = fetch_real_polymarket_data()
    print("\n=== Sample Data (first 5 rows) ===")
    print(df.head().to_string())
    print("\n=== Data Stats ===")
    print(df.describe().to_string())
