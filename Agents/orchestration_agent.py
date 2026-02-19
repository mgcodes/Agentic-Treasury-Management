import os
import json
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)

# Robust imports: prefer package import but fall back to loading modules by path
import importlib.util
import sys
import os

try:
    # when package-imported as `Agents.orchestration_agent`
    from Agents import cashflow_agent, sweep_agent, investment_agent
except Exception:
    try:
        # when installed/available as agentic_sweeper
        from agentic_sweeper import cashflow_agent, sweep_agent, investment_agent
    except Exception:
        # fallback: load modules by file path relative to this file
        base = os.path.dirname(__file__)

        def _load(name: str, filename: str):
            path = os.path.join(base, filename)
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            return mod

        cashflow_agent = _load("cashflow_agent", "cashflow_agent.py")
        sweep_agent = _load("sweep_agent", "sweep_agent.py")
        investment_agent = _load("investment_agent", "investment_agent.py")


class LlmAdapter:
    def __init__(self, endpoint: str = None, model: str = None, api_key: str = None):
        self.endpoint = endpoint or os.getenv("LLM_ENDPOINT")
        self.model = model or os.getenv("LLM_MODEL_NAME")
        self.api_key = api_key or os.getenv("LLM_API_KEY")

    def is_available(self) -> bool:
        return bool(self.endpoint and self.model and self.api_key)

    def generate(self, prompt: str) -> str:
        # Placeholder: call real LLM in production. Keep consistent with other agents.
        return f"[LLM simulated summary] prompt_length={len(prompt)}"


