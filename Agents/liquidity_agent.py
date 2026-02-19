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
        return f"[LLM simulated] Liquidity overview for prompt length {len(prompt)}"


class LiquidityAgent:
    def __init__(self, adapter: LlmAdapter = None):
        self.adapter = adapter or LlmAdapter()

    def overview_accounts(self, payload: Dict) -> Dict:
        """Return liquidity overview for provided accounts.

        Expected payload:
          {"accounts": [{"id": "acct1", "balance": 10000, "liquidity_score": 0.9}, ...],
           "low_balance_threshold": 1000 }
        """
        accounts: List[Dict] = payload.get("accounts", []) or []
        if not accounts:
            return {"error": "no accounts provided"}

        total = sum(float(a.get("balance", 0)) for a in accounts)
        avg = total / len(accounts) if accounts else 0
        sorted_acc = sorted(accounts, key=lambda x: float(x.get("balance", 0)), reverse=True)
        largest = sorted_acc[0] if sorted_acc else None

        # liquidity score interpretation: 0-1, treat missing as 0.5
        liquid_sum = 0.0
        for a in accounts:
            score = float(a.get("liquidity_score", 0.5))
            if score >= 0.7:
                liquid_sum += float(a.get("balance", 0))

        low_threshold = float(payload.get("low_balance_threshold", 1000))
        low_accounts = [a for a in accounts if float(a.get("balance", 0)) < low_threshold]

        account_summaries = []
        for a in accounts:
            bal = float(a.get("balance", 0))
            account_summaries.append({
                "id": a.get("id"),
                "balance": round(bal, 2),
                "pct_of_total": round((bal / total * 100) if total else 0, 2),
                "liquidity_score": a.get("liquidity_score", None),
                "low_balance": bal < low_threshold,
            })

        overview = {
            "total_balance": round(total, 2),
            "average_balance": round(avg, 2),
            "largest_account": {"id": largest.get("id"), "balance": round(float(largest.get("balance", 0)), 2)} if largest else None,
            "liquid_balance_estimate": round(liquid_sum, 2),
            "low_balance_count": len(low_accounts),
            "accounts": account_summaries,
        }

        # human summary (LLM if available)
        if self.adapter.is_available():
            prompt = "Provide a liquidity overview for accounts: " + json.dumps(overview)
            human = self.adapter.generate(prompt)
        else:
            human_lines = [f"Total balance: {overview['total_balance']}", f"Liquid-like balance: {overview['liquid_balance_estimate']}", f"Accounts below {low_threshold}: {len(low_accounts)}"]
            human = " -- ".join(human_lines)

        return {"overview": overview, "human_summary": human}


def agent_info() -> Dict:
    return {"name": "LiquidityAgent", "version": "0.1", "capabilities": ["overview_accounts", "mcp_handle", "a2a_handle"]}


def handle_mcp(payload: Dict) -> Dict:
    try:
        inner = payload.get("input") if isinstance(payload, dict) and "input" in payload else payload
        agent = LiquidityAgent()
        out = agent.overview_accounts(inner)
        return {"status": "success", "output": out}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_a2a(message: Dict) -> Dict:
    try:
        mtype = message.get("type")
        sender = message.get("from")
        if mtype == "request_liquidity_overview":
            agent = LiquidityAgent()
            payload = message.get("payload", {})
            overview = agent.overview_accounts(payload)
            return {"from": agent_info()["name"], "to": sender, "type": "response_liquidity_overview", "payload": overview}
        else:
            return {"from": agent_info()["name"], "to": sender, "type": "error", "payload": {"error": "unsupported message type"}}
    except Exception as e:
        return {"from": agent_info()["name"], "to": message.get("from"), "type": "error", "payload": {"error": str(e)}}


if __name__ == "__main__":
    sample = {"accounts": [{"id": "acct_main", "balance": 25000, "liquidity_score": 0.95}, {"id": "acct_b", "balance": 500, "liquidity_score": 0.2}], "low_balance_threshold": 1000}
    a = LiquidityAgent()
    print(json.dumps(a.overview_accounts(sample), indent=2))
