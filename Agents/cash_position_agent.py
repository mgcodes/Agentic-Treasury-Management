import os
import json
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv(override=True)


class LlmAdapter:
    def __init__(self, endpoint: str = None, model: str = None, api_key: str = None):
        self.endpoint = endpoint or os.getenv("LLM_ENDPOINT")
        self.model = model or os.getenv("LLM_MODEL_NAME")
        self.api_key = api_key or os.getenv("LLM_API_KEY")

    def is_available(self) -> bool:
        return bool(self.endpoint and self.model and self.api_key)

    def generate(self, prompt: str) -> str:
        return f"[LLM simulated] Cash position summary for prompt length {len(prompt)}"


class CashPositionAgent:
    """Aggregates prior-day and intraday bank data to produce current cash position."""

    def __init__(self, adapter: LlmAdapter = None):
        self.adapter = adapter or LlmAdapter()

    def aggregate_positions(self, payload: Dict) -> Dict:
        """Expected payload keys:
           - prior_day: [{"id":"acct1","balance":1000},...]
           - intraday: [{"id":"acct1","balance":1200}, ...] (optional, overrides prior_day)
           - accounts: [{'id':..., 'balance':...}] (optional)
        Returns a summary dictionary with per-account latest balances and totals.
        """
        prior = {a.get("id"): float(a.get("balance", 0)) for a in (payload.get("prior_day") or [])}
        intraday = {a.get("id"): float(a.get("balance", 0)) for a in (payload.get("intraday") or [])}
        # start with explicit accounts if provided
        explicit = {a.get("id"): float(a.get("balance", 0)) for a in (payload.get("accounts") or [])}

        # merge precedence: intraday > explicit > prior
        ids = set(list(prior.keys()) + list(intraday.keys()) + list(explicit.keys()))
        per_account = {}
        for acc in ids:
            if acc in intraday:
                bal = intraday[acc]
                source = "intraday"
            elif acc in explicit:
                bal = explicit[acc]
                source = "accounts"
            else:
                bal = prior.get(acc, 0.0)
                source = "prior_day"
            per_account[acc] = {"balance": round(float(bal), 2), "source": source}

        total = round(sum(v["balance"] for v in per_account.values()), 2)

        # simple metrics
        negative_accounts = [k for k, v in per_account.items() if v["balance"] < 0]
        zero_accounts = [k for k, v in per_account.items() if v["balance"] == 0]

        overview = {
            "per_account": per_account,
            "total_balance": total,
            "negative_accounts": negative_accounts,
            "zero_accounts": zero_accounts,
            "account_count": len(per_account),
        }

        # human summary
        if self.adapter.is_available():
            prompt = "Describe current cash position: " + json.dumps(overview)
            human = self.adapter.generate(prompt)
        else:
            human = f"Total balance: {total}, accounts: {len(per_account)}, negatives: {len(negative_accounts)}"

        return {"overview": overview, "human_summary": human}


def agent_info() -> Dict:
    return {"name": "CashPositionAgent", "version": "0.1", "capabilities": ["aggregate_positions", "mcp_handle", "a2a_handle"]}


def handle_mcp(payload: Dict) -> Dict:
    try:
        inner = payload.get("input") if isinstance(payload, dict) and "input" in payload else payload
        agent = CashPositionAgent()
        out = agent.aggregate_positions(inner)
        return {"status": "success", "output": out}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_a2a(message: Dict) -> Dict:
    try:
        mtype = message.get("type")
        sender = message.get("from")
        if mtype == "request_cash_position":
            agent = CashPositionAgent()
            payload = message.get("payload", {})
            overview = agent.aggregate_positions(payload)
            return {"from": agent_info()["name"], "to": sender, "type": "response_cash_position", "payload": overview}
        else:
            return {"from": agent_info()["name"], "to": sender, "type": "error", "payload": {"error": "unsupported message type"}}
    except Exception as e:
        return {"from": agent_info()["name"], "to": message.get("from"), "type": "error", "payload": {"error": str(e)}}


if __name__ == "__main__":
    sample = {
        "prior_day": [{"id": "acct1", "balance": 10000}, {"id": "acct2", "balance": 5000}],
        "intraday": [{"id": "acct1", "balance": 12000}],
    }
    a = CashPositionAgent()
    import json as _j
    print(_j.dumps(a.aggregate_positions(sample), indent=2))
