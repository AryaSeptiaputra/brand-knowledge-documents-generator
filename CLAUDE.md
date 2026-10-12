# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Source of truth

Read these before changing behavior. When they conflict: **PRD > technical design > coding rules**. If none answers a decision, ask Arya instead of guessing.

- `docs/PRD.md` — product scope (Indonesian).
- `docs/technical-design.md` — layout, stack, API, module behavior (§9 is product rules), testing, and the Definition of Done (§12).
- `docs/coding-rules.md` — style only: function flow/job roles, naming and ordering inside classes, error and logging rules.
- `docs/design/ui-ux/` — screen PNGs, static HTML per screen (exact layout and markup), and `tokens.md` (Tailwind theme values). `docs/design/uml/` — class and sequence diagrams; class/method names follow them.

Do not edit the PRD, diagrams, technical design, coding rules, or `tokens.md` unless asked. Adding a dependency outside technical-design §3 requires asking first.

## Commands

Backend (from `backend/`, Python 3.13, managed with `uv`; never `pip install` here):

```bash
uv sync
uv run uvicorn brand_docs.main:app --reload          # http://127.0.0.1:8000; also serves frontend/dist if built
uv run ruff format --check && uv run ruff check && uv run mypy src
uv run pytest
uv run pytest tests/unit/test_services.py::test_checker_drops_fabricated_paragraphs   # single test
uv run pytest -k checker                              # by keyword
```

Frontend (from `frontend/`, pnpm 11.25.0). `pnpm` may not be on PATH on this machine; the local binaries work directly, and corepack ≥ 0.36 is at `%APPDATA%\npm\corepack` (the one in `Program Files\nodejs` is too old to download pnpm):

```bash
node_modules/.bin/biome check            # lint + format; must pass with no arguments
node_modules/.bin/tsc --noEmit
node_modules/.bin/vitest run
node_modules/.bin/vitest run src/features/write-data/YamlEditor.test.tsx   # single file
node_modules/.bin/vite build
"$APPDATA/npm/corepack" pnpm@11.25.0 add <pkg>    # keeps pnpm-lock.yaml consistent
```

Regenerate API types after any request/response change: start the backend, then `node_modules/.bin/openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/generated/schema.d.ts` and format it with Biome. Never hand-edit `schema.d.ts`. Arya often has a `--reload` dev server on port 8000; use another port rather than killing it.

PDF export needs GTK/Pango (MSYS2 `mingw-w64-x86_64-pango` and `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin`). WeasyPrint is imported lazily, so the app and tests run without it; PDF endpoints then return 503.

## Architecture

A user writes free-form YAML about a brand; the app turns it into three customer documents (Policy / *Kebijakan*, Guide / *Panduan*, Product Knowledge) as preview HTML and RAG-friendly PDFs. The core product rule: **every fact in a document comes from the YAML** — nothing on the composition path may introduce facts.

Request flow (`api/router.py` only coordinates; services are wired in `factory.py` and held on `app.state.services`):

1. `POST /api/analyze` — `DataValidator` (size and alias-expansion limits, `brand` required) → `FactExtractor` turns YAML into ordered `Fact`s with dot paths (keys as written) and source line numbers; a top-level `product`/`produk`/`products` key holds product knowledge → `DocumentGrouper` proposes which document types each unit (general section, product, product size attribute) goes into → `CompletenessAdvisor` suggestions (never rendered in documents) → in-memory `SessionStore` (sliding TTL, no database, nothing written to disk).
2. `PATCH /api/grouping` — user edits the mapping.
3. `POST /api/documents` — `DocumentComposer` builds structure from the grouping (headings and template blocks come from code, never the LLM). With `BKDG_USE_LLM=true`, Ollama writes 1–3 short paragraphs per section as structured `ComposedSection` JSON citing `source_paths`; on failure the section keeps only template blocks. `ContentChecker` then drops any LLM paragraph that cites unknown paths, introduces numbers not in its source facts, or introduces proper terms (checked per position; `&`/alphanumeric tokens always checked), recording it in `replaced_paragraphs`.
4. Preview/PDF — `HtmlRenderer` renders one Jinja template (`rendering/templates/document.html.j2`) for both; facts render as tables/lists/definition blocks from `Section.facts`. Source chips and the footnote appear only when `show_sources` (preview), never in PDFs. `PdfRenderer` calls WeasyPrint only through `_write_pdf`.

`llm/client.py` defines the `LlmClient` Protocol (kept so the model runner can be swapped) and `FakeLlmClient`; tests never call a real Ollama. Prompts live in `llm/prompts/*.j2`. Project errors live in `errors.py` and are mapped to HTTP statuses in `main.py`; error bodies are `{"errors": [{"message", "line"?, "column"?}]}`. Settings come only from `Settings` (env prefix `BKDG_`); every new setting goes into `backend/.env.example`.

Frontend (`frontend/src`): a 3-step workflow (write YAML → review grouping → preview & download). All API calls go through the typed `openapi-fetch` client in `api/client.ts`; server state lives in TanStack Query (hooks `features/workflow/useBrandWorkflow.ts`, `features/preview/useLogo.ts`), with `useState` only for UI state. Components in `components/ui/` are shadcn/ui on Radix with Tailwind tokens from `tokens.md`. The preview is a sandboxed `srcDoc` iframe (no `allow-scripts`) sized from the parent. UI copy is English; generated documents are Indonesian.

## Conventions that are easy to miss

- Function names encode role and reach (`coding-rules.md` §2.2–2.3): sub-processes are `_verb` and sit above the public process that calls them; external access (files, network, model, WeasyPrint) happens only in accessor methods that convert exceptions to project errors.
- Every regex and format string needs a comment stating its intent (`coding-rules.md` §2.6).
- `mypy --strict` must pass for `src`; do not disable lint/type rules globally.
- Files must use LF line endings; Biome fails on CRLF.
