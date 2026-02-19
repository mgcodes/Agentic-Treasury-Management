import os
import json
from typing import List, Dict
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
        # Placeholder: in real usage call the LLM endpoint here.
        # For the example we just echo the prompt header.
        return f"[LLM simulated response] Summary for prompt length {len(prompt)}"


class CashFlowAgent:
    def __init__(self, adapter: LlmAdapter = None):
        self.adapter = adapter or LlmAdapter()

    def analyze_cashflow(self, payload: Dict) -> Dict:
        """Basic cashflow & liquidity analysis.

        payload expected shape:
        {
          "as_of": "2026-01-12",
          "accounts": [{"id":"acct1","balance":1000.0}, ...],
          "inflows": [{"date":"2026-01-13","amount":5000.0}, ...],
          "outflows": [{"date":"2026-01-14","amount":3000.0}, ...],
          "forecast_days": 7
        }
        """
        accounts = payload.get("accounts", [])
        inflows = payload.get("inflows", [])
        outflows = payload.get("outflows", [])
        forecast_days = int(payload.get("forecast_days", 7))

        total_balance = sum(float(a.get("balance", 0)) for a in accounts)
        total_inflows = sum(float(i.get("amount", 0)) for i in inflows)
        total_outflows = sum(float(o.get("amount", 0)) for o in outflows)

        net_forecast = total_inflows - total_outflows
        ending_cash = total_balance + net_forecast

        # Simple daily projection
        daily_net = net_forecast / max(1, forecast_days)
        recommended_buffer = round(total_outflows * 0.1, 2)

        recommendations: List[str] = []
        if ending_cash < recommended_buffer:
            recommendations.append("Consider drawing on credit line or netting payables")
        if net_forecast < 0 and abs(net_forecast) > recommended_buffer:
            recommendations.append("Short-term financing recommended to cover net outflows")
        if total_balance > recommended_buffer * 10:
            recommendations.append("Invest surplus cash or increase sweep frequency")

        # Optionally call LLM adapter for human-friendly summary (simulated here)
        if self.adapter.is_available():
            prompt = (
                f"Analyze cashflow: balance={total_balance}, inflows={total_inflows}, "
                f"outflows={total_outflows}, days={forecast_days}"
            )
            llm_summary = self.adapter.generate(prompt)
        else:
            llm_summary = "LLM adapter not configured; skipping natural-language summary."

        result = {
            "as_of": payload.get("as_of"),
            "total_balance": round(total_balance, 2),
            "total_inflows": round(total_inflows, 2),
            "total_outflows": round(total_outflows, 2),
            "net_forecast": round(net_forecast, 2),
            "ending_cash": round(ending_cash, 2),
            "daily_net": round(daily_net, 2),
            "recommended_buffer": recommended_buffer,
            "recommendations": recommendations,
            "llm_summary": llm_summary,
        }

        return result


def run_cashflow_example():
    payload = {
        "as_of": "2026-01-12",
        "accounts": [
            {"id": "acct_main", "balance": 25000.0},
            {"id": "acct_payroll", "balance": 2000.0},
            {"id": "acct_receivables", "balance": 5000.0},
        ],
        "inflows": [
            {"date": "2026-01-13", "amount": 12000.0},
            {"date": "2026-01-15", "amount": 3000.0},
        ],
        "outflows": [
            {"date": "2026-01-14", "amount": 18000.0},
            {"date": "2026-01-16", "amount": 2000.0},
        ],
        "forecast_days": 7,
    }

    agent = CashFlowAgent()
    result = agent.analyze_cashflow(payload)
    print(json.dumps({"payload": payload, "analysis": result}, indent=2))


if __name__ == "__main__":
    run_cashflow_example()


# --- MCP / A2A helpers ---
def agent_info() -> Dict:
    return {
        "name": "CashFlowAgent",
        "version": "0.1",
        "capabilities": ["analyze_cashflow", "mcp_handle", "a2a_handle"],
    }


def handle_mcp(payload: Dict) -> Dict:
    """MCP-style handler: expects either {'input': <payload>} or direct payload.

    Returns: {'status': 'success', 'output': <analysis>} or error structure.
    """
    try:
        inner = payload.get("input") if isinstance(payload, dict) and "input" in payload else payload
        agent = CashFlowAgent()
        analysis = agent.analyze_cashflow(inner)
        return {"status": "success", "output": analysis}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_a2a(message: Dict) -> Dict:
    """Agent-to-Agent (A2A) handler.

    Expects message dict with keys: 'from', 'to', 'type', 'payload'
    Returns a response message dict with 'to' set to the original sender.
    """
    try:
        mtype = message.get("type")
        sender = message.get("from")
        if mtype == "request_cashflow_analysis":
            agent = CashFlowAgent()
            analysis = agent.analyze_cashflow(message.get("payload", {}))
            return {"from": agent_info()["name"], "to": sender, "type": "response_cashflow_analysis", "payload": analysis}
        else:
            return {"from": agent_info()["name"], "to": sender, "type": "error", "payload": {"error": "unsupported message type"}}
    except Exception as e:
        return {"from": agent_info()["name"], "to": message.get("from"), "type": "error", "payload": {"error": str(e)}}

