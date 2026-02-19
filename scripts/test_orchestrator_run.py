from graph.orchestrator import run_orchestrator
import json

payload = {
    "prior_day": [{"id": "acct1", "balance": 10000}, {"id": "acct2", "balance": 5000}],
    "intraday": [{"id": "acct1", "balance": 12000}],
    "accounts": [{"id": "acct1", "balance": 12000}, {"id": "acct2", "balance": 5000}],
    "inflows": [{"date": "2026-01-15", "amount": 8000}],
    "outflows": [{"date": "2026-01-16", "amount": 3000}],
    "bank_transactions": [{"id":"b1","amount":100.0,"ref":"INV-100"},{"id":"b2","amount":50.0}],
    "ledger_transactions": [{"id":"l1","amount":100.0,"ref":"INV-100"},{"id":"l2","amount":75.0}],
    "ap_schedule": [{"date": "2026-01-17", "amount": 2000}],
    "ar_schedule": [{"date": "2026-01-16", "amount": 5000}],
    "forecast_days": 30,
    "universe": [
        {"id": "inst1", "tenor": "short", "expected_yield": 0.005, "liquidity_score": 0.9},
        {"id": "inst2", "tenor": "medium", "expected_yield": 0.02, "liquidity_score": 0.6},
    ],
}

out = run_orchestrator(payload)
print(json.dumps(out, indent=2))
# Also request reporting explicitly via MCP-style wrapper
from Agents import reporting_agent
print('\n--- Reporting Agent Direct Call ---\n')
print(json.dumps(reporting_agent.handle_mcp({'input': {'node_outputs': out.get('node_outputs', {})}}), indent=2))
