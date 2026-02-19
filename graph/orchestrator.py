
"""
Orchestrator: One-to-many (tree) LangGraph from a central hub to all agent nodes
in parallel, then merge back to a single node.

This version OFFLOADS ALL NODE EXECUTION to a worker thread using asyncio.to_thread(...)
so any synchronous calls inside nodes (including os.getcwd(), file I/O, pandas, etc.)
won't block the ASGI event loop used by `langgraph dev`.

Folder (example):
    project-root/
    └─ graphs/
       ├─ orchestrator.py   <-- this file
       ├─ nodes.py          <-- your node classes
       └─ node.py           <-- your lightweight Graph runner (optional)

langgraph.json (in the same folder):
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "orchestrator": "./orchestrator.py:orchestrator"
  },
  "env": ".env"
}

Invocation (Studio/SDK):
{
  "context": { ... your business payload dict ... }
}
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from typing_extensions import TypedDict, Annotated


# --------------------------------------------------------------------------------------
# 0) Robust imports for your internal runner and node classes
# --------------------------------------------------------------------------------------
# Try package-style first; fall back to relative; finally file-path load.
try:
    from graphs.node import Graph
    from graphs.nodes import (
        CashPositionNode, ReconciliationNode, CashForecastNode, ReportingNode,
        CashFlowNode, LiquidityNode, SweepNode, InvestmentNode, LLMNode,
    )
except Exception:
    try:
        from .node import Graph
        from .nodes import (
            CashPositionNode, ReconciliationNode, CashForecastNode, ReportingNode,
            CashFlowNode, LiquidityNode, SweepNode, InvestmentNode, LLMNode,
        )
    except Exception:
        import importlib.util, sys
        BASE_DIR = Path(__file__).resolve().parent

        def _load(name: str, filename: str):
            path = BASE_DIR / filename
            spec = importlib.util.spec_from_file_location(name, str(path))
            if not spec or not spec.loader:
                raise ImportError(f"Cannot load {filename} as {name}")
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            sys.modules[name] = mod
            spec.loader.exec_module(mod)  # type: ignore[call-arg]
            return mod

        node_mod = _load("graphs.node", "node.py")
        nodes_mod = _load("graphs.nodes", "nodes.py")

        Graph = node_mod.Graph  # type: ignore[attr-defined]
        CashPositionNode = getattr(nodes_mod, "CashPositionNode", None)
        ReconciliationNode = getattr(nodes_mod, "ReconciliationNode", None)
        CashForecastNode = getattr(nodes_mod, "CashForecastNode", None)
        ReportingNode = getattr(nodes_mod, "ReportingNode", None)
        CashFlowNode = getattr(nodes_mod, "CashFlowNode")
        LiquidityNode = getattr(nodes_mod, "LiquidityNode", None)
        SweepNode = getattr(nodes_mod, "SweepNode")
        InvestmentNode = getattr(nodes_mod, "InvestmentNode")
        LLMNode = getattr(nodes_mod, "LLMNode")


# --------------------------------------------------------------------------------------
# 1) LangGraph State + reducer for parallel merges
# --------------------------------------------------------------------------------------
def _merge_context(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Reducer to merge two context dicts during parallel fan-out.
    - Merges nested "node_outputs" dicts instead of overwriting
    - For other dict keys, shallow-merge dicts; last-writer-wins for scalars
    """
    a = dict(a or {})
    b = dict(b or {})
    out: Dict[str, Any] = dict(a)

    for k, v in b.items():
        if k == "node_outputs":
            ao = dict(out.get("node_outputs") or {})
            bo = dict(v or {})
            ao.update(bo)
            out["node_outputs"] = ao
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}  # type: ignore[index]
        else:
            out[k] = v
    return out


class OrchestratorState(TypedDict, total=False):
    # Shared working payload across all nodes. Annotated with a reducer so
    # parallel updates safely merge at fan-in.
    context: Annotated[Dict[str, Any], _merge_context]


# --------------------------------------------------------------------------------------
# 2) Helpers to bridge your internal nodes into LangGraph nodes (NON-BLOCKING)
# --------------------------------------------------------------------------------------
def _ensure_ctx(state: OrchestratorState) -> Dict[str, Any]:
    """
    Return a per-node shallow copy of context so each branch works in isolation
    (important for parallel execution).
    """
    return dict(state.get("context") or {})

