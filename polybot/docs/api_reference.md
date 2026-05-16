# Polymarket API Reference (for polybot)

Sources: [Polymarket Docs](https://docs.polymarket.com/market-data/overview),
[Data API Gist](https://gist.github.com/shaunlebron/0dd3338f7dea06b8e9f8724981bb13bf)

## APIs We Use

| API | Base URL | Auth | Purpose |
|-----|----------|------|---------|
| Gamma API | `https://gamma-api.polymarket.com` | None | Market/event discovery |
| Data API | `https://data-api.polymarket.com` | None | Trades, positions, holders |
| CLOB API | `https://clob.polymarket.com` | None (public) | Prices, orderbook |

---

## Data API: GET /trades

Fetches trades. Ordered by timestamp descending (most recent first).

### Query Parameters (all optional)

| Param | Type | Description |
|-------|------|-------------|
| `user` | string | Wallet address to filter by |
| `market` | string | conditionId (supports CSV for multiple) |
| `limit` | int | Max results, default 100, max 500 |
| `offset` | int | Pagination offset |
| `side` | string | `BUY` or `SELL` |
| `takerOnly` | bool | Only taker orders (default true) |
| `filterType` | string | `CASH` or `TOKENS` |
| `filterAmount` | number | Min amount for filterType |

### Response (array of objects)

```json
{
  "proxyWallet": "0x6af75d4e4...",
  "side": "SELL",
  "asset": "2877466546393263139...",
  "conditionId": "0x1731c2d00c722fa4d...",
  "size": 160.26,
  "price": 0.89,
  "timestamp": 1724210494,
  "title": "2024 August hottest on record?",
  "slug": "2024-august-hottest-on-record",
  "icon": "https://...",
  "eventSlug": "2024-august-hottest-on-record",
  "outcome": "Yes",
  "outcomeIndex": 0,
  "name": "gopfan",
  "pseudonym": "Mean-Record",
  "bio": "",
  "profileImage": "https://...",
  "profileImageOptimized": "",
  "transactionHash": "0x5620f25e..."
}
```

Key notes:
- `proxyWallet` is the trader's address (not `maker_address`)
- `asset` is a large numeric token ID string (not hex)
- `size` is a float (number of tokens)
- `price` is a float 0-1
- `timestamp` is Unix seconds (integer)
- `transactionHash` is the on-chain tx hash
- `conditionId` is the market identifier (hex)
- `outcome` is the outcome label ("Yes", "No", etc.)
- `outcomeIndex` is the numeric index of the outcome

---

## Gamma API: GET /markets

### Query Parameters

| Param | Type | Description |
|-------|------|-------------|
| `active` | bool | Filter active markets |
| `closed` | bool | Filter closed markets |
| `limit` | int | Results per page |
| `next_cursor` | string | Keyset pagination cursor |

### Response

```json
{
  "markets": [ ... ],
  "next_cursor": "<string>"
}
```

Key market fields we care about:
- `conditionId`: unique market identifier
- `question`: the market question
- `slug`: URL-friendly identifier
- `active`: bool
- `closed`: bool
- `endDate`: ISO 8601 datetime
- `volume`: string (total volume)
- `outcomes`: JSON string array e.g. `"[\"Yes\", \"No\"]"`
- `outcomePrices`: JSON string array e.g. `"[\"0.20\", \"0.80\"]"`
- `clobTokenIds`: string (token IDs for CLOB)

---

## CLOB API: GET /trades (authenticated user's own trades)

Different from Data API. Requires API keys. Response format:

```json
{
  "limit": 100,
  "next_cursor": "MTAw",
  "count": 2,
  "data": [
    {
      "id": "trade-123",
      "taker_order_id": "0xabcdef...",
      "market": "0x000...0001",
      "asset_id": "15871154585...",
      "side": "BUY",
      "size": "100000000",
      "fee_rate_bps": "30",
      "price": "0.5",
      "status": "TRADE_STATUS_CONFIRMED",
      "match_time": "1700000000",
      "last_update": "1700000000",
      "outcome": "YES",
      "bucket_index": 0,
      "owner": "f4f247b7-...",
      "maker_address": "0x123...",
      "transaction_hash": "0x123...def",
      "trader_side": "TAKER",
      "maker_orders": []
    }
  ]
}
```

Note: This is for YOUR OWN trades. For tracking OTHER wallets,
use the Data API `/trades?user=<address>` endpoint instead.
