"""
=============================================================================
STEP 3: LABEL DEFINITION
=============================================================================

WHAT WE ARE PREDICTING AND WHY:

We predict: "Will the price go UP in the next T steps?"

This is a BINARY CLASSIFICATION problem:
  - Label = 1: price increases over next T steps (profitable to buy now)
  - Label = 0: price stays flat or decreases (don't buy)

WHY BINARY (not regression)?
1. Simpler to learn — the model doesn't need to predict exact magnitude
2. Maps directly to a trading decision: BUY or HOLD
3. More robust to noise — small price fluctuations don't flip the label

WHY T=5 STEPS AHEAD?
- Too short (T=1): dominated by noise, hard to profit after fees
- Too long (T=50): too many confounders, signal decays
- T=5 is a sweet spot for short-term momentum strategies

THE FORWARD RETURN:
  future_return[t] = (price[t+T] - price[t]) / price[t]
  label[t] = 1 if future_return[t] > threshold else 0

CRITICAL: The label uses FUTURE data. This is fine for training labels
(we're defining what we want to predict), but features must NEVER use
future data. This asymmetry is the foundation of supervised learning
for trading.
"""

import pandas as pd
import numpy as np
from monitoring import get_logger
from config import FORWARD_RETURN_STEPS, LABEL_THRESHOLD

logger = get_logger("Labels")


def create_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create forward-looking labels for supervised learning.
    
    The label answers: "If I buy now, will I make money in T steps?"
    """
    df = df.copy()
    logger.info(
        f"Creating labels: forward_steps={FORWARD_RETURN_STEPS}, "
        f"threshold={LABEL_THRESHOLD}"
    )

    # --- Forward return: what WILL happen ---
    df["future_return"] = df["price"].shift(-FORWARD_RETURN_STEPS) / df["price"] - 1

    # --- Binary label ---
    df["label"] = (df["future_return"] > LABEL_THRESHOLD).astype(int)

    # --- Drop rows where we can't compute forward return ---
    initial_len = len(df)
    df = df.dropna(subset=["future_return"]).reset_index(drop=True)
    dropped = initial_len - len(df)

    # --- Debug: label distribution ---
    label_counts = df["label"].value_counts()
    label_pct = df["label"].value_counts(normalize=True)

    logger.info(f"Dropped {dropped} rows (no future data available)")
    logger.info(
        f"Label distribution:\n"
        f"  Class 0 (don't buy): {label_counts.get(0, 0)} "
        f"({label_pct.get(0, 0):.1%})\n"
        f"  Class 1 (buy):       {label_counts.get(1, 0)} "
        f"({label_pct.get(1, 0):.1%})"
    )

    # Check for severe imbalance
    minority_pct = label_pct.min()
    if minority_pct < 0.3:
        logger.warning(
            f"Label imbalance detected ({minority_pct:.1%} minority). "
            f"Consider adjusting threshold or using class weights."
        )

    return df


if __name__ == "__main__":
    from data_ingestion import generate_simulated_data
    from feature_engineering import engineer_features

    df = generate_simulated_data()
    df = engineer_features(df)
    df = create_labels(df)

    print("\n=== Label Statistics ===")
    print(f"Future return stats:\n{df['future_return'].describe()}")
    print(f"\nLabel value counts:\n{df['label'].value_counts()}")
