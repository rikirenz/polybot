"""
Data ingestion module.

Responsible for:
- Fetching markets from Gamma API
- Fetching trades from Data API
- Parsing raw JSON into validated domain models
- Checkpointing for resumable ingestion

No business logic here — just fetch, parse, persist.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from src.schemas import (
    IngestionCheckpoint,
    Market,
    Trade,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Parsing: Gamma API markets
# ---------------------------------------------------------------------------


def parse_markets_response(
    raw: dict,
) -> tuple[list[Market], str | None]:
    """
    Parse a Gamma API GET /markets response into Market objects.

    Returns (markets, next_cursor). Malformed entries are skipped
    with a warning log, not raised as exceptions.
    """
    markets: list[Market] = []
    cursor = raw.get("next_cursor")

    for item in raw.get("markets", []):
        try:
            market = Market(
                condition_id=item["conditionId"],
                question=item["question"],
                slug=item["slug"],
                active=item["active"],
                closed=item["closed"],
                end_date=item.get("endDate"),
                volume=item["volume"],
                outcomes=item["outcomes"],
                outcome_prices=item["outcomePrices"],
            )
            markets.append(market)
        except (KeyError, ValueError) as e:
            logger.warning(
                "skipping_malformed_market",
                error=str(e),
                raw_item=item,
            )

    return markets, cursor


# ---------------------------------------------------------------------------
# Parsing: Data API trades
# ---------------------------------------------------------------------------


def parse_trades_response(raw: list[dict]) -> list[Trade]:
    """
    Parse a Data API GET /trades response (plain array) into Trade objects.

    Malformed entries are skipped with a warning log.
    """
    trades: list[Trade] = []

    for item in raw:
        try:
            trade = Trade(
                proxy_wallet=item["proxyWallet"],
                side=item["side"],
                asset=item["asset"],
                condition_id=item["conditionId"],
                size=item["size"],
                price=item["price"],
                timestamp=item["timestamp"],
                title=item["title"],
                slug=item["slug"],
                event_slug=item["eventSlug"],
                outcome=item["outcome"],
                outcome_index=item["outcomeIndex"],
                transaction_hash=item["transactionHash"],
                name=item.get("name", ""),
                pseudonym=item.get("pseudonym", ""),
            )
            trades.append(trade)
        except (KeyError, ValueError) as e:
            logger.warning(
                "skipping_malformed_trade",
                error=str(e),
                raw_item=item,
            )

    return trades


# ---------------------------------------------------------------------------
# Checkpointing: resumable ingestion
# ---------------------------------------------------------------------------


def save_checkpoint(
    checkpoint: IngestionCheckpoint, storage_path: Path
) -> None:
    """Persist a checkpoint to disk as JSON."""
    storage_path.mkdir(parents=True, exist_ok=True)
    file = storage_path / f"{checkpoint.market_condition_id}.json"
    file.write_text(checkpoint.model_dump_json())


def load_checkpoint(
    market_condition_id: str, storage_path: Path
) -> IngestionCheckpoint | None:
    """Load a checkpoint from disk. Returns None if no prior run."""
    file = storage_path / f"{market_condition_id}.json"
    if not file.exists():
        return None
    return IngestionCheckpoint.model_validate_json(file.read_text())
