#!/usr/bin/env bash
set -eu

API_URL="${API_URL:-http://localhost:8000/mcp/invest}"
# Allow overriding via env; fall back to the demo key from .env if not set
API_KEY="${API_KEY:-443b28b3-584b-4e38-8363-6a9db927557d}"

read -r -d '' PAYLOAD <<'JSON'
{
  "input": {
    "excess_cash": 50000,
    "risk_limits": {"max_per_instrument": 0.2},
    "universe": [
      {"id":"i1","tenor":"short","expected_yield":0.005,"liquidity_score":0.9}
    ]
  }
}
JSON

curl -sS -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d "$PAYLOAD"
