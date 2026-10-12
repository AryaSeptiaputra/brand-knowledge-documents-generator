# Backend

The backend uses Python 3.13 and `uv`.

```powershell
uv sync
Copy-Item .env.example .env
uv run --env-file .env uvicorn brand_docs.main:app --app-dir src --reload
```

The default `BKDG_USE_LLM=false` runs the document fallback without Ollama. To enable the local model, set `BKDG_USE_LLM=true` and configure `BKDG_OLLAMA_HOST` and `BKDG_MODEL_NAME` in the environment before starting the server.

Run the backend checks from this directory with `uv run ruff format --check`, `uv run ruff check`, `uv run mypy src`, and `uv run pytest`.
