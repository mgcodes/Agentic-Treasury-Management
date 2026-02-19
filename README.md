# Agentic Sweeper — LangGraph-enabled Sweeping Agent

Quick run

Hugging Face is the default LLM (recommended for offline/open-source use).

```bash
pip install -r requirements.txt
python run_langgraph.py examples/agentic_input.json --agentic
```

Run with OpenAI (cloud):

```bash
pip install -r requirements.txt
pip install openai
setx OPENAI_API_KEY "sk-..."   # Windows, or use PowerShell to set env
python run_langgraph.py examples/agentic_input.json --agentic --llm
```

Notes
- If `langgraph` is installed the runner will attempt to build and execute a flow.
- If `openai` or `OPENAI_API_KEY` are missing the runner falls back to a deterministic mock LLM.
- For Hugging Face models, set `HF_MODEL` environment variable to choose a model (default: `google/flan-t5-small`). Use `--hf` to force HF explicitly; use `--llm` to prefer OpenAI.
