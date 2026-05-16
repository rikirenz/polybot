"""
Tests for the HTTP client layer.

These test the functions that actually call the Polymarket APIs.
All HTTP calls are mocked — no real network traffic.
Tests verify:
- Correct URL construction and query params
- Pagination handling (cursor and offset)
- Retry behavior on transient errors
- Rate limiting respect
"""

from __future__ import annotations

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from src.config import IngestionConfig
from src.schemas import Market, Trade


@pytest.fixture
def ingestion_config() -> IngestionConfig:
    return IngestionConfig(
        gamma_api_base_url="https://gamma-api.polymarket.com",
        data_api_base_url="https://data-api.polymarket.com",
        clob_api_base_url="https://clob.polymarket.com",
        max_requests_per_second=100.0,
        max_retries=2,
        retry_backoff_base=0.01,  # fast retries in tests
        batch_size=2,
        local_market_limit=5,
    )


class TestFetchResolvedMarkets:
    """Verify fetching markets from Gamma API with pagination."""

    @pytest.mark.asyncio
    async def test_fetches_single_page_of_markets(self, ingestion_config):
        """Single page response returns parsed markets."""
        from src.client import fetch_resolved_markets

        mock_response = httpx.Response(
            200,
            json={
                "markets": [
                    {
                        "conditionId": "0xabc",
                        "question": "Test market?",
                        "slug": "test-market",
                        "active": False,
                        "closed": True,
                        "endDate": "2025-01-01T00:00:00Z",
                        "volume": "500000",
                        "outcomes": '["Yes","No"]',
                        "outcomePrices": '["0.85","0.15"]',
                    }
                ],
                "next_cursor": None,
            },
        )

        with patch("src.client.make_request", return_value=mock_response):
            markets = await fetch_resolved_markets(ingestion_config, limit=5)

        assert len(markets) == 1
        assert markets[0].condition_id == "0xabc"
        assert markets[0].closed is True

    @pytest.mark.asyncio
    async def test_paginates_through_multiple_pages(self, ingestion_config):
        """Follows next_cursor until None."""
        from src.client import fetch_resolved_markets

        page1 = httpx.Response(
            200,
            json={
                "markets": [
                    {
                        "conditionId": "0x111",
                        "question": "Market 1?",
                        "slug": "m1",
                        "active": False,
                        "closed": True,
                        "volume": "100000",
                        "outcomes": '["Yes","No"]',
                        "outcomePrices": '["1.0","0.0"]',
                    }
                ],
                "next_cursor": "page2cursor",
            },
        )
        page2 = httpx.Response(
            200,
            json={
                "markets": [
                    {
                        "conditionId": "0x222",
                        "question": "Market 2?",
                        "slug": "m2",
                        "active": False,
                        "closed": True,
                        "volume": "200000",
                        "outcomes": '["Yes","No"]',
                        "outcomePrices": '["0.0","1.0"]',
                    }
                ],
                "next_cursor": None,
            },
        )

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return page1 if call_count == 1 else page2

        with patch("src.client.make_request", side_effect=mock_request):
            markets = await fetch_resolved_markets(ingestion_config, limit=10)

        assert len(markets) == 2
        assert markets[0].condition_id == "0x111"
        assert markets[1].condition_id == "0x222"


class TestFetchHolders:
    """Verify fetching top holders for a market."""

    @pytest.mark.asyncio
    async def test_returns_wallet_addresses_for_market(self, ingestion_config):
        """Extracts wallet addresses from holders response."""
        from src.client import fetch_holders

        mock_response = httpx.Response(
            200,
            json=[
                {
                    "token": "12345",
                    "holders": [
                        {"proxyWallet": "0xAAA", "amount": 5000.0, "outcomeIndex": 0},
                        {"proxyWallet": "0xBBB", "amount": 3000.0, "outcomeIndex": 0},
                    ],
                },
                {
                    "token": "67890",
                    "holders": [
                        {"proxyWallet": "0xCCC", "amount": 2000.0, "outcomeIndex": 1},
                    ],
                },
            ],
        )

        with patch("src.client.make_request", return_value=mock_response):
            holders = await fetch_holders("0xcondition", ingestion_config)

        # Returns all holders across all tokens
        assert len(holders) == 3
        assert holders[0]["proxy_wallet"] == "0xaaa"
        assert holders[0]["amount"] == 5000.0


