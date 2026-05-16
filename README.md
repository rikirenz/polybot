# Polybot

Classification model that identifies Polymarket wallets with consistent contrarian edge — wallets that buy low-probability outcomes cheaply and win big when the crowd is wrong.

## Strategy

Find wallets that repeatedly take large positions on unlikely outcomes (price 0.10–0.30) in popular markets and are correct. Then replicate their strategy at smaller scale.

Payoff profile: lose small many times, win big when it hits.

## Project Structure

```
polybot/
├── src/
│   ├── config.py          # Env-var based configuration
│   ├── logging.py         # Structured logging (structlog)
│   ├── schemas.py         # Data contracts (Pydantic models)
│   ├── ingestion.py       # Parse API responses, checkpointing
│   └── client.py          # HTTP client (fetch markets, trades, holders)
├── tests/
│   ├── conftest.py        # Shared fixtures
│   ├── test_ingestion.py  # Parsing and checkpoint tests
│   └── test_client.py     # HTTP client tests (mocked)
├── docs/
│   └── api_reference.md   # Documented Polymarket API response shapes
├── Dockerfile
├── docker-compose.yml
├── requirements.txt       # Pinned dependencies
└── STATUS.md              # Current progress and next steps
```

## Running Tests

```bash
docker compose build testrunner
docker compose run --rm testrunner
```

## Configuration

All settings via environment variables. Defaults are set for local development.

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `local` | `local` or `cloud` |
| `DATABASE_URL` | `sqlite:///polybot.db` | DB connection string |
| `GAMMA_API_BASE_URL` | `https://gamma-api.polymarket.com` | Market discovery API |
| `DATA_API_BASE_URL` | `https://data-api.polymarket.com` | Trades/positions API |
| `MAX_REQUESTS_PER_SECOND` | `10.0` | Rate limit for API calls |
| `MAX_RETRIES` | `3` | Retry count on transient failures |
| `LOG_LEVEL` | `DEBUG` | Logging verbosity |
| `LOCAL_MARKET_LIMIT` | `10` | Markets to fetch in local mode |

## Pipeline Overview

1. **Ingestion** — Fetch resolved markets, find contrarian winners, pull their trades
2. **Wallet Tracking** — Compute per-wallet metrics (win rate, avg entry price, consistency)
3. **Feature Engineering** — Build ML features from trading patterns
4. **Labeling** — Define "contrarian sharp wallet" vs noise
5. **Model** — Train classifier with time-series-aware splits
6. **Backtesting** — Simulate following model signals at small scale
