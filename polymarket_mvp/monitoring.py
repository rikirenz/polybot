"""
=============================================================================
STEP 7: MONITORING / OBSERVABILITY LAYER
=============================================================================

WHY THIS EXISTS:
In any trading system, you need to answer "why did it do that?" at any point.
This module provides:
  A. Structured logging (not print statements — filterable, parseable)
  B. Signal tracking (which features drove a decision)
  C. Metrics collection (for the dashboard)

A trading system without observability is a black box that loses money silently.
We build this FIRST because every other module uses it.
"""

import logging
import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from config import LOG_LEVEL, LOG_FORMAT


# =============================================================================
# A. STRUCTURED LOGGING
# =============================================================================

def get_logger(name: str) -> logging.Logger:
    """
    Create a structured logger for a module.
    
    Why structured? Because when you're debugging why a trade fired at 3am,
    you want to grep logs by module, level, and content — not scroll through
    print() spaghetti.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, LOG_LEVEL))
    return logger


# =============================================================================
# B. SIGNAL TRACKING
# =============================================================================

@dataclass
class TradeSignal:
    """
    Immutable record of a trading decision.
    Every time the model says "buy" or "hold", we capture WHY.
    """
    timestamp: int
    prediction: float
    decision: str                    # "BUY" or "HOLD"
    actual_return: Optional[float] = None
    pnl: Optional[float] = None
    top_features: dict = field(default_factory=dict)
    smart_money_active: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class SignalTracker:
    """
    Collects all trade signals for post-hoc analysis.
    Think of this as the "flight recorder" for your strategy.
    """

    def __init__(self):
        self.signals: list[TradeSignal] = []
        self.logger = get_logger("SignalTracker")

    def record(self, signal: TradeSignal):
        self.signals.append(signal)
        self.logger.info(
            f"Signal recorded: ts={signal.timestamp} "
            f"pred={signal.prediction:.4f} decision={signal.decision} "
            f"smart_money={signal.smart_money_active}"
        )

    def summary(self) -> dict:
        if not self.signals:
            return {"total_signals": 0}

        buys = [s for s in self.signals if s.decision == "BUY"]
        wins = [s for s in buys if s.pnl and s.pnl > 0]

        return {
            "total_signals": len(self.signals),
            "total_buys": len(buys),
            "total_holds": len(self.signals) - len(buys),
            "win_rate": len(wins) / len(buys) if buys else 0,
            "total_pnl": sum(s.pnl for s in buys if s.pnl is not None),
        }


# =============================================================================
# C. METRICS COLLECTOR (feeds the dashboard)
# =============================================================================

class MetricsCollector:
    """
    Lightweight metrics store. In production you'd use Prometheus/Grafana.
    Here we just accumulate series for plotting.
    """

    def __init__(self):
        self.cumulative_pnl: list[float] = []
        self.signal_timestamps: list[int] = []
        self.predictions: list[float] = []
        self.logger = get_logger("Metrics")

    def record_pnl(self, pnl: float):
        running = (self.cumulative_pnl[-1] if self.cumulative_pnl else 0) + pnl
        self.cumulative_pnl.append(running)

    def record_signal(self, timestamp: int, prediction: float):
        self.signal_timestamps.append(timestamp)
        self.predictions.append(prediction)

    def log_summary(self):
        self.logger.info(
            f"Metrics summary: "
            f"final_pnl={self.cumulative_pnl[-1]:.2f} "
            f"total_signals={len(self.signal_timestamps)} "
            f"pred_mean={sum(self.predictions)/len(self.predictions):.4f}"
            if self.predictions else "No predictions recorded"
        )
