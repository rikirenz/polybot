"""
Tests for the data ingestion module.

These tests define the expected behavior BEFORE implementation.
They cover:
- Parsing raw API responses into validated schemas
- Handling pagination (offset-based for Data API, cursor for Gamma API)
- Resumability (checkpointing)
- Error handling (malformed data skipped gracefully)

No network calls — all tests use fixtures from conftest.py.
"""

from __future__ import annotations

import pytest
from src.schemas import Market, Trade, TradeDirection


class TestParseMarkets:
    """Verify Gamma API market responses are parsed correctly."""

    def test_parse_valid_market_response(self, sample_market_api_response):
        """A well-formed Gamma API response produces Market objects."""
        from src.ingestion import parse_markets_response

        markets, cursor = parse_markets_response(sample_market_api_response)

        assert len(markets) == 1
        m = markets[0]
        assert isinstance(m, Market)
        assert m.condition_id == "0xabc123def456"
        assert m.question == "Will BTC exceed $100k by end of 2025?"
        assert m.closed is True
        assert cursor == "cursor_abc123"

    def test_parse_empty_market_response(self):
        """Empty markets array returns empty list, no crash."""
        from src.ingestion import parse_markets_response

        markets, cursor = parse_markets_response(
            {"markets": [], "next_cursor": None}
        )
        assert markets == []
        assert cursor is None

    def test_parse_market_missing_required_field_is_skipped(self):
        """A market missing conditionId is skipped, not a crash."""
        from src.ingestion import parse_markets_response

        bad_response = {
            "markets": [
                {
                    # missing conditionId
                    "question": "Test?",
                    "slug": "test",
                    "active": True,
                    "closed": False,
                    "volume": "100",
                    "outcomes": '["Yes","No"]',
                    "outcomePrices": '["0.5","0.5"]',
                }
            ],
            "next_cursor": None,
        }
        markets, _ = parse_markets_response(bad_response)
        assert len(markets) == 0


class TestParseTrades:
    """Verify Data API trade responses are parsed correctly."""

    def test_parse_valid_trades_response(self, sample_trades_api_response):
        """A well-formed Data API response produces Trade objects."""
        from src.ingestion import parse_trades_response

        trades = parse_trades_response(sample_trades_api_response)

        assert len(trades) == 2
        t = trades[0]
        assert isinstance(t, Trade)
        assert t.side == TradeDirection.BUY
        assert t.price == 0.65
        assert t.size == 160.26
        assert t.proxy_wallet == "0x6af75d4e4aaf700450efbac3708cce1665810ff1"
        assert t.condition_id == "0xabc123def456"

    def test_parse_trade_normalizes_wallet_to_lowercase(
        self, sample_trades_api_response
    ):
        """Wallet addresses are lowercased during parsing."""
        from src.ingestion import parse_trades_response

        # Modify to have uppercase address
        modified = [
            {**sample_trades_api_response[0], "proxyWallet": "0x6AF75D4E4AAF700450EFBAC3708CCE1665810FF1"}
        ]
        trades = parse_trades_response(modified)
        assert trades[0].proxy_wallet == "0x6af75d4e4aaf700450efbac3708cce1665810ff1"

    def test_parse_trade_with_invalid_price_is_skipped(self):
        """A trade with price > 1 is skipped."""
        from src.ingestion import parse_trades_response

        bad_trade = [
            {
                "proxyWallet": "0xabc",
                "side": "BUY",
                "asset": "123",
                "conditionId": "0xdef",
                "size": 100,
                "price": 1.5,  # invalid
                "timestamp": 1724210494,
                "title": "Test",
                "slug": "test",
                "eventSlug": "test-event",
                "outcome": "Yes",
                "outcomeIndex": 0,
                "transactionHash": "0xaaa",
            }
        ]
        trades = parse_trades_response(bad_trade)
        assert len(trades) == 0

    def test_parse_empty_trades_response(self):
        """Empty array returns empty list."""
        from src.ingestion import parse_trades_response

        trades = parse_trades_response([])
        assert trades == []


class TestCheckpointing:
    """Ingestion must be resumable via offset-based checkpoints."""

    def test_checkpoint_saves_and_loads(self, tmp_path):
        """After processing a batch, checkpoint is persisted."""
        from src.ingestion import save_checkpoint, load_checkpoint
        from src.schemas import IngestionCheckpoint

        cp = IngestionCheckpoint(
            market_condition_id="0xabc123",
            last_offset=200,
            total_trades_fetched=200,
        )

        save_checkpoint(cp, storage_path=tmp_path)
        loaded = load_checkpoint("0xabc123", storage_path=tmp_path)

        assert loaded is not None
        assert loaded.last_offset == 200
        assert loaded.total_trades_fetched == 200

    def test_load_checkpoint_returns_none_for_new_market(self, tmp_path):
        """First run for a market returns None (start from offset 0)."""
        from src.ingestion import load_checkpoint

        result = load_checkpoint("0xnever_seen", storage_path=tmp_path)
        assert result is None
