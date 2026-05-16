# Polybot — Project Status

## What is this?

A classification model that identifies Polymarket wallets with consistent
contrarian edge — wallets that buy low-probability outcomes at cheap prices
and win big when the crowd is wrong. The goal is to replicate their strategy
at smaller scale.

## Edge Thesis

We want wallets that:
- Take large positions on **unlikely outcomes** (price 0.10–0.30)
- On **popular, high-volume markets**
- And are **right repeatedly** (not one-time lucky)

The payoff profile: lose small many times, win big when it hits.

---

## Current State

### Done ✅

| What | Files | Notes |
|------|-------|-------|
| Project skeleton | `Dockerfile`, `docker-compose.yml`, `pyproject.toml` | `docker compose run --rm testrunner` works |
| Config system | `src/config.py` | Env-var based, no hardcoded secrets |
| Data contracts | `src/schemas.py` | `Market`, `Trade`, `IngestionCheckpoint` — matches real API shapes |
| API reference doc | `docs/api_reference.md` | Documented actual Gamma/Data/CLOB API response formats |
| Ingestion parsing | `src/ingestion.py` | Parses raw API JSON → validated models, skips malformed data |
| Checkpointing | `src/ingestion.py` | Save/load offset-based checkpoints for resumable fetches |
| Tests (9 passing) | `tests/test_ingestion.py` | Parsing, normalization, error handling, checkpointing |
| Structured logging | `src/logging.py` | structlog setup, configurable level |

### Next Up 🔜

**Step 1b: HTTP client layer for ingestion**

The fetching strategy (agreed upon):

```
1. Fetch resolved markets from Gamma API
   GET gamma-api.polymarket.com/markets?closed=true&limit=100

2. Filter to "upset" markets — where the winning outcome was low-probability
   (winner's price was < 0.30 for most of the market's life)
   Use CLOB API GET /prices-history or infer from trade prices

3. For upset markets, find who held the winning side
   GET data-api.polymarket.com/holders?market=<conditionId>

4. For those wallets, fetch their full closed position history
   GET data-api.polymarket.com/closed-positions?user=<wallet>

5. Keep wallets that show a PATTERN of contrarian wins (not one-offs)

6. For kept wallets, fetch all their trades
   GET data-api.polymarket.com/trades?user=<wallet>
```

Implementation needs:
- httpx async client with retry (tenacity) and rate limiting
- Pagination handling (cursor for Gamma, offset for Data API)
- Resume from checkpoint on failure
- Store raw data to DB (staging table)

### Later Steps

| Step | Module | Description |
|------|--------|-------------|
| 2 | `wallet_tracking.py` | Per-wallet metrics: contrarian win rate, avg entry price vs resolution, consistency |
| 3 | `feature_engineering.py` | ML features: entry timing, position sizing, market selection patterns |
| 4 | `labels.py` | Binary label: "contrarian sharp wallet" vs noise |
| 5 | `model.py` | Classifier with time-series-aware splits |
| 6 | `backtesting.py` | Simulate following model signals at small scale |

---

## APIs We Use

| API | Base URL | Auth | Purpose |
|-----|----------|------|---------|
| Gamma API | `gamma-api.polymarket.com` | None | Market discovery (resolved, high-volume) |
| Data API | `data-api.polymarket.com` | None | Trades, positions, holders |
| CLOB API | `clob.polymarket.com` | None (public endpoints) | Price history |

---

## How to Run

```bash
# Run all tests
docker compose run --rm testrunner

# (Future) Run ingestion
docker compose run --rm ingestion
```

---

## Key Decisions Made

1. **TDD approach** — tests written before implementation
2. **Data API for trade history** (not CLOB API which requires auth for user trades)
3. **Contrarian edge thesis** — we specifically target wallets buying low-prob outcomes
4. **Offset pagination** for Data API, cursor pagination for Gamma API
5. **Checkpointing** — ingestion is resumable if interrupted
6. **Malformed data is skipped** with warning logs, not crashes
