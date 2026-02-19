import os
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict
from pydantic import BaseModel

try:
    from agentic_sweeper import investment_agent
except Exception:
    # Fall back to loading the InvestmentAgent implementation from the local Agents/ folder
    import importlib.util
    import sys
    import os

    agents_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "Agents", "investment_agent.py"))
    spec = importlib.util.spec_from_file_location("investment_agent", agents_path)
    investment_agent = importlib.util.module_from_spec(spec)
    sys.modules["investment_agent"] = investment_agent
    spec.loader.exec_module(investment_agent)

API_KEY = os.getenv("API_KEY") or os.getenv("LLM_API_KEY")
ALLOW_NO_AUTH = os.getenv("ALLOW_NO_AUTH") == "1"

app = FastAPI(title="Treasury Agents API")

# Allow local web UI development to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MCPRequest(BaseModel):
    input: dict


def check_key(x_api_key: str | None):
    if ALLOW_NO_AUTH:
        # Development override: allow unauthenticated requests when explicitly enabled
        return
    if not API_KEY:
        # no key configured in env; allow local dev
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.post("/mcp/invest")
async def mcp_invest(req: Request, x_api_key: str | None = Header(None)):
    check_key(x_api_key)
    payload = await req.json()
    return investment_agent.handle_mcp(payload)


@app.post("/a2a/invest")
async def a2a_invest(req: Request, x_api_key: str | None = Header(None)):
    check_key(x_api_key)
    msg = await req.json()
    return investment_agent.handle_a2a(msg)


# Run the orchestrator graph and return combined outputs
@app.post("/orchestrator/run")
async def run_orchestrator_endpoint(req: Request, x_api_key: str | None = Header(None)) -> Dict[str, Any]:
    check_key(x_api_key)
    payload = await req.json()
    # If client did not provide a payload or provided an empty object,
    # fall back to the example payload bundled with the repo so the UI
    # can retrieve a realistic demo response without sending data.
    try:
        if not payload:
            from pathlib import Path
            import json as _json
            examples_path = Path(__file__).resolve().parents[0].parent / 'examples' / 'agentic_input.json'
            if examples_path.exists():
                payload = _json.load(open(examples_path, 'r'))
    except Exception:
        # ignore fallback errors and continue with whatever payload we have
        pass
    try:
        from graph.orchestrator import run_orchestrator
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"orchestrator import failed: {e}")

    try:
        out = run_orchestrator(payload or {})
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"orchestrator run failed: {e}")
