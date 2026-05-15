"""
=============================================================================
STEP 2: FEATURE ENGINEERING
=============================================================================

WHY THESE FEATURES MATTER:

1. MOMENTUM (returns over N steps):
   - Captures trend direction. Markets that are going up tend to keep going up
     (short-term momentum effect). This is one of the most robust signals in
     quantitative finance — it works across asset classes and time horizons.
   - Calculated as: (price[t] - price[t-N]) / price[t-N]

2. ROLLING VOLUME:
   - Volume confirms conviction. A price move on high volume is more meaningful
     than one on low volume. We use rolling average to smooth noise.
   - Also: volume spikes often precede big moves (informed traders act first).

3. ROLLING VOLATILITY:
   - Measures uncertainty. High volatility = market is unsure = potential opportunity.
   - Also used for position sizing in production (bet less when uncertain).
   - Calculated as: std(returns) over rolling window.

WHY ROLLING WINDOWS?
Raw point-in-time values are noisy. Rolling aggregations smooth out noise while
preserving the signal. The window size (10 steps) is a hyperparameter — in
production you'd optimize this.

IMPORTANT: All features use ONLY past data (no look-ahead bias).
"""

import pandas as pd
import numpy as np
from monitoring import get_logger
from config import MOMENTUM_WINDOW, VOLUME_WINDOW, VOLATILITY_WINDOW

logger = get_logger("FeatureEngineering")


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add trading features to the raw data.
    
    All features are backward-looking only (no future information leakage).
    This is critical — if you accidentally use future data in features,
    your backtest will look amazing but your live system will fail.
    """
    df = df.copy()
    logger.info(f"Engineering features on {len(df)} rows")

    # --- 1. Returns (basis for momentum) ---
    df["returns"] = df["price"].pct_change()

    # --- 2. Momentum: cumulative return over lookback window ---
    # This captures "is the market trending up or down?"
    df["momentum"] = df["price"].pct_change(periods=MOMENTUM_WINDOW)

    # --- 3. Rolling Volume: smoothed trading activity ---
    # High rolling volume = sustained interest, not just a spike
    df["rolling_volume"] = df["volume"].rolling(window=VOLUME_WINDOW).mean()

    # --- 4. Rolling Volatility: uncertainty measure ---
    # High volatility = market is repricing = opportunity
    df["rolling_volatility"] = df["returns"].rolling(window=VOLATILITY_WINDOW).std()

    # --- 5. Volume-weighted momentum (interaction feature) ---
    # Momentum confirmed by volume is stronger signal
    df["volume_momentum"] = df["momentum"] * df["rolling_volume"]

    # --- 6. Price distance from mean (mean-reversion signal) ---
    # How far is current price from recent average?
    df["price_zscore"] = (
        (df["price"] - df["price"].rolling(20).mean()) /
        df["price"].rolling(20).std()
    )

    # --- Drop rows with NaN (from rolling calculations) ---
    initial_len = len(df)
    df = df.dropna().reset_index(drop=True)
    dropped = initial_len - len(df)

    logger.info(
        f"Features engineered: dropped {dropped} NaN rows, "
        f"{len(df)} rows remaining"
    )

    # --- Monitoring: show sample feature values ---
    sample = df.iloc[0:3][["timestamp", "price", "momentum", "rolling_volume",
                            "rolling_volatility", "volume_momentum", "price_zscore"]]
    logger.info(f"Sample feature values:\n{sample.to_string()}")

    return df


if __name__ == "__main__":
    from data_ingestion import generate_simulated_data

    df = generate_simulated_data()
    df = engineer_features(df)

    print("\n=== Feature Statistics ===")
    feature_cols = ["momentum", "rolling_volume", "rolling_volatility",
                    "volume_momentum", "price_zscore"]
    print(df[feature_cols].describe().to_string())
