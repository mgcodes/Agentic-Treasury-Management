import os
import json
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv(override=True)


class LlmAdapter:
    """Lightweight adapter placeholder (matches other agents)."""

    def __init__(self, endpoint: str = None, model: str = None, api_key: str = None):
        self.endpoint = endpoint or os.getenv("LLM_ENDPOINT")
        self.model = model or os.getenv("LLM_MODEL_NAME")
        self.api_key = api_key or os.getenv("LLM_API_KEY")

    def is_available(self) -> bool:
        return bool(self.endpoint and self.model and self.api_key)

    def generate(self, prompt: str) -> str:
        return f"[LLM simulated] Investment plan summary for prompt length {len(prompt)}"


class InvestmentAgent:
    def __init__(self, adapter: LlmAdapter = None):
        self.adapter = adapter or LlmAdapter()

    def propose_allocations(self, payload: Dict) -> Dict:
        """Create a simple allocation plan from excess cash, risk limits and instrument universe.

        Expected payload:
          {
            "excess_cash": 100000.0,
            "risk_limits": {"max_per_instrument": 0.25, "max_per_tenor": {"short":0.5,"medium":0.3,"long":0.2}},
            "universe": [{"id":"bondA","tenor":"short","expected_yield":0.01,"liquidity_score":0.9}, ...]
          }
        """
        # Allow the orchestrator to pass liquidity outputs in the shared context under `node_outputs`.
        # Prefer explicit `excess_cash`, otherwise try to derive from liquidity node output.
        excess = payload.get("excess_cash", None)
        if excess is None:
            try:
                node_outputs = payload.get("node_outputs", {})
                liq = node_outputs.get("liquidity", {}).get("output", {})
                overview = liq.get("overview", {}) if isinstance(liq, dict) else {}
                excess = overview.get("liquid_balance_estimate") or overview.get("total_balance") or 0
            except Exception:
                excess = 0
        excess = float(excess or 0)
        risk_limits = payload.get("risk_limits", {})
        universe: List[Dict] = payload.get("universe", [])

        # Basic validation
        if excess <= 0 or not universe:
            return {"error": "no excess cash or empty universe"}

        # Apply simple scoring: yield * liquidity_score
        for inst in universe:
            inst["score"] = float(inst.get("expected_yield", 0)) * float(inst.get("liquidity_score", 0))

        # Group by tenor
        tenor_buckets = {"short": [], "medium": [], "long": []}
        for inst in universe:
            t = inst.get("tenor", "medium")
            if t not in tenor_buckets:
                tenor_buckets[t] = []
            tenor_buckets[t].append(inst)

        # Determine tenor allocation weights from risk_limits or simple heuristic
        max_per_tenor = risk_limits.get("max_per_tenor", {"short": 0.5, "medium": 0.3, "long": 0.2})

        allocations = []
        remaining_cash = excess

        # Cap per instrument
        max_per_inst_frac = float(risk_limits.get("max_per_instrument", 0.25))
        max_per_inst_amt = excess * max_per_inst_frac if max_per_inst_frac > 0 else excess

        for tenor, bucket in tenor_buckets.items():
            if not bucket:
                continue

            tenor_budget = round(excess * float(max_per_tenor.get(tenor, 0)), 2)

            # weight instruments by score
            total_score = sum(i.get("score", 0) for i in bucket)
            if total_score <= 0:
                # equal-weight fallback
                per_inst = round(tenor_budget / len(bucket), 2)
                for inst in bucket:
                    amt = min(per_inst, max_per_inst_amt, remaining_cash)
                    allocations.append({"instrument": inst.get("id"), "tenor": tenor, "amount": round(amt, 2)})
                    remaining_cash -= amt
                continue

            for inst in bucket:
                frac = inst.get("score", 0) / total_score
                amt = round(tenor_budget * frac, 2)
                amt = min(amt, max_per_inst_amt, remaining_cash)
                if amt <= 0:
                    continue
                allocations.append({"instrument": inst.get("id"), "tenor": tenor, "amount": round(amt, 2)})
                remaining_cash -= amt

        # If any leftover cash remain, allocate to highest score across universe within caps
        if remaining_cash > 0:
            sorted_universe = sorted(universe, key=lambda x: x.get("score", 0), reverse=True)
            for inst in sorted_universe:
                if remaining_cash <= 0:
                    break
                already = sum(a["amount"] for a in allocations if a["instrument"] == inst.get("id"))
                can_put = min(max_per_inst_amt - already, remaining_cash)
                if can_put > 0:
                    allocations.append({"instrument": inst.get("id"), "tenor": inst.get("tenor"), "amount": round(can_put, 2)})
                    remaining_cash -= can_put

        # Produce simple summary and optional LLM summary
        total_allocated = round(sum(a["amount"] for a in allocations), 2)
        summary = {"excess_cash": excess, "total_allocated": total_allocated, "remaining_cash": round(remaining_cash, 2)}

        # allocations by tenor for clearer reporting
        alloc_by_tenor: Dict[str, Dict] = {}
        for a in allocations:
            t = a.get("tenor", "unknown")
            alloc_by_tenor.setdefault(t, {"total": 0.0, "instruments": []})
            alloc_by_tenor[t]["total"] = round(alloc_by_tenor[t]["total"] + float(a["amount"]), 2)
            alloc_by_tenor[t]["instruments"].append({"instrument": a["instrument"], "amount": a["amount"]})

        # Human-readable decision summary
        decision_lines: List[str] = []
        decision_lines.append(f"Applied tenor weights: {max_per_tenor}")
        decision_lines.append(f"Per-instrument cap: {round(max_per_inst_amt,2)}")
        for tenor, info in alloc_by_tenor.items():
            decision_lines.append(f"{tenor.capitalize()}: allocated {info['total']} across {len(info['instruments'])} instruments")
        if remaining_cash > 0:
            decision_lines.append(f"Remaining unallocated cash: {round(remaining_cash,2)}")
        else:
            decision_lines.append("All excess cash allocated.")

        decision_summary = " -- ".join(decision_lines)

        if self.adapter.is_available():
            prompt = f"Propose allocations for excess={excess}, universe_count={len(universe)}"
            llm_summary = self.adapter.generate(prompt)
        else:
            llm_summary = "LLM adapter not configured"

        return {
            "allocations": allocations,
            "summary": summary,
            "allocations_by_tenor": alloc_by_tenor,
            "decision_summary": decision_summary,
            "llm_summary": llm_summary,
        }