def _record_output(ctx: Dict[str, Any], name: str, output: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Mirror your runner's node_outputs aggregation in the shared context.
    Each node writes an entry by its name.
    """
    node_outputs = dict(ctx.get("node_outputs") or {})
    node_outputs[name] = output if isinstance(output, dict) else {"ok": True}
    ctx["node_outputs"] = node_outputs
    return ctx

def _call_node_logic_sync(node_obj: Any, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Synchronous entry for node logic. We call THIS in a worker thread via asyncio.to_thread.
    Supports common method names:
      - run / invoke / execute / process
      - or callable instance
    Allows nodes that mutate ctx in-place and return None.
    """
    for attr in ("run", "invoke", "execute", "process"):
        if hasattr(node_obj, attr):
            fn: Callable = getattr(node_obj, attr)
            return fn(ctx)
    if callable(node_obj):
        return node_obj(ctx)
    raise TypeError(f"Node object {node_obj!r} exposes no supported execution method")

async def _run_node_offloop(node_factory: Callable[[], Any], ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Create the node and execute its synchronous logic OFF the event loop.
    This prevents any os.getcwd(), open(), pandas, etc. from blocking ASGI.
    """
    node = node_factory()
    # Important: pass the per-branch ctx copy so mutations are isolated
    return await asyncio.to_thread(_call_node_logic_sync, node, ctx)


# --------------------------------------------------------------------------------------
# 3) Per‑stage wrappers (each one is a LangGraph node; all NON-BLOCKING)
# --------------------------------------------------------------------------------------
# Each wrapper:
#   1) takes a COPY of the context
#   2) runs node logic in a worker thread (non-blocking)
#   3) merges returned deltas
#   4) records node output under ctx["node_outputs"][<name>]
#   5) returns {"context": ctx} for reducer-based fan-in merge

async def cash_position(state: OrchestratorState, *, config=None) -> OrchestratorState:
    ctx = _ensure_ctx(state)
    if CashPositionNode is None:
        return {"context": ctx}
    out = await _run_node_offloop(CashPositionNode, ctx)
    if isinstance(out, dict): ctx.update(out)
    return {"context": _record_output(ctx, "cash_position", out if isinstance(out, dict) else None)}

async def reconciliation(state: OrchestratorState, *, config=None) -> OrchestratorState:
    ctx = _ensure_ctx(state)
    if ReconciliationNode is None:
        return {"context": ctx}
    out = await _run_node_offloop(ReconciliationNode, ctx)
    if isinstance(out, dict): ctx.update(out)
    return {"context": _record_output(ctx, "reconciliation", out if isinstance(out, dict) else None)}

async def liquidity(state: OrchestratorState, *, config=None) -> OrchestratorState:
    ctx = _ensure_ctx(state)
    if LiquidityNode is None:
        return {"context": ctx}
    out = await _run_node_offloop(LiquidityNode, ctx)
    if isinstance(out, dict): ctx.update(out)
    return {"context": _record_output(ctx, "liquidity", out if isinstance(out, dict) else None)}

async def cash_forecast(state: OrchestratorState, *, config=None) -> OrchestratorState:
    ctx = _ensure_ctx(state)
    if CashForecastNode is None:
        return {"context": ctx}
    out = await _run_node_offloop(CashForecastNode, ctx)
    if isinstance(out, dict): ctx.update(out)
    return {"context": _record_output(ctx, "cash_forecast", out if isinstance(out, dict) else None)}

async def cashflow(state: OrchestratorState, *, config=None) -> OrchestratorState:
    ctx = _ensure_ctx(state)
    out = await _run_node_offloop(CashFlowNode, ctx)
    if isinstance(out, dict): ctx.update(out)
    return {"context": _record_output(ctx, "cashflow", out if isinstance(out, dict) else None)}

async def sweep(state: OrchestratorState, *, config=None) -> OrchestratorState:
    ctx = _ensure_ctx(state)
    out = await _run_node_offloop(SweepNode, ctx)
    if isinstance(out, dict): ctx.update(out)
    return {"context": _record_output(ctx, "sweep", out if isinstance(out, dict) else None)}

async def investment(state: OrchestratorState, *, config=None) -> OrchestratorState:
    ctx = _ensure_ctx(state)
    out = await _run_node_offloop(InvestmentNode, ctx)
    if isinstance(out, dict): ctx.update(out)
    return {"context": _record_output(ctx, "investment", out if isinstance(out, dict) else None)}

async def reporting(state: OrchestratorState, *, config=None) -> OrchestratorState:
    ctx = _ensure_ctx(state)
    if ReportingNode is None:
        return {"context": ctx}
    out = await _run_node_offloop(ReportingNode, ctx)
    if isinstance(out, dict): ctx.update(out)
    return {"context": _record_output(ctx, "reporting", out if isinstance(out, dict) else None)}

async def llm(state: OrchestratorState, *, config=None) -> OrchestratorState:
    ctx = _ensure_ctx(state)
    out = await _run_node_offloop(LLMNode, ctx)
    if isinstance(out, dict):
        ctx.update(out)
        if "summary" in out:
            ctx["summary"] = out["summary"]  # convenient top-level summary
    return {"context": _record_output(ctx, "llm", out if isinstance(out, dict) else None)}


# --------------------------------------------------------------------------------------
# 4) Graph factory (this is what langgraph.json references)
# --------------------------------------------------------------------------------------
def orchestrator():
    """
    Factory function that RETURNS a compiled LangGraph graph.
    The LangGraph server will import this symbol and call it.
    """
    from langgraph.graph import StateGraph, END  # import INSIDE the factory

    builder = StateGraph(OrchestratorState)

    # Core utility nodes
    async def central_hub(state: OrchestratorState, *, config=None) -> OrchestratorState:
        return state

    async def merge_results(state: OrchestratorState, *, config=None) -> OrchestratorState:
        ctx = dict(state.get("context") or {})
        node_outputs = ctx.get("node_outputs", {})
        if isinstance(node_outputs, dict) and isinstance(node_outputs.get("llm"), dict):
            summary = node_outputs["llm"].get("summary")
            if summary is not None:
                ctx["summary"] = summary
        return {"context": ctx}

    builder.add_node("central_hub", central_hub)
    builder.add_node("merge_results", merge_results)

    # Agent nodes (conditionally add if class exists)
    children: list[str] = []

    if CashPositionNode is not None:
        builder.add_node("cash_position", cash_position); children.append("cash_position")
    if ReconciliationNode is not None:
        builder.add_node("reconciliation", reconciliation); children.append("reconciliation")
    if LiquidityNode is not None:
        builder.add_node("liquidity", liquidity); children.append("liquidity")
    if CashForecastNode is not None:
        builder.add_node("cash_forecast", cash_forecast); children.append("cash_forecast")

    builder.add_node("cashflow", cashflow);       children.append("cashflow")
    builder.add_node("sweep", sweep);             children.append("sweep")
    builder.add_node("investment", investment);   children.append("investment")

    if ReportingNode is not None:
        builder.add_node("reporting", reporting); children.append("reporting")

    builder.add_node("llm", llm);                 children.append("llm")

    if not children:
        raise RuntimeError("No agent nodes available to fan out to.")

    # Entry point
    builder.set_entry_point("central_hub")

    # Fan-out: add an edge from hub to each child (portable, no Send() dependency)
    for child in children:
        builder.add_edge("central_hub", child)

    # Fan-in: each child returns to merge_results
    for child in children:
        builder.add_edge(child, "merge_results")

    # Terminate
    builder.add_edge("merge_results", END)

    # Compile and RETURN the compiled graph
    return builder.compile(name="orchestrator")


# --------------------------------------------------------------------------------------
# 5) (Optional) Legacy internal runner helpers (unchanged)
# --------------------------------------------------------------------------------------
def build_graph() -> Graph:
    g = Graph()
    if CashPositionNode is not None: g.add_node(CashPositionNode())
    if ReconciliationNode is not None: g.add_node(ReconciliationNode())
    if LiquidityNode is not None: g.add_node(LiquidityNode())
    if CashForecastNode is not None: g.add_node(CashForecastNode())
    g.add_node(CashFlowNode()); g.add_node(SweepNode()); g.add_node(InvestmentNode())
    if ReportingNode is not None: g.add_node(ReportingNode())
    g.add_node(LLMNode())

    if CashPositionNode is not None: g.add_step("cash_position")
    if ReconciliationNode is not None: g.add_step("reconciliation")
    if LiquidityNode is not None: g.add_step("liquidity")
    if CashForecastNode is not None: g.add_step("cash_forecast")
    g.add_step("cashflow"); g.add_step("sweep"); g.add_step("investment")
    if ReportingNode is not None: g.add_step("reporting")
    g.add_step("llm")
    return g

def run_orchestrator(payload: Dict[str, Any]) -> Dict[str, Any]:
    g = build_graph()
    context = dict(payload or {}) if isinstance(payload, dict) else {}
    result_ctx = g.run(context)
    node_outputs = result_ctx.get("node_outputs", {})
    overall_summary = node_outputs.get("llm", {}).get("summary") if node_outputs.get("llm") else None
    return {"node_outputs": node_outputs, "summary": overall_summary}


# if __name__ == "__main__":
#     # Balanced test payload exercising all nodes
    # payload = {
    #     "accounts": [
    #         {"id": "acct_main", "balance": 30000},
    #         {"id": "acct_oper", "balance": 15000},
    #         {"id": "acct_reserve", "balance": 5000},
    #     ],
    #     "bank_transactions": [
    #         {"id": "b1", "date": "2026-01-14", "amount": 12000, "type": "credit", "description": "AR payment inv-100"},
    #         {"id": "b2", "date": "2026-01-14", "amount": -3000, "type": "debit", "description": "Payroll"},
    #         {"id": "b3", "date": "2026-01-15", "amount": -500, "type": "debit", "description": "Bank fee"},
    #         {"id": "b4", "date": "2026-01-15", "amount": 7000, "type": "credit", "description": "Wire from client"},
    #         {"id": "b_unmatched", "date": "2026-01-15", "amount": -123, "type": "debit", "description": "Unmatched small item"},
    #     ],
    #     "ledger_transactions": [
    #         {"id": "l1", "date": "2026-01-14", "amount": 12000, "type": "credit", "description": "AR payment inv-100"},
    #         {"id": "l2", "date": "2026-01-14", "amount": -3000, "type": "debit", "description": "Payroll"},
    #         {"id": "l3", "date": "2026-01-15", "amount": -500, "type": "debit", "description": "Bank fee"},
    #         {"id": "l4", "date": "2026-01-15", "amount": 7000, "type": "credit", "description": "Wire from client"},
    #     ],
    #     "inflows": [
    #         {"date": "2026-01-16", "amount": 10000, "source": "expected_AR"},
    #         {"date": "2026-01-17", "amount": 5000, "source": "scheduled_receipt"},
    #     ],
    #     "outflows": [
    #         {"date": "2026-01-16", "amount": 4000, "purpose": "supplier_payments"},
    #         {"date": "2026-01-18", "amount": 2000, "purpose": "short_term_liabilities"},
    #     ],
    #     "ap_schedule": [
    #         {"id": "ap1", "due_date": "2026-01-16", "amount": 4000, "vendor": "Supplier A"},
    #         {"id": "ap2", "due_date": "2026-01-20", "amount": 8000, "vendor": "Supplier B"},
    #     ],
    #     "ar_schedule": [
    #         {"id": "ar1", "due_date": "2026-01-16", "amount": 10000, "customer": "Client A"},
    #     ],
    #     "forecast_days": 14,
    #     "sweep_rules": {
    #         "min_balance": 5000,
    #         "target_balance": 15000,
    #         "sweep_from": ["acct_oper", "acct_reserve"],
    #         "sweep_to": "acct_main",
    #     },
    #     "investment_preferences": {
    #         "risk_tolerance": "conservative",
    #         "max_allocation_per_instrument": 0.5,
    #         "min_liquidity_score": 0.5,
    #     },
    #     "universe": [
    #         {"id": "inst1", "tenor": "overnight", "expected_yield": 0.0005, "liquidity_score": 0.95},
    #         {"id": "inst2", "tenor": "1m", "expected_yield": 0.002, "liquidity_score": 0.8},
    #         {"id": "inst3", "tenor": "3m", "expected_yield": 0.01, "liquidity_score": 0.6},
    #     ],
    #     "meta": {"run_id": "test-balanced-2026-01-16", "notes": "Payload crafted to produce outputs from all agents"},
    # }

    # import json
    # try:
    #     out = run_orchestrator(payload)
    #     print(json.dumps(out, indent=2))
    # except Exception:
    #     import traceback
    #     traceback.print_exc()
