#!/usr/bin/env python3
"""Simple script that uses `api.client.ResilientClient` to call the `/mcp/invest` endpoint."""
import os
import json
from api.client import default_client


def main():
    client = default_client()
    payload = {
        "input": {
            "excess_cash": 50000,
            "risk_limits": {"max_per_instrument": 0.2},
            "universe": [
                {"id": "i1", "tenor": "short", "expected_yield": 0.005, "liquidity_score": 0.9}
            ],
        }
    }

    try:
        resp = client.post("/mcp/invest", json=payload)
        data = resp.json()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print("Request failed:", str(e))
    finally:
        client.close()


if __name__ == "__main__":
    main()