def run_investment_example():
    payload = {
        "excess_cash": 100000.0,
        "risk_limits": {"max_per_instrument": 0.25, "max_per_tenor": {"short": 0.5, "medium": 0.3, "long": 0.2}},
        "universe": [
            {"id": "inst_short_a", "tenor": "short", "expected_yield": 0.005, "liquidity_score": 0.95},
            {"id": "inst_short_b", "tenor": "short", "expected_yield": 0.006, "liquidity_score": 0.8},
            {"id": "inst_med_a", "tenor": "medium", "expected_yield": 0.02, "liquidity_score": 0.6},
            {"id": "inst_long_a", "tenor": "long", "expected_yield": 0.035, "liquidity_score": 0.4},
        ],
    }

    agent = InvestmentAgent()
    result = agent.propose_allocations(payload)
    print(json.dumps({"payload": payload, "proposal": result}, indent=2))
    # Print human-friendly report
    try:
        report = format_human_report(result)
        print("\n--- Human-friendly Investment Report ---\n")
        print(report)
    except Exception:
        pass


# MCP / A2A helpers
def agent_info() -> Dict:
    return {"name": "InvestmentAgent", "version": "0.1", "capabilities": ["propose_allocations", "mcp_handle", "a2a_handle"]}


def handle_mcp(payload: Dict) -> Dict:
    try:
        inner = payload.get("input") if isinstance(payload, dict) and "input" in payload else payload
        agent = InvestmentAgent()
        out = agent.propose_allocations(inner)
        return {"status": "success", "output": out}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_a2a(message: Dict) -> Dict:
    try:
        mtype = message.get("type")
        sender = message.get("from")
        if mtype == "request_investment_proposal":
            agent = InvestmentAgent()
            proposal = agent.propose_allocations(message.get("payload", {}))
            return {"from": agent_info()["name"], "to": sender, "type": "response_investment_proposal", "payload": proposal}
        else:
            return {"from": agent_info()["name"], "to": sender, "type": "error", "payload": {"error": "unsupported message type"}}
    except Exception as e:
        return {"from": agent_info()["name"], "to": message.get("from"), "type": "error", "payload": {"error": str(e)}}


if __name__ == "__main__":
    run_investment_example()


def format_human_report(proposal: Dict) -> str:
    """Return a multi-line human-friendly report for the proposal dict."""
    if not isinstance(proposal, dict):
        return "No proposal available"

    out_lines: List[str] = []
    summary = proposal.get("summary", {})
    out_lines.append(f"As-Of: N/A")
    out_lines.append(f"Excess Cash: {summary.get('excess_cash', 0):,.2f}")
    out_lines.append(f"Total Allocated: {summary.get('total_allocated', 0):,.2f}")
    out_lines.append(f"Remaining Cash: {summary.get('remaining_cash', 0):,.2f}")
    out_lines.append("")
    out_lines.append("Allocations by Tenor:")
    alloc_by_tenor = proposal.get("allocations_by_tenor", {})
    for tenor in ["short", "medium", "long"]:
        info = alloc_by_tenor.get(tenor)
        if not info:
            continue
        out_lines.append(f"  - {tenor.capitalize()}: {info.get('total',0):,.2f} across {len(info.get('instruments',[]))} instruments")
        for inst in info.get("instruments", []):
            out_lines.append(f"      • {inst.get('instrument')}: {inst.get('amount',0):,.2f}")

    out_lines.append("")
    out_lines.append("Decision summary:")
    out_lines.append(proposal.get("decision_summary", "(none)"))

    llm = proposal.get("llm_summary")
    if llm:
        out_lines.append("")
        out_lines.append("LLM Summary:")
        out_lines.append(llm)

    return "\n".join(out_lines)