class OrchestrationAgent:
    def __init__(self, adapter: LlmAdapter = None):
        self.adapter = adapter or LlmAdapter()

    def orchestrate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch payloads to CashFlow, Sweep and Investment agents and summarize results.

        Expected payload shape (flexible):
          {
            "cashflow": { ... },
            "sweep": { ... },
            "investment": { ... }
          }

        If a per-agent key is missing, the full payload is forwarded to that agent.
        """
        cf_input = payload.get("cashflow") or payload
        sw_input = payload.get("sweep") or payload
        inv_input = payload.get("investment") or payload

        # Call each agent's MCP-style handler (they return status+output)
        cf_resp = cashflow_agent.handle_mcp(cf_input)
        sw_resp = sweep_agent.handle_mcp(sw_input)
        inv_resp = investment_agent.handle_mcp(inv_input)

        outputs = {
            "cashflow": cf_resp,
            "sweep": sw_resp,
            "investment": inv_resp,
        }

        # Build a compact text summary for the LLM
        summary_prompt = "Orchestrator: summarize agent outputs:\n"
        for name, resp in outputs.items():
            summary_prompt += f"\n== {name.upper()} OUTPUT ==\n{json.dumps(resp, indent=2)}\n"

        if self.adapter.is_available():
            llm_summary = self.adapter.generate(summary_prompt)
        else:
            # If LLM not configured, create a simple programmatic summary
            llm_summary = self._simple_summary(outputs)

        return {"status": "success", "outputs": outputs, "summary": llm_summary}

    def _simple_summary(self, outputs: Dict[str, Any]) -> str:
        parts = []
        # Cashflow
        cf = outputs.get("cashflow", {})
        cf_out = cf.get("output") if isinstance(cf, dict) else None
        if cf_out and isinstance(cf_out, dict):
            parts.append(f"Cashflow ending_cash={cf_out.get('ending_cash')}, recommendations={cf_out.get('recommendations')}")
        else:
            parts.append("Cashflow: no structured output")

        # Sweep
        sw = outputs.get("sweep", {})
        sw_out = sw.get("output") if isinstance(sw, dict) else None
        if sw_out and isinstance(sw_out, dict):
            parts.append(f"Sweep recommended_transfers={sw_out.get('recommended_transfers', [])}")
        else:
            parts.append("Sweep: no structured output")

        # Investment
        inv = outputs.get("investment", {})
        inv_out = inv.get("output") if isinstance(inv, dict) else None
        if inv_out and isinstance(inv_out, dict):
            parts.append(f"Investment total_allocated={inv_out.get('summary',{}).get('total_allocated')}")
        else:
            parts.append("Investment: no structured output")

        return " | ".join(parts)


def run_orchestration_example():
    payload = {
        "cashflow": {
            "as_of": "2026-01-14",
            "accounts": [{"id": "acct_main", "balance": 30000}],
            "inflows": [{"date": "2026-01-15", "amount": 10000}],
            "outflows": [{"date": "2026-01-16", "amount": 5000}],
            "forecast_days": 7,
        },
        "sweep": {"excess_cash": 5000, "rules": {}},
        "investment": {
            "excess_cash": 20000,
            "risk_limits": {"max_per_instrument": 0.25, "max_per_tenor": {"short": 0.5, "medium": 0.3, "long": 0.2}},
            "universe": [
                {"id": "inst1", "tenor": "short", "expected_yield": 0.005, "liquidity_score": 0.9},
                {"id": "inst2", "tenor": "medium", "expected_yield": 0.02, "liquidity_score": 0.6},
            ],
        },
    }

    agent = OrchestrationAgent()
    out = agent.orchestrate(payload)
    print(json.dumps(out, indent=2))

    # Also print a human-friendly report
    try:
        report = format_human_report(out)
        print("\n--- Human-frien        python -m Agents.orchestration_agentdly Orchestration Report ---\n")
        print(report)
    except Exception:
        pass


def agent_info() -> Dict:
    return {"name": "OrchestrationAgent", "version": "0.1", "capabilities": ["orchestrate", "mcp_handle", "a2a_handle"]}


def handle_mcp(payload: Dict) -> Dict:
    try:
        inner = payload.get("input") if isinstance(payload, dict) and "input" in payload else payload
        agent = OrchestrationAgent()
        out = agent.orchestrate(inner)
        return {"status": "success", "output": out}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_a2a(message: Dict) -> Dict:
    try:
        mtype = message.get("type")
        sender = message.get("from")
        if mtype == "request_orchestration":
            agent = OrchestrationAgent()
            payload = message.get("payload", {})
            result = agent.orchestrate(payload)
            return {"from": agent_info()["name"], "to": sender, "type": "response_orchestration", "payload": result}
        else:
            return {"from": agent_info()["name"], "to": sender, "type": "error", "payload": {"error": "unsupported message type"}}
    except Exception as e:
        return {"from": agent_info()["name"], "to": message.get("from"), "type": "error", "payload": {"error": str(e)}}


if __name__ == "__main__":
    run_orchestration_example()


def format_human_report(orchestration_result: Dict) -> str:
    """Return a human-friendly multi-line report summarizing orchestration outputs.

    Expects the dict returned by `OrchestrationAgent.orchestrate()` or the MCP wrapper.
    """
    if not isinstance(orchestration_result, dict):
        return "No orchestration result available"

    outputs = orchestration_result.get("outputs") or orchestration_result.get("output", {}).get("outputs") if orchestration_result.get("output") else orchestration_result.get("outputs")
    human_summaries = orchestration_result.get("human_summaries") or (orchestration_result.get("output") or {}).get("human_summaries") or {}
    overall = orchestration_result.get("summary") or (orchestration_result.get("output") or {}).get("summary") or ""

    lines = []
    lines.append("Orchestration Summary:")
    lines.append("")

    for agent_name in ["cashflow", "sweep", "investment"]:
        lines.append(f"**{agent_name.capitalize()}**:")
        hs = human_summaries.get(agent_name)
        if hs:
            lines.append(hs)
        else:
            # fallback: include raw output summary if available
            aout = outputs.get(agent_name) if isinstance(outputs, dict) else None
            if aout:
                lines.append(json.dumps(aout, indent=2))
            else:
                lines.append("(no output)")
        lines.append("")

    lines.append("Overall orchestration summary:")
    lines.append(overall or "(no summary)")

    return "\n".join(lines)
