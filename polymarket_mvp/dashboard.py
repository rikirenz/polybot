"""
=============================================================================
STEP 7C: METRICS DASHBOARD
=============================================================================

Simple visualization layer using matplotlib.
Plots:
1. Cumulative PnL over time — are we making money?
2. Number of signals over time — is the model active?
3. Prediction distribution — is the model well-calibrated?
4. Price chart with buy signals overlaid

In production, this would be Grafana/Streamlit. For the MVP, static plots
saved to disk are sufficient and don't require a running server.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from monitoring import SignalTracker, MetricsCollector, get_logger

logger = get_logger("Dashboard")


def plot_dashboard(
    tracker: SignalTracker,
    metrics: MetricsCollector,
    test_df: pd.DataFrame,
    save_path: str = "/app/output/dashboard.png"
):
    """
    Generate a 4-panel dashboard showing strategy performance.
    """
    logger.info("Generating dashboard plots...")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Polymarket MVP — Strategy Dashboard", fontsize=14, fontweight="bold")

    # --- Panel 1: Cumulative PnL ---
    ax1 = axes[0, 0]
    if metrics.cumulative_pnl:
        ax1.plot(metrics.cumulative_pnl, color="green", linewidth=1.5)
        ax1.axhline(y=0, color="red", linestyle="--", alpha=0.5)
        ax1.fill_between(
            range(len(metrics.cumulative_pnl)),
            metrics.cumulative_pnl,
            alpha=0.1, color="green"
        )
    ax1.set_title("Cumulative PnL ($)")
    ax1.set_xlabel("Trade #")
    ax1.set_ylabel("PnL ($)")
    ax1.grid(True, alpha=0.3)

    # --- Panel 2: Signals Over Time ---
    ax2 = axes[0, 1]
    if metrics.signal_timestamps:
        ax2.hist(metrics.signal_timestamps, bins=30, color="steelblue", alpha=0.7)
    ax2.set_title("Signal Distribution Over Time")
    ax2.set_xlabel("Timestamp")
    ax2.set_ylabel("Number of Signals")
    ax2.grid(True, alpha=0.3)

    # --- Panel 3: Prediction Distribution ---
    ax3 = axes[1, 0]
    if metrics.predictions:
        buy_preds = [p for p in metrics.predictions if p > 0.55]
        hold_preds = [s.prediction for s in tracker.signals if s.decision == "HOLD"]

        ax3.hist(hold_preds, bins=30, alpha=0.5, label="HOLD", color="gray")
        ax3.hist(buy_preds, bins=30, alpha=0.7, label="BUY", color="green")
        ax3.axvline(x=0.55, color="red", linestyle="--", label="Threshold")
        ax3.legend()
    ax3.set_title("Prediction Distribution")
    ax3.set_xlabel("Predicted Probability")
    ax3.set_ylabel("Count")
    ax3.grid(True, alpha=0.3)

    # --- Panel 4: Price + Buy Signals ---
    ax4 = axes[1, 1]
    ax4.plot(test_df["timestamp"], test_df["price"], color="black", linewidth=0.8, label="Price")

    # Overlay buy signals
    buy_signals = [s for s in tracker.signals if s.decision == "BUY"]
    if buy_signals:
        buy_ts = [s.timestamp for s in buy_signals]
        buy_prices = test_df[test_df["timestamp"].isin(buy_ts)]["price"]
        buy_timestamps = test_df[test_df["timestamp"].isin(buy_ts)]["timestamp"]
        ax4.scatter(buy_timestamps, buy_prices, color="green", marker="^",
                   s=20, alpha=0.6, label="BUY signal")

    ax4.set_title("Price Chart with Buy Signals")
    ax4.set_xlabel("Timestamp")
    ax4.set_ylabel("Price")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    logger.info(f"Dashboard saved to: {save_path}")
    plt.close()

    return save_path


def plot_multi_slug_dashboard(
    results_df: pd.DataFrame,
    save_path: str = "/app/output/multi_slug_dashboard.png"
):
    """
    Plot multi-market performance as bar charts plus a summary table.
    """
    logger.info("Generating multi-slug dashboard plots...")

    if results_df.empty:
        raise ValueError("Cannot plot multi-slug dashboard: results_df is empty")

    df = results_df.copy()
    for col in ["total_pnl", "win_rate", "total_trades", "rows_fetched"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    successful = df[df.get("status", "ok") == "ok"].copy()

    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.2])

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, :])

    fig.suptitle("Polymarket MVP - Multi-Slug Performance", fontsize=14, fontweight="bold")

    if not successful.empty:
        ranked_pnl = successful.sort_values("total_pnl", ascending=False)
        ax1.bar(ranked_pnl["market_slug"], ranked_pnl["total_pnl"], color="seagreen", alpha=0.8)
        ax1.set_title("Total PnL by Market")
        ax1.set_ylabel("PnL ($)")
        ax1.tick_params(axis="x", labelrotation=35)
        ax1.grid(True, axis="y", alpha=0.3)

        ranked_wr = successful.sort_values("win_rate", ascending=False)
        ax2.bar(ranked_wr["market_slug"], ranked_wr["win_rate"] * 100, color="royalblue", alpha=0.8)
        ax2.set_title("Win Rate by Market")
        ax2.set_ylabel("Win Rate (%)")
        ax2.tick_params(axis="x", labelrotation=35)
        ax2.grid(True, axis="y", alpha=0.3)
    else:
        ax1.text(0.5, 0.5, "No successful runs", ha="center", va="center")
        ax1.set_axis_off()
        ax2.text(0.5, 0.5, "No successful runs", ha="center", va="center")
        ax2.set_axis_off()

    ax3.set_axis_off()
    display_cols = [
        col for col in [
            "market_slug", "status", "rows_fetched", "total_signals",
            "total_trades", "win_rate", "total_pnl", "avg_pnl_per_trade"
        ] if col in df.columns
    ]

    table_df = df[display_cols].copy()
    if "win_rate" in table_df.columns:
        table_df["win_rate"] = (table_df["win_rate"] * 100).map(lambda x: f"{x:.1f}%" if pd.notna(x) else "-")
    if "total_pnl" in table_df.columns:
        table_df["total_pnl"] = table_df["total_pnl"].map(lambda x: f"${x:,.2f}" if pd.notna(x) else "-")
    if "avg_pnl_per_trade" in table_df.columns:
        table_df["avg_pnl_per_trade"] = table_df["avg_pnl_per_trade"].map(
            lambda x: f"${x:,.2f}" if pd.notna(x) else "-"
        )

    table = ax3.table(
        cellText=table_df.values,
        colLabels=table_df.columns,
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    logger.info(f"Multi-slug dashboard saved to: {save_path}")
    plt.close()

    return save_path
