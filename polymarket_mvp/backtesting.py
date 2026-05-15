"""
=============================================================================
STEP 5: BACKTESTING ENGINE
=============================================================================

HOW A TRADING STRATEGY IS DERIVED FROM PREDICTIONS:

The model outputs a probability: P(price goes up in next T steps).
The strategy converts this into a decision:

  IF predicted_probability > threshold (0.55) → BUY
  ELSE → HOLD (do nothing)

WHY 0.55 AND NOT 0.50?
- At 0.50, you'd trade on every coin-flip signal (too many trades, fees eat you)
- Higher threshold = fewer but higher-conviction trades
- 0.55 means "I'm at least 55% confident this goes up" — a reasonable bar

THE BACKTEST LOOP:
For each time step in the test set:
1. Model makes a prediction
2. If prediction > threshold → simulate buying
3. Record the ACTUAL outcome (did price go up?)
4. Compute PnL for that trade
5. Track everything for analysis

WHY BACKTESTING MATTERS:
A model with 60% accuracy can still LOSE money if:
- It's wrong on big moves and right on small ones
- Transaction costs eat the edge
- It trades too frequently

The backtest tells you: "Given this model, would you actually make money?"

MONITORING:
Every trade is logged with full context (prediction, actual outcome, PnL).
This is your audit trail — essential for debugging and improving the strategy.
"""

import pandas as pd
import numpy as np
from monitoring import get_logger, TradeSignal, SignalTracker, MetricsCollector
from config import BUY_THRESHOLD, POSITION_SIZE
from model import FEATURE_COLS

logger = get_logger("Backtesting")


def run_backtest(
    test_df: pd.DataFrame,
    model,
    feature_cols: list[str] = None,
    smart_money_available: bool = False,
) -> tuple[SignalTracker, MetricsCollector]:
    """
    Simulate trading on historical data using model predictions.
    
    This is a VECTORIZED backtest for speed, but we log each trade
    individually for observability.
    """
    if feature_cols is None:
        feature_cols = FEATURE_COLS.copy()
        if smart_money_available and "smart_money_signal" in test_df.columns:
            feature_cols.append("smart_money_signal")

    tracker = SignalTracker()
    metrics = MetricsCollector()

    logger.info(
        f"Starting backtest: {len(test_df)} steps, "
        f"threshold={BUY_THRESHOLD}, position_size=${POSITION_SIZE}"
    )

    # Get predictions
    X = test_df[feature_cols]
    predictions = model.predict_proba(X)[:, 1]

    # --- Trade simulation loop ---
    trades = 0
    wins = 0
    total_pnl = 0.0

    for i in range(len(test_df)):
        row = test_df.iloc[i]
        pred = predictions[i]
        actual_return = row.get("future_return", 0)

        # Decision logic
        if pred > BUY_THRESHOLD:
            decision = "BUY"
            # PnL = position_size * actual_return
            pnl = POSITION_SIZE * actual_return
            trades += 1
            total_pnl += pnl
            if pnl > 0:
                wins += 1

            # Record metrics
            metrics.record_pnl(pnl)
            metrics.record_signal(int(row["timestamp"]), pred)
        else:
            decision = "HOLD"
            pnl = 0.0

        # Determine which features contributed most to this prediction
        top_features = {}
        if decision == "BUY":
            feature_values = {col: row[col] for col in feature_cols}
            # Sort by absolute value (most extreme = most influential)
            sorted_features = sorted(
                feature_values.items(), key=lambda x: abs(x[1]), reverse=True
            )
            top_features = dict(sorted_features[:3])

        # Record signal
        signal = TradeSignal(
            timestamp=int(row["timestamp"]),
            prediction=pred,
            decision=decision,
            actual_return=actual_return if decision == "BUY" else None,
            pnl=pnl if decision == "BUY" else None,
            top_features=top_features,
            smart_money_active=(
                bool(row.get("smart_money_signal", 0))
                if smart_money_available else False
            ),
        )
        tracker.record(signal)

    # --- Summary ---
    win_rate = wins / trades if trades > 0 else 0
    avg_pnl = total_pnl / trades if trades > 0 else 0

    logger.info("\n" + "=" * 60)
    logger.info("BACKTEST RESULTS")
    logger.info("=" * 60)
    logger.info(f"  Total trades:     {trades}")
    logger.info(f"  Winning trades:   {wins}")
    logger.info(f"  Win rate:         {win_rate:.1%}")
    logger.info(f"  Total PnL:        ${total_pnl:.2f}")
    logger.info(f"  Average PnL/trade: ${avg_pnl:.2f}")
    logger.info(f"  Position size:    ${POSITION_SIZE}")
    logger.info("=" * 60)

    # Log sample trades for debugging
    buy_signals = [s for s in tracker.signals if s.decision == "BUY"]
    if buy_signals:
        logger.info("\n=== Sample Trades (first 5) ===")
        for signal in buy_signals[:5]:
            logger.info(
                f"  ts={signal.timestamp} pred={signal.prediction:.4f} "
                f"actual={signal.actual_return:.4f} pnl=${signal.pnl:.2f} "
                f"smart_money={signal.smart_money_active} "
                f"top_features={signal.top_features}"
            )

    # Log metrics summary
    metrics.log_summary()

    return tracker, metrics


if __name__ == "__main__":
    from data_ingestion import generate_simulated_data
    from feature_engineering import engineer_features
    from labels import create_labels
    from model import train_model

    df = generate_simulated_data()
    df = engineer_features(df)
    df = create_labels(df)
    model, test_df, importance = train_model(df)
    tracker, metrics = run_backtest(test_df, model)

    print("\n=== Signal Summary ===")
    print(tracker.summary())
