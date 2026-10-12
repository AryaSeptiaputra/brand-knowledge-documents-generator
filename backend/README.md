# Backend

The backend uses Python 3.13 and `uv`.

```powershell
uv sync
Copy-Item .env.example .env
uv run --env-file .env uvicorn brand_docs.main:app --app-dir src --reload
```

The default `BKDG_USE_LLM=false` runs the document fallback without Ollama. To enable the local model, set `BKDG_USE_LLM=true` and configure `BKDG_OLLAMA_HOST` and `BKDG_MODEL_NAME` in the environment before starting the server.

Upload limits are configurable: `BKDG_MAX_LOGO_BYTES` (logo size), `BKDG_MAX_YAML_BYTES` (YAML size), and `BKDG_MAX_YAML_NODES` (values after YAML aliases are expanded).

## PDF export on Windows (GTK)

WeasyPrint needs the Pango/GTK libraries to create PDFs. It is imported only when a PDF is requested, so the server, the preview, and the tests run without them; without GTK the PDF endpoints return a 500 error with `Unable to render the requested PDF.`

1. Install [MSYS2](https://www.msys2.org/) with the default path `C:\msys64`.
2. In the MSYS2 shell, install Pango:

   ```sh
   pacman -S mingw-w64-x86_64-pango
   ```

3. Point WeasyPrint at the libraries before starting the server (PowerShell):

   ```powershell
   $env:WEASYPRINT_DLL_DIRECTORIES = "C:\msys64\mingw64\bin"
   ```

4. Check the installation with `uv run python -c "import weasyprint"`.

## Checks

Run the backend checks from this directory with `uv run ruff format --check`, `uv run ruff check`, `uv run mypy src`, and `uv run pytest`.
