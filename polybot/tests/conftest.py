"""
Shared test fixtures for polybot.

Provides deterministic sample data, mock API responses,
and database fixtures for fast, reproducible tests.
"""

from __future__ import annotations

import pytest
from src.schemas import Market, Trade, TradeDirection, IngestionCheckpoint
from src.config import AppConfig, DatabaseConfig, IngestionConfig


@pytest.fixture
def test_config() -> AppConfig:
    """App config suitable for testing (SQLite, fast settings)."""
    return AppConfig(
        db=DatabaseConfig(url="sqlite:///test_polybot.db"),
        ingestion=IngestionConfig(
            clob_api_base_url="https://clob.polymarket.com",
            max_requests_per_second=100.0,
            max_retries=1,
            batch_size=10,
            local_market_limit=5,
        ),
    )


@pytest.fixture
def sample_market_api_response() -> dict:
    """
    Raw JSON from Gamma API GET /markets (keyset pagination).
    Matches actual response shape documented in docs/api_reference.md.
    """
    return {
        "markets": [
            {
                "conditionId": "0xabc123def456",
                "question": "Will BTC exceed $100k by end of 2025?",
                "slug": "btc-100k-2025",
                "active": False,
                "closed": True,
                "endDate": "2025-12-31T00:00:00Z",
                "volume": "1500000.00",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.75","0.25"]',
            }
        ],
        "next_cursor": "cursor_abc123",
    }


@pytest.fixture
def sample_trades_api_response() -> list[dict]:
    """
    Raw JSON from Data API GET /trades.
    Note: response is a plain array, not wrapped in {data: ...}.
    Matches actual response shape documented in docs/api_reference.md.
    """
    return [
        {
            "proxyWallet": "0x6af75d4e4aaf700450efbac3708cce1665810ff1",
            "side": "BUY",
            "asset": "28774665463932631392072718054733378944250725021214679767633993409918492440355",
            "conditionId": "0xabc123def456",
            "size": 160.26,
            "price": 0.65,
            "timestamp": 1724210494,
            "title": "Will BTC exceed $100k by end of 2025?",
            "slug": "btc-100k-2025",
            "icon": "https://example.com/icon.png",
            "eventSlug": "btc-100k-2025-event",
            "outcome": "Yes",
            "outcomeIndex": 0,
            "name": "trader1",
            "pseudonym": "Sharp-Whale",
            "bio": "",
            "profileImage": "",
            "profileImageOptimized": "",
            "transactionHash": "0x5620f25e2772f0ec2c5b2f2f814f6e20b52b4363286a9043b62632418729c7f9",
        },
        {
            "proxyWallet": "0x58053ef6d4b8a7f1816397110284799e725cc2b8",
            "side": "SELL",
            "asset": "28774665463932631392072718054733378944250725021214679767633993409918492440355",
            "conditionId": "0xabc123def456",
            "size": 200.0,
            "price": 0.70,
            "timestamp": 1724210500,
            "title": "Will BTC exceed $100k by end of 2025?",
            "slug": "btc-100k-2025",
            "icon": "https://example.com/icon.png",
            "eventSlug": "btc-100k-2025-event",
            "outcome": "Yes",
            "outcomeIndex": 0,
            "name": "",
            "pseudonym": "Quiet-Otter",
            "bio": "",
            "profileImage": "",
            "profileImageOptimized": "",
            "transactionHash": "0xc98ead6ed4a8f9bb75e20babf150fcb137c3dcb9439358d18054bb519fe2448b",
        },
    ]
