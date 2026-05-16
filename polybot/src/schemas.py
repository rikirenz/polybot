"""
Data contracts for the polybot pipeline.

These Pydantic models define the shape of data flowing between modules.
Each module validates its inputs and outputs against these schemas.
If upstream produces garbage, downstream fails fast with a clear error.

API reference: docs/api_reference.md
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TradeDirection(str, Enum):
    """Whether a trade is buying or selling outcome tokens."""
    BUY = "BUY"
    SELL = "SELL"


class Market(BaseModel):
    """
    A Polymarket prediction market.

    Source: Gamma API GET /markets (keyset pagination).
    We only keep the fields relevant to our pipeline.
    """

    condition_id: str = Field(
        ..., description="Unique market identifier (hex)"
    )
    question: str = Field(..., description="The market question text")
    slug: str = Field(..., description="URL-friendly identifier")
    active: bool
    closed: bool
    end_date: str | None = Field(
        None, description="ISO 8601 end date string"
    )
    volume: str = Field(
        ..., description="Total volume as string"
    )
    outcomes: str = Field(
        ..., description='JSON string array, e.g. \'["Yes","No"]\''
    )
    outcome_prices: str = Field(
        ..., description='JSON string array, e.g. \'["0.20","0.80"]\''
    )
    category: str | None = Field(
        None, description="Market category (e.g. Crypto, Sports, Tech)"
    )

    @field_validator("condition_id")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("condition_id must not be empty")
        return v


class Trade(BaseModel):
    """
    A single trade from the Data API.

    Source: Data API GET /trades
    Fields match the actual API response (camelCase mapped to snake_case).
    """

    proxy_wallet: str = Field(
        ..., description="Trader's proxy wallet address"
    )
    side: TradeDirection
    asset: str = Field(
        ..., description="Numeric token ID string"
    )
    condition_id: str = Field(
        ..., description="Market condition ID (hex)"
    )
    size: float = Field(
        ..., gt=0, description="Number of outcome tokens traded"
    )
    price: float = Field(
        ..., gt=0, le=1, description="Price per token (0-1)"
    )
    timestamp: int = Field(
        ..., description="Unix timestamp in seconds"
    )
    title: str = Field(
        ..., description="Market title"
    )
    slug: str
    event_slug: str
    outcome: str = Field(
        ..., description="Outcome label (e.g. 'Yes', 'No')"
    )
    outcome_index: int
    transaction_hash: str = Field(
        ..., description="On-chain transaction hash"
    )
    # Profile fields (may be empty strings)
    name: str = ""
    pseudonym: str = ""

    @field_validator("proxy_wallet")
    @classmethod
    def normalize_wallet(cls, v: str) -> str:
        return v.lower().strip()


class IngestionCheckpoint(BaseModel):
    """
    Tracks ingestion progress for resumability.

    Stored locally so that if ingestion crashes, it can resume
    from the last successfully processed offset.
    """

    market_condition_id: str
    last_offset: int = 0
    total_trades_fetched: int = 0