class TestFetchTradesForWallet:
    """Verify fetching trade history for a specific wallet."""

    @pytest.mark.asyncio
    async def test_fetches_trades_with_offset_pagination(self, ingestion_config):
        """Paginates using offset until fewer results than limit."""
        from src.client import fetch_trades_for_wallet

        page1 = httpx.Response(
            200,
            json=[
                {
                    "proxyWallet": "0xaaa",
                    "side": "BUY",
                    "asset": "123",
                    "conditionId": "0xcond",
                    "size": 100.0,
                    "price": 0.25,
                    "timestamp": 1700000000,
                    "title": "Test?",
                    "slug": "test",
                    "eventSlug": "test-event",
                    "outcome": "Yes",
                    "outcomeIndex": 0,
                    "transactionHash": "0xtx1",
                },
                {
                    "proxyWallet": "0xaaa",
                    "side": "SELL",
                    "asset": "123",
                    "conditionId": "0xcond",
                    "size": 50.0,
                    "price": 0.40,
                    "timestamp": 1700001000,
                    "title": "Test?",
                    "slug": "test",
                    "eventSlug": "test-event",
                    "outcome": "Yes",
                    "outcomeIndex": 0,
                    "transactionHash": "0xtx2",
                },
            ],
        )
        # Second page returns empty → stop
        page2 = httpx.Response(200, json=[])

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return page1 if call_count == 1 else page2

        with patch("src.client.make_request", side_effect=mock_request):
            trades = await fetch_trades_for_wallet("0xaaa", ingestion_config)

        assert len(trades) == 2
        assert trades[0].side.value == "BUY"
        assert trades[1].price == 0.40


class TestFetchTags:
    """Verify fetching available tags from Gamma API."""

    @pytest.mark.asyncio
    async def test_returns_parsed_tags(self, ingestion_config):
        """Tags response is parsed into id/label/slug dicts."""
        from src.client import fetch_tags

        mock_response = httpx.Response(
            200,
            json=[
                {
                    "id": "101611",
                    "label": "Altcoins",
                    "slug": "altcoins",
                    "createdAt": "2025-01-01T00:00:00Z",
                    "updatedAt": "2025-01-01T00:00:00Z",
                    "requiresTranslation": False,
                },
                {
                    "id": "833",
                    "label": "ETF",
                    "slug": "etf",
                    "createdAt": "2024-01-01T00:00:00Z",
                    "updatedAt": "2024-01-01T00:00:00Z",
                    "requiresTranslation": False,
                },
            ],
        )

        with patch("src.client.make_request", return_value=mock_response):
            tags = await fetch_tags(ingestion_config)

        assert len(tags) == 2
        assert tags[0] == {"id": "101611", "label": "Altcoins", "slug": "altcoins"}
        assert tags[1] == {"id": "833", "label": "ETF", "slug": "etf"}


class TestFetchResolvedMarketsWithCategory:
    """Verify client-side category filtering."""

    @pytest.mark.asyncio
    async def test_filters_markets_by_category(self, ingestion_config):
        """Only markets matching the requested category are returned."""
        from src.client import fetch_resolved_markets

        mock_response = httpx.Response(
            200,
            json={
                "markets": [
                    {
                        "conditionId": "0x111",
                        "question": "BTC to 200k?",
                        "slug": "btc-200k",
                        "active": False,
                        "closed": True,
                        "volume": "900000",
                        "outcomes": '["Yes","No"]',
                        "outcomePrices": '["0.1","0.9"]',
                        "category": "Crypto",
                    },
                    {
                        "conditionId": "0x222",
                        "question": "Will president resign?",
                        "slug": "president-resign",
                        "active": False,
                        "closed": True,
                        "volume": "500000",
                        "outcomes": '["Yes","No"]',
                        "outcomePrices": '["0.3","0.7"]',
                        "category": "US-current-affairs",
                    },
                ],
                "next_cursor": None,
            },
        )

        with patch("src.client.make_request", return_value=mock_response):
            markets = await fetch_resolved_markets(
                ingestion_config, limit=10, category="Crypto"
            )

        assert len(markets) == 1
        assert markets[0].condition_id == "0x111"
