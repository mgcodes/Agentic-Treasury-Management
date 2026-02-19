import os
import json
from typing import Dict, List, Tuple
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
        return f"[LLM simulated] Reconciliation summary for prompt length {len(prompt)}"


class ReconciliationAgent:
    """Performs simple bank reconciliation and transaction matching."""

    def __init__(self, adapter: LlmAdapter = None):
        self.adapter = adapter or LlmAdapter()

    def match_transactions(self, bank_tx: List[Dict], ledger_tx: List[Dict], tol: float = 0.01) -> Dict:
        """Match bank and ledger transactions using amount and optional reference/date heuristics.

        bank_tx and ledger_tx are lists of dicts with at least 'id' and 'amount' and optional 'date'/'ref'.
        Returns matched pairs, unmatched bank, unmatched ledger, exceptions.
        """
        # Normalize amounts to floats
        bank = [{**b, "amount": float(b.get("amount", 0))} for b in (bank_tx or [])]
        ledger = [{**l, "amount": float(l.get("amount", 0))} for l in (ledger_tx or [])]

        matched: List[Tuple[Dict, Dict]] = []
        unmatched_bank = bank.copy()
        unmatched_ledger = ledger.copy()

        # simple exact/near-amount matching first
        for b in list(unmatched_bank):
            found = None
            for l in list(unmatched_ledger):
                if abs(b["amount"] - l["amount"]) <= tol:
                    found = l
                    break
            if found:
                matched.append((b, found))
                unmatched_bank.remove(b)
                unmatched_ledger.remove(found)

        # heuristic match by reference if present
        if unmatched_bank and unmatched_ledger:
            for b in list(unmatched_bank):
                bref = str(b.get("ref", "")).lower()
                if not bref:
                    continue
                for l in list(unmatched_ledger):
                    lref = str(l.get("ref", "")).lower()
                    if lref and (bref in lref or lref in bref):
                        matched.append((b, l))
                        unmatched_bank.remove(b)
                        unmatched_ledger.remove(l)
                        break

        # Build reconciled ledger as ledger + unmatched_bank as import candidates
        reconciled = {l.get("id"): l for l in ledger}
        # tag matched
        matched_report = []
        for b, l in matched:
            matched_report.append({"bank_id": b.get("id"), "ledger_id": l.get("id"), "amount": b.get("amount")})

        exceptions = []
        # Unmatched items are exceptions
        for b in unmatched_bank:
            exceptions.append({"source": "bank", "id": b.get("id"), "amount": b.get("amount")})
        for l in unmatched_ledger:
            exceptions.append({"source": "ledger", "id": l.get("id"), "amount": l.get("amount")})

        overview = {
            "matched_count": len(matched_report),
            "matched": matched_report,
            "unmatched_bank": unmatched_bank,
            "unmatched_ledger": unmatched_ledger,
            "exceptions": exceptions,
        }

        if self.adapter.is_available():
            prompt = "Reconciliation overview: " + json.dumps(overview)
            human = self.adapter.generate(prompt)
        else:
            human = f"Matched: {len(matched_report)}, Exceptions: {len(exceptions)}"

        return {"overview": overview, "human_summary": human}


def agent_info() -> Dict:
    return {"name": "ReconciliationAgent", "version": "0.1", "capabilities": ["match_transactions", "mcp_handle", "a2a_handle"]}


def handle_mcp(payload: Dict) -> Dict:
    try:
        inner = payload.get("input") if isinstance(payload, dict) and "input" in payload else payload
        bank = inner.get("bank_transactions") or inner.get("bank") or []
        ledger = inner.get("ledger_transactions") or inner.get("ledger") or []
        agent = ReconciliationAgent()
        out = agent.match_transactions(bank, ledger, tol=float(inner.get("tolerance", 0.01)))
        return {"status": "success", "output": out}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_a2a(message: Dict) -> Dict:
    try:
        mtype = message.get("type")
        sender = message.get("from")
        if mtype == "request_reconciliation":
            agent = ReconciliationAgent()
            payload = message.get("payload", {})
            overview = agent.match_transactions(payload.get("bank_transactions", []), payload.get("ledger_transactions", []))
            return {"from": agent_info()["name"], "to": sender, "type": "response_reconciliation", "payload": overview}
        else:
            return {"from": agent_info()["name"], "to": sender, "type": "error", "payload": {"error": "unsupported message type"}}
    except Exception as e:
        return {"from": agent_info()["name"], "to": message.get("from"), "type": "error", "payload": {"error": str(e)}}


if __name__ == "__main__":
    sample_bank = [{"id": "b1", "amount": 100.0, "ref": "INV-100"}, {"id": "b2", "amount": 50.0}]
    sample_ledger = [{"id": "l1", "amount": 100.0, "ref": "INV-100"}, {"id": "l2", "amount": 75.0}]
    a = ReconciliationAgent()
    import json as _j
    print(_j.dumps(a.match_transactions(sample_bank, sample_ledger), indent=2))
