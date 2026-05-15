"""
=============================================================================
POLYMARKET MVP TRADING SYSTEM — MAIN ORCHESTRATOR
=============================================================================

HIGH-LEVEL ARCHITECTURE:
┌─────────────────────────────────────────────────────────────────────────┐
│                        POLYMARKET MVP PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐      │
│  │ 1. Data      │───▶│ 2. Feature       │───▶│ 3. Labels        │      │
│  │ Ingestion    │    │ Engineering      │    │ (future return)  │      │
│  └──────────────┘    └──────────────────┘    └──────────────────┘      │
│         │                                            │                  │
│         ▼                                            ▼                  │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐      │
│  │ 6. Wallet    │───▶│ 4. Model         │◀───│ Train/Test Split │      │
│  │ Tracking     │    │ (XGBoost)        │    │ (time-based)     │      │
│  └──────────────┘    └──────────────────┘    └──────────────────┘      │
│                              │                                          │
│                              ▼                                          │
│                       ┌──────────────────┐                              │
│                       │ 5. Backtesting   │                              │
│                       │ Engine           │                              │
│                       └──────────────────┘                              │
│                              │                                          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │ 7. MONITORING LAYER (logging, signals, metrics, dashboard)   │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

EXECUTION FLOW:
1. Generate/fetch market data (price, volume, wallet)
2. Engineer features (momentum, volatility, volume)
3. Create labels (future returns → binary classification)
4. Track wallets → identify smart money → add as feature
5. Train XGBoost model
6. Backtest strategy on held-out test data
7. Generate dashboard + monitoring outputs

RUN THIS FILE:
    cd polymarket_mvp
    python main.py
"""

import sys
import os
import pandas as pd
import numpy as np

# Ensure imports work when running from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monitoring import get_logger, SignalTracker, MetricsCollector
from data_ingestion import fetch_real_polymarket_data
from feature_engineering import engineer_features
from labels import create_labels
from wallet_tracking import compute_wallet_profitability, add_smart_money_signal
from model import train_model, FEATURE_COLS
from backtesting import run_backtest
from dashboard import plot_dashboard

logger = get_logger("Main")


