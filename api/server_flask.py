from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict
from flask import Flask, request, jsonify, abort
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {or unset API_KEY in the environment to allow unauthenticated access):"origins": "*"}})

API_KEY = os.getenv("API_KEY") or os.getenv("LLM_API_KEY")


def check_key(x_api_key: str | None):
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        abort(401, description="unauthorized")


# Dynamic fallback to local investment agent implementation if package not available
try:
    from agentic_sweeper import investment_agent
except Exception:
    import importlib.util, sys
    agents_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "Agents", "investment_agent.py"))
    spec = importlib.util.spec_from_file_location("investment_agent", agents_path)
    investment_agent = importlib.util.module_from_spec(spec)
    sys.modules["investment_agent"] = investment_agent
    spec.loader.exec_module(investment_agent)


@app.route('/mcp/invest', methods=['POST'])
def mcp_invest():
    check_key(request.headers.get('x-api-key'))
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(investment_agent.handle_mcp(payload))
    except Exception as e:
        return (jsonify({"error": str(e)}), 500)


@app.route('/a2a/invest', methods=['POST'])
def a2a_invest():
    check_key(request.headers.get('x-api-key'))
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(investment_agent.handle_a2a(payload))
    except Exception as e:
        return (jsonify({"error": str(e)}), 500)


@app.route('/orchestrator/run', methods=['POST'])
def orchestrator_run():
    check_key(request.headers.get('x-api-key'))
    payload = request.get_json(silent=True)

    # If no payload provided, fall back to bundled example payload
    if not payload:
        try:
            examples_path = Path(__file__).resolve().parents[1] / 'examples' / 'agentic_input.json'
            if examples_path.exists():
                payload = json.load(open(examples_path, 'r'))
            else:
                payload = {}
        except Exception:
            payload = {}

    try:
        from graph.orchestrator import run_orchestrator
    except Exception as e:
        return (jsonify({"error": f"orchestrator import failed: {e}"}), 500)

    try:
        out = run_orchestrator(payload or {})
        return jsonify(out)
    except Exception as e:
        return (jsonify({"error": f"orchestrator run failed: {e}"}), 500)


if __name__ == '__main__':
    # Development runner
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)), debug=True)
