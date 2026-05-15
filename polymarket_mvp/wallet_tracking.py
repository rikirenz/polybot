"""
=============================================================================
STEP 6: WALLET TRACKING (SMART MONEY)
=============================================================================

WHY TRACKING PROFITABLE WALLETS CREATES EDGE:

On Polymarket (and all blockchain markets), every trade is PUBLIC. You can see
exactly which wallet made which trade. This is a massive informational advantage
that doesn't exist in traditional finance.

THE INSIGHT:
Some wallets are consistently profitable. These are "smart money" — they might be:
- Professional traders with better models
- Insiders with information
- Market makers with sophisticated strategies

If smart money is buying, that's a signal. Not because we're copying them blindly,
but because their activity CONFIRMS (or contradicts) our model's prediction.

HOW WE USE IT:
1. Track each wallet's historical profitability
2. Identify the top-N most profitable wallets
3. Create a feature: "are smart money wallets active right now?"
4. Use this as an additional input to our trading decision

This is the blockchain equivalent of watching what hedge funds are doing —
except here it's transparent and real-time.
"""

import pandas as pd
import numpy as np
from monitoring import get_logger
from config import SMART_MONEY_TOP_N, SMART_MONEY_LOOKBACK, FORWARD_RETURN_STEPS

logger = get_logger("WalletTracking")


def compute_wallet_profitability(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each wallet, compute their average return on trades.
    
    A wallet's "profitability" = average future return of their trades.
    If a wallet consistently buys before price goes up, they're smart money.
    """
    logger.info(f"Computing wallet profitability for {df['wallet_id'].nunique()} wallets")

    # Each row is a trade. Compute the return that followed each trade.
    wallet_stats = df.groupby("wallet_id").agg(
        num_trades=("future_return", "count"),
        avg_return=("future_return", "mean"),
        total_return=("future_return", "sum"),
        win_rate=("label", "mean"),  # % of trades that were profitable
    ).reset_index()

    wallet_stats = wallet_stats.sort_values("avg_return", ascending=False)

    # --- Monitoring: show top wallets ---
    top_wallets = wallet_stats.head(SMART_MONEY_TOP_N)
    logger.info(
        f"\n=== Top {SMART_MONEY_TOP_N} Profitable Wallets ===\n"
        f"{top_wallets.to_string(index=False)}"
    )

    bottom_wallets = wallet_stats.tail(3)
    logger.info(
        f"\n=== Bottom 3 Wallets (for contrast) ===\n"
        f"{bottom_wallets.to_string(index=False)}"
    )

    return wallet_stats


def add_smart_money_signal(
    df: pd.DataFrame,
    wallet_stats: pd.DataFrame
) -> pd.DataFrame:
    """
    Add a "smart_money_signal" feature to the dataset.
    
    The signal = 1 if any top-N wallet traded in the recent lookback window.
    
    Intuition: if smart money is active nearby, our confidence in a BUY
    signal should increase.
    """
    df = df.copy()

    # Identify smart money wallets
    smart_wallets = set(
        wallet_stats.head(SMART_MONEY_TOP_N)["wallet_id"].tolist()
    )
    logger.info(f"Smart money wallets: {smart_wallets}")

    # Mark rows where smart money traded
    df["is_smart_money"] = df["wallet_id"].isin(smart_wallets).astype(int)

    # Rolling signal: was smart money active in recent window?
    df["smart_money_signal"] = (
        df["is_smart_money"]
        .rolling(window=SMART_MONEY_LOOKBACK, min_periods=1)
        .max()  # 1 if ANY smart money trade in window
    )

    # --- Monitoring ---
    smart_pct = df["smart_money_signal"].mean()
    logger.info(
        f"Smart money signal active in {smart_pct:.1%} of timestamps"
    )

    # Show correlation between smart money and future returns
    corr = df["smart_money_signal"].corr(df["future_return"])
    logger.info(
        f"Correlation(smart_money_signal, future_return) = {corr:.4f}"
    )

    return df


if __name__ == "__main__":
    from data_ingestion import generate_simulated_data
    from feature_engineering import engineer_features
    from labels import create_labels

    df = generate_simulated_data()
    df = engineer_features(df)
    df = create_labels(df)

    wallet_stats = compute_wallet_profitability(df)
    df = add_smart_money_signal(df, wallet_stats)

    print("\n=== Smart Money Signal Distribution ===")
    print(df["smart_money_signal"].value_counts())
