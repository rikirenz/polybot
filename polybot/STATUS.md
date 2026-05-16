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

## Current State (15 tests passing)

### Done ✅

| What | Files | Notes |
|------|-------|-------|
| Project skeleton | `Dockerfile`, `docker-compose.yml`, `pyproject.toml` | `docker compose run --rm testrunner` works |
| Config system | `src/config.py` | Env-var based, includes all 3 API base URLs |
| Data contracts | `src/schemas.py` | `Market` (with category), `Trade`, `IngestionCheckpoint` |
| API reference doc | `docs/api_reference.md` | Documented actual API response formats |
| Ingestion parsing | `src/ingestion.py` | Parses raw API JSON → validated models |
| Checkpointing | `src/ingestion.py` | Save/load offset-based checkpoints |
| HTTP client | `src/client.py` | Fetches markets, holders, trades, tags |
| Category filtering | `src/client.py` | Client-side filter (API doesn't support server-side) |
| Structured logging | `src/logging.py` | structlog setup |
| Tests | `tests/test_ingestion.py`, `tests/test_client.py` | 15 tests, all passing |

### API Findings (from hitting real endpoints)

- **Gamma API** `GET /markets?closed=true` — returns markets with a `category` field
- Categories found: `Crypto`, `Sports`, `Tech`, `US-current-affairs`, `Pop-Culture`, `Coronavirus`
- No server-side category filter — we filter client-side after fetch
- **Gamma API** `GET /tags` — only 50 niche tags, not useful for broad filtering
- **Data API** `GET /trades`, `/holders`, `/positions` — all public, no auth needed
- Pagination: Gamma uses `next_cursor`, Data API uses `offset`/`limit`

### Client Functions Available

```python
await fetch_tags(config)                                    # discover tags
await fetch_resolved_markets(config, limit=50, category="Crypto")  # filtered markets
await fetch_holders("0xconditionId", config)                # top holders per market
await fetch_trades_for_wallet("0xwallet", config)           # all trades for a wallet
```

---

## Next Up 🔜

**Step 1c: "Upset detection" — find markets where the unlikely outcome won**

Logic needed:
1. Take resolved markets (fetched above)
2. Look at `outcomePrices` — these are final prices (winner = ~1.0, loser = ~0.0)
3. But we need the HISTORICAL price to know if it was an upset
4. Options:
   - Use CLOB API `GET /prices-history?token=<id>` to get price over time
   - Or: fetch trades for the market and look at early trade prices
   - Simpler: if the winning outcome's final price is 1.0 but early trades
     were at 0.10-0.30, that's an upset

After upset detection:
- `GET /holders` on upset markets → find who held the winning (unlikely) side
- `GET /closed-positions` per wallet → check if they're consistently profitable
- `GET /trades` per profitable wallet → raw data for ML features

### Later Steps

| Step | Module | Description |
|------|--------|-------------|
| 2 | `wallet_tracking.py` | Per-wallet metrics: contrarian win rate, avg entry price, consistency |
| 3 | `feature_engineering.py` | ML features: entry timing, position sizing, market selection |
| 4 | `labels.py` | Binary label: "contrarian sharp wallet" vs noise |
| 5 | `model.py` | Classifier with time-series-aware splits |
| 6 | `backtesting.py` | Simulate following model signals at small scale |

---

## How to Run

```bash
# Run all tests
docker compose run --rm testrunner
```

---

## Key Decisions Made

1. **TDD approach** — tests before implementation, always
2. **Data API for trade history** (public, no auth needed)
3. **Contrarian edge thesis** — target wallets buying low-prob outcomes
4. **Client-side category filtering** — API doesn't support it server-side
5. **Offset pagination** for Data API, cursor for Gamma API
6. **Checkpointing** — ingestion is resumable if interrupted
7. **Malformed data is skipped** with warning logs, not crashes
