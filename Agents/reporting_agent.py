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
        return f"[LLM simulated] Reporting summary for prompt length {len(prompt)}"


class ReportingAgent:
    """Produces dashboards, KPIs and liquidity reports from orchestrator outputs."""

    def __init__(self, adapter: LlmAdapter = None):
        self.adapter = adapter or LlmAdapter()

    def generate_report(self, payload: Dict) -> Dict:
        """Expect payload to include node_outputs from orchestrator.

        Returns a compact analytics dict with KPIs and a human summary.
        """
        node_outputs = payload.get("node_outputs") or payload

        # Simple KPI calculations
        total_balance = None
        if node_outputs.get("cashflow") and node_outputs["cashflow"].get("status") == "success":
            cf = node_outputs["cashflow"]["output"]
            total_balance = cf.get("total_balance")

        forecast = node_outputs.get("cash_forecast", {}).get("output", {}).get("forecast") if node_outputs.get("cash_forecast") else None

        # Forecast accuracy KPI placeholder (needs historical actuals to compute)
        forecast_kpis = {"short_term_accuracy": None, "mid_term_accuracy": None, "long_term_accuracy": None}

        liquidity_overview = node_outputs.get("liquidity", {}).get("output", {}).get("overview") if node_outputs.get("liquidity") else None

        dashboard = {
            "total_balance": total_balance,
            "forecast": forecast,
            "forecast_kpis": forecast_kpis,
            "liquidity": liquidity_overview,
            "reconciliation_exceptions": len(node_outputs.get("reconciliation", {}).get("output", {}).get("overview", {}).get("exceptions", [])) if node_outputs.get("reconciliation") else None,
        }

        # Simple charts payload: top lines for CFO
        charts = {
            "cash_daily": forecast.get("daily") if forecast else [],
            "top_accounts": (liquidity_overview.get("accounts")[:5] if liquidity_overview and liquidity_overview.get("accounts") else [])
        }

        if self.adapter.is_available():
            prompt = "Prepare CFO summary: " + json.dumps({"dashboard": dashboard, "charts": charts})
            human = self.adapter.generate(prompt)
        else:
            human = f"Total balance: {total_balance}, Exceptions: {dashboard.get('reconciliation_exceptions')}"

        report = {"dashboard": dashboard, "charts": charts, "human_summary": human}
        return report


def agent_info() -> Dict:
    return {"name": "ReportingAgent", "version": "0.1", "capabilities": ["generate_report", "mcp_handle", "a2a_handle"]}


def handle_mcp(payload: Dict) -> Dict:
    try:
        inner = payload.get("input") if isinstance(payload, dict) and "input" in payload else payload
        agent = ReportingAgent()
        out = agent.generate_report(inner)
        return {"status": "success", "output": out}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_a2a(message: Dict) -> Dict:
    try:
        mtype = message.get("type")
        sender = message.get("from")
        if mtype == "request_reporting":
            agent = ReportingAgent()
            payload = message.get("payload", {})
            report = agent.generate_report(payload)
            return {"from": agent_info()["name"], "to": sender, "type": "response_reporting", "payload": report}
        else:
            return {"from": agent_info()["name"], "to": sender, "type": "error", "payload": {"error": "unsupported message type"}}
    except Exception as e:
        return {"from": agent_info()["name"], "to": message.get("from"), "type": "error", "payload": {"error": str(e)}}


if __name__ == "__main__":
    sample = {"node_outputs": {}}
    a = ReportingAgent()
    import json as _j
    print(_j.dumps(a.generate_report(sample), indent=2))
