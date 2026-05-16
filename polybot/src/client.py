"""
HTTP client layer for Polymarket APIs.

Handles:
- Request construction and execution
- Retry with exponential backoff
- Rate limiting
- Pagination (cursor for Gamma, offset for Data API)

This module only does HTTP + pagination. Parsing into domain
models is delegated to src/ingestion.py.
"""

from __future__ import annotations

import asyncio

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config import IngestionConfig
from src.ingestion import parse_markets_response, parse_trades_response
from src.schemas import Market, Trade

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Low-level request helper (retry + rate limit)
# ---------------------------------------------------------------------------

# Module-level rate limit state
_last_request_time: float = 0.0


async def make_request(
    url: str,
    params: dict | None = None,
    config: IngestionConfig | None = None,
) -> httpx.Response:
    """
    Make a GET request with rate limiting and retry.

    This function is patched in tests to avoid real HTTP calls.
    """
    global _last_request_time

    if config:
        min_interval = 1.0 / config.max_requests_per_second
        now = asyncio.get_event_loop().time()
        elapsed = now - _last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        _last_request_time = asyncio.get_event_loop().time()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response


# ---------------------------------------------------------------------------
# Fetch resolved markets (Gamma API, cursor pagination)
# ---------------------------------------------------------------------------


async def fetch_tags(config: IngestionConfig) -> list[dict]:
    """
    Fetch available market tags/categories from Gamma API.

    Returns list of dicts with id, label, slug.
    Use the id to filter markets by category.
    """
    url = f"{config.gamma_api_base_url}/tags"
    response = await make_request(url, config=config)
    data = response.json()

    tags = [{"id": t["id"], "label": t["label"], "slug": t["slug"]} for t in data]
    logger.info("fetched_tags", count=len(tags))
    return tags


async def fetch_resolved_markets(
    config: IngestionConfig,
    limit: int = 100,
    tag_id: str | None = None,
    category: str | None = None,
) -> list[Market]:
    """
    Fetch closed/resolved markets from Gamma API.

    Args:
        config: Ingestion configuration.
        limit: Max number of markets to fetch.
        tag_id: Optional tag ID to filter server-side.
        category: Optional category to filter client-side
                  (e.g. "Crypto", "Sports", "US-current-affairs").

    Paginates via next_cursor until exhausted or limit reached.
    """
    all_markets: list[Market] = []
    cursor: str | None = None

    while len(all_markets) < limit:
        params = {"closed": "true", "limit": str(min(100, limit - len(all_markets)))}
        if tag_id:
            params["tag_id"] = tag_id
        if cursor:
            params["next_cursor"] = cursor

        url = f"{config.gamma_api_base_url}/markets"
        response = await make_request(url, params=params, config=config)
        data = response.json()

        markets, cursor = parse_markets_response(data)

        if category:
            markets = [m for m in markets if m.category == category]

        all_markets.extend(markets)

        if not cursor:
            break

    logger.info("fetched_resolved_markets", count=len(all_markets), tag_id=tag_id, category=category)
    return all_markets


# ---------------------------------------------------------------------------
# Fetch holders (Data API)
# ---------------------------------------------------------------------------


async def fetch_holders(
    market_condition_id: str, config: IngestionConfig
) -> list[dict]:
    """
    Fetch top holders for a market from Data API.

    Returns list of dicts with proxy_wallet, amount, outcome_index.
    """
    url = f"{config.data_api_base_url}/holders"
    params = {"market": market_condition_id}

    response = await make_request(url, params=params, config=config)
    data = response.json()

    holders = []
    for token_group in data:
        for holder in token_group.get("holders", []):
            holders.append({
                "proxy_wallet": holder["proxyWallet"].lower(),
                "amount": holder["amount"],
                "outcome_index": holder["outcomeIndex"],
            })

    logger.info(
        "fetched_holders",
        market=market_condition_id,
        count=len(holders),
    )
    return holders


# ---------------------------------------------------------------------------
# Fetch trades for a wallet (Data API, offset pagination)
# ---------------------------------------------------------------------------


async def fetch_trades_for_wallet(
    wallet_address: str, config: IngestionConfig
) -> list[Trade]:
    """
    Fetch all trades for a wallet from Data API.

    Paginates using offset until an empty page is returned.
    """
    all_trades: list[Trade] = []
    offset = 0
    batch_size = config.batch_size

    while True:
        url = f"{config.data_api_base_url}/trades"
        params = {
            "user": wallet_address,
            "limit": str(batch_size),
            "offset": str(offset),
        }

        response = await make_request(url, params=params, config=config)
        data = response.json()

        if not data:
            break

        trades = parse_trades_response(data)
        all_trades.extend(trades)
        offset += batch_size

        if len(data) < batch_size:
            break

    logger.info(
        "fetched_trades_for_wallet",
        wallet=wallet_address,
        count=len(all_trades),
    )
    return all_trades
