import os
import json
from typing import Any, Dict

from .node import Node

# Attempt to import agent implementations from the Agents package; fall back to file-loads
try:
    from Agents import cashflow_agent, sweep_agent, investment_agent
except Exception:
    try:
        from agentic_sweeper import cashflow_agent, sweep_agent, investment_agent
    except Exception:
        # final fallback: import by path relative to this file
        import importlib.util, sys
        base = os.path.join(os.path.dirname(__file__), "..", "Agents")
        def _load(name, fname):
            path = os.path.normpath(os.path.join(base, fname))
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            return mod
        cashflow_agent = _load("cashflow_agent", "cashflow_agent.py")
        sweep_agent = _load("sweep_agent", "sweep_agent.py")
        investment_agent = _load("investment_agent", "investment_agent.py")


class CashFlowNode(Node):
    def __init__(self, name: str = "cashflow"):
        super().__init__(name)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Expect unified payload keys; reuse agent handle_mcp
        inp = payload.get("cashflow") or payload
        return cashflow_agent.handle_mcp(inp)


class CashPositionNode(Node):
    def __init__(self, name: str = "cash_position"):
        super().__init__(name)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        inp = payload.get("cash_position") or payload
        try:
            from Agents import cash_position_agent
        except Exception:
            try:
                from agentic_sweeper import cash_position_agent
            except Exception:
                import importlib.util, sys, os
                base = os.path.join(os.path.dirname(__file__), "..", "Agents")
                path = os.path.normpath(os.path.join(base, "cash_position_agent.py"))
                spec = importlib.util.spec_from_file_location("cash_position_agent", path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules["cash_position_agent"] = mod
                spec.loader.exec_module(mod)
                cash_position_agent = mod

        return cash_position_agent.handle_mcp(inp)


class CashForecastNode(Node):
    def __init__(self, name: str = "cash_forecast"):
        super().__init__(name)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        inp = payload.get("cash_forecast") or payload
        try:
            from Agents import cashflow_forecast_agent
        except Exception:
            try:
                from agentic_sweeper import cashflow_forecast_agent
            except Exception:
                import importlib.util, sys, os
                base = os.path.join(os.path.dirname(__file__), "..", "Agents")
                path = os.path.normpath(os.path.join(base, "cashflow_forecast_agent.py"))
                spec = importlib.util.spec_from_file_location("cashflow_forecast_agent", path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules["cashflow_forecast_agent"] = mod
                spec.loader.exec_module(mod)
                cashflow_forecast_agent = mod

        return cashflow_forecast_agent.handle_mcp(inp)


class ReconciliationNode(Node):
    def __init__(self, name: str = "reconciliation"):
        super().__init__(name)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        inp = payload.get("reconciliation") or payload
        try:
            from Agents import reconciliation_agent
        except Exception:
            try:
                from agentic_sweeper import reconciliation_agent
            except Exception:
                import importlib.util, sys, os
                base = os.path.join(os.path.dirname(__file__), "..", "Agents")
                path = os.path.normpath(os.path.join(base, "reconciliation_agent.py"))
                spec = importlib.util.spec_from_file_location("reconciliation_agent", path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules["reconciliation_agent"] = mod
                spec.loader.exec_module(mod)
                reconciliation_agent = mod

        return reconciliation_agent.handle_mcp(inp)


class ReportingNode(Node):
    def __init__(self, name: str = "reporting"):
        super().__init__(name)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        inp = payload.get("reporting") or payload
        try:
            from Agents import reporting_agent
        except Exception:
            try:
                from agentic_sweeper import reporting_agent
            except Exception:
                import importlib.util, sys, os
                base = os.path.join(os.path.dirname(__file__), "..", "Agents")
                path = os.path.normpath(os.path.join(base, "reporting_agent.py"))
                spec = importlib.util.spec_from_file_location("reporting_agent", path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules["reporting_agent"] = mod
                spec.loader.exec_module(mod)
                reporting_agent = mod

        return reporting_agent.handle_mcp(inp)


class LiquidityNode(Node):
    def __init__(self, name: str = "liquidity"):
        super().__init__(name)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        inp = payload.get("liquidity") or payload
        # Attempt to import liquidity_agent from Agents package or fallback
        try:
            from Agents import liquidity_agent
        except Exception:
            try:
                from agentic_sweeper import liquidity_agent
            except Exception:
                import importlib.util, sys, os
                base = os.path.join(os.path.dirname(__file__), "..", "Agents")
                path = os.path.normpath(os.path.join(base, "liquidity_agent.py"))
                spec = importlib.util.spec_from_file_location("liquidity_agent", path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules["liquidity_agent"] = mod
                spec.loader.exec_module(mod)
                liquidity_agent = mod

        return liquidity_agent.handle_mcp(inp)


class SweepNode(Node):
    def __init__(self, name: str = "sweep"):
        super().__init__(name)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Sweep expects accounts or excess_cash depending on caller
        inp = payload.get("sweep") or payload
        return sweep_agent.handle_mcp(inp)


class InvestmentNode(Node):
    def __init__(self, name: str = "investment"):
        super().__init__(name)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        inp = payload.get("investment") or payload
        return investment_agent.handle_mcp(inp)


class LLMNode(Node):
    """Simple LLM node that formats a prompt and returns a summary string.

    Uses the InvestmentAgent LlmAdapter if available (lightweight adapter present
    in `Agents/investment_agent.py`) for consistent behavior with other agents.
    """

    def __init__(self, name: str = "llm"):
        super().__init__(name)
        # try to reuse an existing LlmAdapter class from investment_agent
        Adapter = getattr(investment_agent, "LlmAdapter", None)
        self.adapter = Adapter() if Adapter is not None else None

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # payload expected to contain a 'prompt' key or 'node_outputs' to summarize
        prompt = payload.get("prompt")
        if not prompt:
            # try to build prompt from node_outputs
            node_outputs = payload.get("node_outputs", {})
            prompt = "Summarize the following agent outputs:\n" + json.dumps(node_outputs, indent=2)

        if self.adapter and self.adapter.is_available():
            summary = self.adapter.generate(prompt)
        else:
            # programmatic fallback: return first 300 chars
            summary = "[LLM not configured] " + (prompt[:300] + ("..." if len(prompt) > 300 else ""))

        return {"summary": summary}
