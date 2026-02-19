import os
import json
from typing import Dict, List
from datetime import datetime, timedelta
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
        return f"[LLM simulated] Cash forecast summary for prompt length {len(prompt)}"


class CashFlowForecastAgent:
    """Produces short, mid, and long-term cash forecasts from AP/AR schedules."""

    def __init__(self, adapter: LlmAdapter = None):
        self.adapter = adapter or LlmAdapter()

    def predict_forecast(self, payload: Dict) -> Dict:
        """Expected payload keys:
           - ap_schedule: [{"date":"YYYY-MM-DD","amount":1000}, ...]
           - ar_schedule: similar
           - forecast_days: integer (default 90)
        Returns totals for short(7), mid(30), long(90) and a simple rolling daily forecast.
        """
        def parse_sched(key):
            sched = payload.get(key) or []
            out = []
            for e in sched:
                try:
                    d = datetime.fromisoformat(e.get("date")) if isinstance(e.get("date"), str) else None
                except Exception:
                    d = None
                amt = float(e.get("amount", 0))
                out.append({"date": d, "amount": amt})
            return out

        ap = parse_sched("ap_schedule")
        ar = parse_sched("ar_schedule")
        # fallback to inflows/outflows
        if not ar and payload.get("inflows"):
            ar = [{"date": datetime.fromisoformat(i.get("date")) if isinstance(i.get("date"), str) else None, "amount": float(i.get("amount", 0))} for i in payload.get("inflows")]
        if not ap and payload.get("outflows"):
            ap = [{"date": datetime.fromisoformat(o.get("date")) if isinstance(o.get("date"), str) else None, "amount": float(o.get("amount", 0))} for o in payload.get("outflows")]

        today = datetime.utcnow().date()
        forecast_horizon = int(payload.get("forecast_days", 90))

        # build daily buckets
        daily = { (today + timedelta(days=i)): 0.0 for i in range(forecast_horizon) }

        for e in ar:
            d = e.get("date")
            if isinstance(d, datetime):
                delta = (d.date() - today).days
                if 0 <= delta < forecast_horizon:
                    daily[today + timedelta(days=delta)] += float(e.get("amount", 0))

        for e in ap:
            d = e.get("date")
            if isinstance(d, datetime):
                delta = (d.date() - today).days
                if 0 <= delta < forecast_horizon:
                    daily[today + timedelta(days=delta)] -= float(e.get("amount", 0))

        # compute aggregates
        def sum_range(days):
            return round(sum(v for k,v in list(daily.items())[:days]), 2)

        short = sum_range(7)
        mid = sum_range(30)
        long = sum_range(min(90, forecast_horizon))

        daily_list = [{"date": d.isoformat(), "net": v} for d, v in sorted(daily.items())]

        forecast = {
            "short_term_total": short,
            "mid_term_total": mid,
            "long_term_total": long,
            "daily": daily_list,
            "as_of": today.isoformat(),
        }

        if self.adapter.is_available():
            prompt = "Forecast summary: " + json.dumps(forecast)
            human = self.adapter.generate(prompt)
        else:
            human = f"Short:{short} Mid:{mid} Long:{long}"

        return {"forecast": forecast, "human_summary": human}


def agent_info() -> Dict:
    return {"name": "CashFlowForecastAgent", "version": "0.1", "capabilities": ["predict_forecast", "mcp_handle", "a2a_handle"]}


def handle_mcp(payload: Dict) -> Dict:
    try:
        inner = payload.get("input") if isinstance(payload, dict) and "input" in payload else payload
        agent = CashFlowForecastAgent()
        out = agent.predict_forecast(inner)
        return {"status": "success", "output": out}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_a2a(message: Dict) -> Dict:
    try:
        mtype = message.get("type")
        sender = message.get("from")
        if mtype == "request_cash_forecast":
            agent = CashFlowForecastAgent()
            payload = message.get("payload", {})
            forecast = agent.predict_forecast(payload)
            return {"from": agent_info()["name"], "to": sender, "type": "response_cash_forecast", "payload": forecast}
        else:
            return {"from": agent_info()["name"], "to": sender, "type": "error", "payload": {"error": "unsupported message type"}}
    except Exception as e:
        return {"from": agent_info()["name"], "to": message.get("from"), "type": "error", "payload": {"error": str(e)}}


if __name__ == "__main__":
    sample = {
        "ap_schedule": [{"date": (datetime.utcnow()+timedelta(days=2)).date().isoformat(), "amount": 2000}],
        "ar_schedule": [{"date": (datetime.utcnow()+timedelta(days=1)).date().isoformat(), "amount": 5000}],
        "forecast_days": 30,
    }
    a = CashFlowForecastAgent()
    print(json.dumps(a.predict_forecast(sample), indent=2))