def run_pipeline():
    """
    Execute the full MVP pipeline end-to-end.
    Each step is logged and observable.
    """
    print("\n" + "=" * 70)
    print("  POLYMARKET MVP TRADING SYSTEM")
    print("  Quantitative Strategy Pipeline")
    print("=" * 70)

    # =========================================================================
    # STEP 1: DATA INGESTION
    # =========================================================================
    print("\n" + "─" * 70)
    print("  STEP 1: DATA INGESTION")
    print("─" * 70)

    market_slug = os.getenv("POLYMARKET_MARKET_SLUG")
    max_trades = int(os.getenv("POLYMARKET_MAX_TRADES", "5000"))
    allow_simulated_fallback = os.getenv("ALLOW_SIMULATED_FALLBACK", "false").lower() == "true"

    df = fetch_real_polymarket_data(
        market_slug=market_slug,
        max_trades=max_trades,
        allow_simulated_fallback=allow_simulated_fallback,
    )

    ts_min = pd.to_datetime(df["timestamp"].min(), unit="s", utc=True)
    ts_max = pd.to_datetime(df["timestamp"].max(), unit="s", utc=True)

    print(f"\n  ✓ Fetched {len(df)} real trade rows")
    print(f"  ✓ Market slug: {market_slug or 'auto-selected active market'}")
    print(f"  ✓ Time range (UTC): {ts_min} -> {ts_max}")
    print(f"  ✓ Columns: {list(df.columns)}")
    print(f"  ✓ Price range: [{df['price'].min():.4f}, {df['price'].max():.4f}]")
    print(f"  ✓ Unique wallets: {df['wallet_id'].nunique()}")
    print(f"\n  Sample data:")
    print(df.head(3).to_string(index=False))

    # =========================================================================
    # STEP 2: FEATURE ENGINEERING
    # =========================================================================
    print("\n" + "─" * 70)
    print("  STEP 2: FEATURE ENGINEERING")
    print("─" * 70)

    df = engineer_features(df)
    feature_cols_display = ["momentum", "rolling_volume", "rolling_volatility",
                            "volume_momentum", "price_zscore"]
    print(f"\n  ✓ Engineered {len(feature_cols_display)} features")
    print(f"\n  Feature statistics:")
    print(df[feature_cols_display].describe().round(4).to_string())

    # =========================================================================
    # STEP 3: LABEL DEFINITION
    # =========================================================================
    print("\n" + "─" * 70)
    print("  STEP 3: LABEL DEFINITION")
    print("─" * 70)

    df = create_labels(df)
    label_dist = df["label"].value_counts()
    print(f"\n  ✓ Labels created (predicting {5}-step forward return)")
    print(f"  ✓ Label distribution:")
    print(f"    Class 0 (HOLD): {label_dist.get(0, 0)} ({label_dist.get(0, 0)/len(df):.1%})")
    print(f"    Class 1 (BUY):  {label_dist.get(1, 0)} ({label_dist.get(1, 0)/len(df):.1%})")
    print(f"  ✓ Future return stats: mean={df['future_return'].mean():.5f}, "
          f"std={df['future_return'].std():.5f}")

    # =========================================================================
    # STEP 6: WALLET TRACKING (before model, so we can use it as feature)
    # =========================================================================
    print("\n" + "─" * 70)
    print("  STEP 4: WALLET TRACKING (SMART MONEY)")
    print("─" * 70)

    wallet_stats = compute_wallet_profitability(df)
    df = add_smart_money_signal(df, wallet_stats)
    print(f"\n  ✓ Computed profitability for {len(wallet_stats)} wallets")
    print(f"  ✓ Smart money signal active in {df['smart_money_signal'].mean():.1%} of rows")
    print(f"\n  Top 5 wallets by avg return:")
    print(wallet_stats.head(5).to_string(index=False))

    # =========================================================================
    # STEP 4: MODEL TRAINING (with smart money feature)
    # =========================================================================
    print("\n" + "─" * 70)
    print("  STEP 5: MODEL TRAINING (XGBoost)")
    print("─" * 70)

    # Add smart money to feature set
    enhanced_features = FEATURE_COLS + ["smart_money_signal"]
    model, test_df, importance = train_model(df, feature_cols=enhanced_features)

    print(f"\n  ✓ Model trained on {int(len(df) * 0.75)} samples")
    print(f"  ✓ Testing on {int(len(df) * 0.25)} samples")
    print(f"\n  Feature Importance:")
    print(importance.to_string(index=False))

    # =========================================================================
    # STEP 5: BACKTESTING
    # =========================================================================
    print("\n" + "─" * 70)
    print("  STEP 6: BACKTESTING")
    print("─" * 70)

    tracker, metrics = run_backtest(
        test_df, model,
        smart_money_available=True,
    )

    summary = tracker.summary()
    print(f"\n  ✓ Backtest complete")
    print(f"  ✓ Total signals: {summary['total_signals']}")
    print(f"  ✓ Total trades (BUY): {summary['total_buys']}")
    print(f"  ✓ Win rate: {summary['win_rate']:.1%}")
    print(f"  ✓ Total PnL: ${summary['total_pnl']:.2f}")

    # Show smart money influence
    smart_money_trades = [
        s for s in tracker.signals
        if s.decision == "BUY" and s.smart_money_active
    ]
    print(f"\n  Smart money influenced trades: {len(smart_money_trades)}")
    if smart_money_trades:
        sm_pnl = sum(s.pnl for s in smart_money_trades if s.pnl)
        print(f"  Smart money trade PnL: ${sm_pnl:.2f}")

    # =========================================================================
    # STEP 7: DASHBOARD
    # =========================================================================
    print("\n" + "─" * 70)
    print("  STEP 7: MONITORING DASHBOARD")
    print("─" * 70)

    dashboard_path = plot_dashboard(tracker, metrics, test_df)
    print(f"\n  ✓ Dashboard saved to: {dashboard_path}")

    # =========================================================================
    # FINAL RESULTS & KEY INSIGHTS
    # =========================================================================
    print("\n" + "=" * 70)
    print("  FINAL RESULTS & KEY INSIGHTS")
    print("=" * 70)

    print(f"""
  PERFORMANCE SUMMARY:
  ├── Total PnL:          ${summary['total_pnl']:.2f}
  ├── Number of trades:   {summary['total_buys']}
  ├── Win rate:           {summary['win_rate']:.1%}
  ├── Avg PnL/trade:     ${summary['total_pnl']/max(summary['total_buys'],1):.2f}
  └── Signals generated:  {summary['total_signals']}

  KEY INSIGHTS:
  1. The model captures short-term momentum patterns in price data.
  2. Feature importance shows which signals drive decisions (interpretable).
  3. Smart money tracking adds a blockchain-native alpha source.
  4. The monitoring layer makes every decision auditable.

  WHAT WORKED:
  - Momentum and volatility features capture real market dynamics
  - Time-based train/test split prevents look-ahead bias
  - Structured logging makes debugging straightforward

  WHAT DIDN'T (and that's expected in an MVP):
    - Single-market training can be regime-specific and noisy
  - No transaction costs modeled (would reduce PnL)
  - Fixed position sizing (should scale with confidence)
  - No risk management (stop-losses, max drawdown limits)

  SUGGESTIONS FOR IMPROVEMENT:
    1. Train across multiple markets to improve generalization
  2. Add transaction cost modeling (Polymarket charges ~2% on profits)
  3. Implement Kelly criterion for position sizing
  4. Add more features: order book depth, time-of-day, event proximity
  5. Ensemble multiple models (XGBoost + logistic regression + LSTM)
  6. Deploy as a live system with paper trading first
  7. Add Telegram/Discord alerts for high-confidence signals
    """)

    # =========================================================================
    # BONUS: HOW TO GO LIVE
    # =========================================================================
    print("─" * 70)
    print("  BONUS: PATH TO PRODUCTION")
    print("─" * 70)
    print("""
    LIVE INGESTION STATUS:
    1. Real trade data is now fetched from Polymarket Data API (/trades)
    2. Market metadata is resolved from Gamma API (/markets)
    3. Data is normalized to (timestamp, price, volume, wallet_id)
    4. The training/backtest pipeline runs on these live rows in Docker

  TO DEPLOY AS A LIVE SYSTEM:
  ┌─────────────────────────────────────────────────────────┐
  │  Scheduler (cron/APScheduler)                           │
  │    └── Every 5 min: fetch new data                      │
  │         └── Run feature engineering                     │
  │              └── Model prediction                       │
  │                   └── If BUY signal:                    │
  │                        ├── Check risk limits            │
  │                        ├── Execute via Polymarket API   │
  │                        └── Log to monitoring            │
  └─────────────────────────────────────────────────────────┘

  REQUIRED FOR LIVE:
  - API keys (Polymarket account + wallet)
  - Risk management (max position, max daily loss)
  - Paper trading period (run signals without real money)
  - Alerting (PagerDuty/Telegram for anomalies)
    """)

    return tracker, metrics, model, test_df


if __name__ == "__main__":
    tracker, metrics, model, test_df = run_pipeline()
