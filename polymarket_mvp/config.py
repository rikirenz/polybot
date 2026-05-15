"""
Configuration constants for the Polymarket MVP trading system.
Centralized here so every module shares the same parameters.
"""

# === Data Ingestion ===
NUM_TIMESTAMPS = 2000          # Number of simulated time steps
NUM_WALLETS = 50               # Number of simulated wallets
PRICE_START = 0.50             # Starting price (Polymarket prices are 0-1)
PRICE_DRIFT = 0.0001           # Slight upward drift (simulates trending market)
PRICE_VOLATILITY = 0.02        # Per-step volatility
POLYMARKET_MAX_TRADES = 5000   # Max rows pulled from data-api /trades
ALLOW_SIMULATED_FALLBACK = False  # Keep False to force real-data training by default

# === Feature Engineering ===
MOMENTUM_WINDOW = 10           # Look-back for momentum (returns over N steps)
VOLUME_WINDOW = 10             # Rolling window for volume aggregation
VOLATILITY_WINDOW = 10         # Rolling window for volatility

# === Label Definition ===
FORWARD_RETURN_STEPS = 5       # How far ahead we predict (T steps)
LABEL_THRESHOLD = 0.0          # Binary label: 1 if future return > threshold

# === Model Training ===
TEST_SIZE = 0.25               # Train/test split ratio
RANDOM_STATE = 42              # Reproducibility

# === Backtesting ===
BUY_THRESHOLD = 0.55           # Predicted probability threshold to enter trade
POSITION_SIZE = 100.0          # Dollars per trade (fixed sizing for MVP)

# === Wallet Tracking ===
SMART_MONEY_TOP_N = 5          # Number of top wallets to track
SMART_MONEY_LOOKBACK = 20      # Steps to look back for smart money activity

# === Monitoring ===
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
