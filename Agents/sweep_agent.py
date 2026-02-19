import os
import json
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv(override=True)


class LlmAdapter:
    """Minimal adapter template for local testing."""

    def __init__(self, endpoint: str = None, model: str = None, api_key: str = None):
        self.endpoint = endpoint or os.getenv("LLM_ENDPOINT")
        self.model = model or os.getenv("LLM_MODEL_NAME")
        self.api_key = api_key or os.getenv("LLM_API_KEY")

    def is_available(self) -> bool:
        return bool(self.endpoint and self.model and self.api_key)

    def generate(self, prompt: str) -> str:
        return f"[LLM simulated] {prompt[:80]}..."


class SweepAgent:
    def __init__(self, adapter: LlmAdapter = None):
        self.adapter = adapter or LlmAdapter()

    def optimize_sweep(self, payload: Dict) -> Dict:
        accounts = payload.get("accounts", [])
        main_id = payload.get("main_account_id")

        moves = []
        total_excess = 0.0
        total_shortfall = 0.0

        for acct in accounts:
            aid = acct.get("id")
            if aid == main_id:
                continue

            balance = float(acct.get("balance", 0))
            min_balance = float(acct.get("min_balance", 0))
            target_balance = float(acct.get("target_balance", min_balance))

            if balance <= min_balance:
                short = min_balance - balance
                if short > 0:
                    total_shortfall += short
                continue

            excess = balance - target_balance
            if excess <= 0:
                continue

            move_amount = round(excess, 2)
            moves.append({"from": aid, "to": main_id, "amount": move_amount})
            total_excess += move_amount

        frequency = "weekly"
        if len(moves) >= 3 or total_excess > 10000:
            frequency = "daily"
        elif total_excess > 1000:
            frequency = "every-2-days"

        summary = {
            "total_excess": round(total_excess, 2),
            "total_shortfall": round(total_shortfall, 2),
            "moves_count": len(moves),
        }

        recommendation = {
            "frequency": frequency,
            "buffer_amount": round(sum(float(a.get("min_balance", 0)) for a in accounts) * 0.01, 2),
        }

        llm_summary = (
            self.adapter.generate(f"Sweep analysis total_excess={total_excess} moves={len(moves)}")
            if self.adapter.is_available()
            else "LLM not configured"
        )

        return {
            "moves": moves,
            "summary": summary,
            "recommendation": recommendation,
            "llm_summary": llm_summary,
        }


def run_sweep_example():
    payload = {
        "main_account_id": "acct_main",
        "accounts": [
            {"id": "acct_main", "balance": 5000, "min_balance": 1000, "target_balance": 2000},
            {"id": "acct_a", "balance": 12000, "min_balance": 1000, "target_balance": 2000},
            {"id": "acct_b", "balance": 1500, "min_balance": 500, "target_balance": 1000},
            {"id": "acct_c", "balance": 300, "min_balance": 500, "target_balance": 500},
        ],
    }

    agent = SweepAgent()
    result = agent.optimize_sweep(payload)
    print(json.dumps({"payload": payload, "analysis": result}, indent=2))


if __name__ == "__main__":
    run_sweep_example()


# --- MCP / A2A helpers ---
def agent_info() -> Dict:
    return {"name": "SweepAgent", "version": "0.1", "capabilities": ["optimize_sweep", "mcp_handle", "a2a_handle"]}


def handle_mcp(payload: Dict) -> Dict:
    try:
        inner = payload.get("input") if isinstance(payload, dict) and "input" in payload else payload
        agent = SweepAgent()
        analysis = agent.optimize_sweep(inner)
        return {"status": "success", "output": analysis}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_a2a(message: Dict) -> Dict:
    try:
        mtype = message.get("type")
        sender = message.get("from")
        if mtype == "request_sweep_optimization":
            agent = SweepAgent()
            analysis = agent.optimize_sweep(message.get("payload", {}))
            return {"from": agent_info()["name"], "to": sender, "type": "response_sweep_optimization", "payload": analysis}
        else:
            return {"from": agent_info()["name"], "to": sender, "type": "error", "payload": {"error": "unsupported message type"}}
    except Exception as e:
        return {"from": agent_info()["name"], "to": message.get("from"), "type": "error", "payload": {"error": str(e)}}

