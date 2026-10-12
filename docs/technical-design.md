# Technical Design — Brand Knowledge Document Generator

**Version:** 0.1 · **Date:** 2026-10-12 · **Owner:** Arya · **For:** anyone (human or AI model) building this project

This document describes **what is built and how it fits together**. Code-writing style is in [`coding-rules.md`](coding-rules.md); product scope is in [`PRD.md`](PRD.md).

When sources conflict: **PRD > this document > coding-rules.md > personal habits.**
If none of them answers a decision, **stop and ask Arya** — do not guess and build.

> The PRD is written in Indonesian. Key terms: *Kebijakan* = Policy, *Panduan* = Guide, *Product Knowledge* = Product Knowledge, *pengetahuan umum brand* = general brand knowledge, *pengetahuan produk* = product knowledge, *saran kelengkapan* = completeness suggestions, *rujukan sumber* = source references, *pratinjau* = preview.

**Design references** (exported from the design canvases):
- UML: [`design/uml/`](design/uml/) — use case, activity, system and per-module sequence, analysis and design class diagrams.
- UI: [`design/ui-ux/`](design/ui-ux/) — screen PNGs, static HTML per screen (`html/`), and design tokens (`tokens.md`).

---

## 1. Working agreement

1. **Do only what is asked.** No features, endpoints, dependencies, or refactors outside the task. Note anything out of scope at the end of your report.
2. **MVP non-goals are not built:** a chatbot/RAG of our own, importing data from websites/PDFs, user accounts, multiple languages, internal/CS versions, a database (PRD §3).
3. **Document content comes 100% from the user's data.** No sentence may state a fact that is not in the YAML. This is the most important product rule; all code on the document-composition path must uphold it.
4. **Small and testable.** One change = one purpose, with tests.
5. **Report honestly.** If tests fail or a step was skipped, say so. Do not claim "done" before §12 passes.

## 2. Repository layout

```
brand-knowledge-document-generator/
├─ docs/                 PRD, coding rules, this document, design exports
├─ backend/              Python (uv)
│  ├─ pyproject.toml
│  ├─ .env.example
│  ├─ src/brand_docs/
│  │  ├─ main.py         create_app(): FastAPI + serve frontend/dist when present
│  │  ├─ settings.py     Settings (pydantic-settings)
│  │  ├─ errors.py       project error classes (§7)
│  │  ├─ factory.py      build_*/create_* functions that wire services and the SessionStore
│  │  ├─ utils/
│  │  │  ├─ logger.py    setup_logger(name)
│  │  │  └─ text.py      humanize_key, format_fact_sentence (§9.3)
│  │  ├─ api/
│  │  │  ├─ router.py    ApiRouter: all endpoints
│  │  │  └─ schemas.py   request/response DTOs (AnalyzeRequest, AnalyzeResponse, …)
│  │  ├─ domain/
│  │  │  ├─ enums.py     DataKind, DocumentType, ParagraphOrigin, UnitKind
│  │  │  └─ models.py    BrandData, Fact, Product, Grouping, GroupingEntry, Document, Section, …, BrandLogo
│  │  ├─ services/
│  │  │  ├─ validator.py DataValidator
│  │  │  ├─ extractor.py FactExtractor
│  │  │  ├─ grouper.py   DocumentGrouper
│  │  │  ├─ advisor.py   CompletenessAdvisor
│  │  │  ├─ composer.py  DocumentComposer
│  │  │  └─ checker.py   ContentChecker
│  │  ├─ llm/
│  │  │  ├─ client.py    LlmClient (Protocol) + FakeLlmClient for tests
│  │  │  ├─ ollama_client.py
│  │  │  └─ prompts/     prompt templates *.j2
│  │  ├─ rendering/
│  │  │  ├─ html.py      HtmlRenderer
│  │  │  ├─ pdf.py       PdfRenderer
│  │  │  └─ templates/   document.html.j2 + CSS (used by BOTH preview and PDF)
│  │  └─ session/store.py SessionStore, Session
│  ├─ tests/
│  │  ├─ unit/  integration/
│  │  └─ fixtures/       kaos_rimba.yaml (example from PRD §5) and error cases
│  └─ evals/             manual Gemma quality evaluations (Vast.ai)
└─ frontend/             React + Vite + TypeScript (pnpm)
   └─ src/
      ├─ api/            openapi-fetch client + generated types
      ├─ features/       write-data/, review-grouping/, generate/, preview/
      ├─ components/ui/  shadcn/ui components
      └─ lib/
```

Class, method, and field names follow the design-level class diagrams (`design/uml/06-…`, `07-…`). Do not rename without approval; if a new class is needed, explain why in your report.

## 3. Stack and dependencies

**Backend:** Python **3.13**, managed with **uv** (`uv add`, `uv run`; no pip/poetry directly).
- Core: fastapi, uvicorn, pydantic v2, pydantic-settings, ruamel.yaml, jinja2, weasyprint, ollama, python-multipart, python-json-logger.
- Dev: pytest, pytest-asyncio (if needed), httpx, ruff, mypy.

**Frontend:** React 18 + Vite + TypeScript, pnpm. Libraries: CodeMirror 6 + `@codemirror/lang-yaml`, TanStack Query, openapi-typescript + openapi-fetch, Tailwind CSS + shadcn/ui, Vitest + Testing Library, Biome.

**Model runner:** Ollama ≥ 0.31.2, model `gemma4:26b-a4b-it-qat` (PRD §10).

Adding any dependency outside these lists **requires asking first**.

## 4. Domain models and data

- All domain models and DTOs are `pydantic.BaseModel`; enums use `enum.StrEnum`.
- Domain models do **not** depend on FastAPI, Ollama, or Jinja2. Dependency direction: `api → services → domain`, `services → llm (via Protocol)`, `rendering → domain`.
- `Fact.path` uses dot notation of the YAML keys exactly as written (e.g. `product.kaos boxy.bahan`); `Fact.line` is the 1-based line number from ruamel.yaml.
- Never modify the user's YAML (no key normalization, no translation). Values are read as-is.
- `GroupingEntry.unit_kind: UnitKind` — `GENERAL_SECTION`, `PRODUCT`, or `PRODUCT_SIZE` (§9.2).
- `Section.facts: list[Fact]` — the facts of the section's grouping unit. Templates render tables, lists, and `label: value` blocks directly from these facts, so the LLM never copies values.

## 5. API

Endpoints (all under `/api`), matching the per-module sequence diagram:

| Method & path | Purpose | Notes |
|---|---|---|
| `POST /api/analyze` | validate → extract → group → suggest → create session | body `{ "yaml": str }`; 422 if the YAML is invalid |
| `PATCH /api/grouping` | change grouping | body contains `session_id`, `section`, `document_types` |
| `POST /api/documents` | compose + check all documents | body `{ "session_id": str }` |
| `GET /api/documents/{type}/preview` | preview HTML (for the iframe) | `?session_id=` |
| `GET /api/documents/{type}/pdf` | download PDF; `type=all` → zip | `?session_id=` |
| `PUT /api/logo` | upload/replace logo (multipart) | `?session_id=`; validate type & size |
| `DELETE /api/logo` | remove logo | `?session_id=` |

- The router only coordinates; services are injected with `Depends`.
- Errors: YAML validation → 422, body `{"errors": [{"message", "line", "column"}]}`. Session not found/expired → 404. Invalid logo → 422 with `{"errors": [{"message"}]}`.
- Never return stack traces or prompt contents to the client.
- The OpenAPI schema is the frontend contract: every request/response change must be followed by regenerating the frontend types.
- Endpoints and services are plain `def`: the `ollama` client, ruamel.yaml, and WeasyPrint are synchronous (FastAPI runs them in a thread pool).

## 6. Sessions and logo

- `SessionStore` is in-memory with a TTL (default 60 minutes, from `Settings`). No database, no session files on disk. Its instance is created in `factory.py` and injected.
- The logo is stored as a `BrandLogo` inside the `Session` (bytes in memory). Size limit from `Settings.max_logo_bytes`; only PNG, JPEG, and SVG are accepted — check the file content, not just the extension. SVGs are sanitized (remove `<script>`, `on*` attributes, external references) before use.
- The logo is uploaded on the Preview & download screen, applies to all documents, and needs no re-generation.

## 7. Errors and logging (project specifics)

- Project error classes in `errors.py`: `LlmUnavailableError`, `LlmOutputError`, `PdfRenderError`, `SessionNotFoundError`, `InvalidLogoError`, plus a YAML validation error carrying line/column. Endpoints map them to the statuses in §5.
- Log format setting: `BKDG_LOG_FORMAT` (`text` | `json`).
- Do not log full YAML, logo bytes, or full prompts at `INFO`; `DEBUG` is allowed for YAML and prompts only.

## 8. Function-role mapping for this project

Roles are defined in `coding-rules.md` §2.2. Applied to the design classes:

| Class / method | Flow role | Job role |
|---|---|---|
| `ApiRouter.analyze`, `.generate`, … | Entry point | — |
| `DataValidator.validate`, `FactExtractor.extract`, `DocumentGrouper.propose`, `CompletenessAdvisor.suggest`, `DocumentComposer.compose`, `ContentChecker.check`, `HtmlRenderer.render` | Process | — |
| `DocumentComposer._compose_section`, `._build_prompt`, `._fallback_section`; `ContentChecker._verify`, `._cover`; `DocumentGrouper._units`, `._classify` | Sub-process | — |
| `OllamaClient.generate` | — | External accessor (model) |
| `PdfRenderer.render`, `.render_all` | Process | Calls WeasyPrint only through `_write_pdf` (external accessor) |
| `DataValidator.validate_logo` | — | Checker |
| `utils.text.humanize_key`, `format_fact_sentence` | — | Shape converter |

**Protocol exception:** `LlmClient` is a `Protocol` with one production implementation (`OllamaClient`). It is kept because the PRD requires an adapter so the model runner can be replaced.

## 9. Module behavior (PRD §9)

These are product decisions. Implement them exactly; changing them requires Arya's approval.

### 9.1 Data kind (`FactExtractor`)
- A top-level key named `product`, `produk`, or `products` (case-insensitive) holds **product knowledge**. Each direct child key is one product name; everything below it belongs to that product (`Fact.product` = the product name, `data_kind = PRODUCT`).
- Every other top-level key except `brand` is **general brand knowledge** (`data_kind = GENERAL_BRAND`, `Fact.product = None`).
- `brand` is the brand name, not a fact section. Missing or empty `brand` is a validation error.
- A value under the product key that is not a mapping of products (e.g. `product: kaos`) is a validation error with its line and column.

### 9.2 Grouping units and default mapping (`DocumentGrouper`)
Grouping units (one row each on the Review grouping screen, in YAML order):
- each general top-level section, e.g. `retur`, `pengiriman` → `GENERAL_SECTION`;
- each product, e.g. `product.kaos boxy` → `PRODUCT`;
- each **size attribute** of a product (attribute key matches the size keywords below), e.g. `product.kaos boxy.size` → `PRODUCT_SIZE`, as its own row.

Default document types (`_classify`):

| Unit | Default types |
|---|---|
| Product | `PRODUCT_KNOWLEDGE` |
| Product size attribute | `PRODUCT_KNOWLEDGE`, `GUIDE` |
| General section whose name matches a guide keyword | `POLICY`, `GUIDE` |
| Any other general section | `POLICY` |

Keyword matching: lower-case the key, split on `_`, `-`, and spaces; a unit matches when **any token** is in the list. The lists are constants in `services/grouper.py`.
- Guide keywords: `cara`, `langkah`, `panduan`, `petunjuk`, `tutorial`, `perawatan`, `rawat`, `pemesanan`, `pesan`, `ukuran`, `size`, `sizing`, `howto`, `guide`.
- Size keywords: `ukuran`, `size`, `sizing` (so `size_chart` matches through its `size` token).

A unit with no document type selected by the user is allowed; its facts are reported as not covered by any document, not as an error. The UI marks such a row "not in any document".

### 9.3 Document content (`DocumentComposer` + templates)
- Titles: `Kebijakan {brand}`, `Panduan {brand}`, `Product Knowledge {brand}`.
- Structure comes from the template, never from the LLM, in YAML order:
  - Policy and Guide: one `h2` per grouping unit, heading = `humanize_key(key)` (`ongkir_retur` → `Ongkir retur`: underscores to spaces, first letter upper-case, the rest unchanged).
  - A `PRODUCT_SIZE` unit in Policy or Guide: heading `{humanized key} · {product name}`, e.g. `Size · kaos boxy`.
  - Product Knowledge: one `h2` per product (product name as written), one `h3` per attribute (humanized key).
- Values are rendered by the template from `Section.facts`, not by the LLM:
  - a list of scalars → bullet list, captioned with the humanized key;
  - a mapping of mappings that share the same keys (e.g. `size: {S: {...}, M: {...}}`) → table; first column = the outer key, other columns = the inner keys humanized;
  - a mapping of scalars → definition list (`label: value`), captioned with the humanized key;
  - a scalar → `label: value`.
- The LLM writes only **one to three short explanatory paragraphs per section** (`origin = LLM`), placed before the template blocks, in Indonesian, formal-friendly, addressing the reader as "Anda". It must not add steps, conditions, numbers, names, or promises that are not in the facts, and must not repeat the whole table in prose.
- Prompt template (`llm/prompts/section.j2`) must contain: the brand name, the document type and its purpose, the section heading, the facts as `path = value` lines, the rules above, and the instruction to return `ComposedSection` JSON with `source_paths` for every paragraph (paths copied exactly from the given list).
- `OllamaClient` passes the JSON Schema of `ComposedSection` in the `format` parameter and validates the result with Pydantic; invalid output raises `LlmOutputError`. `DocumentComposer` retries up to `max_retries`, then falls back.
- Fallback (`_fallback_section`, `origin = TEMPLATE`): one sentence per fact from `format_fact_sentence` — `"{Label}: {value}."`, label = humanized last key, lists joined with `, `. Used when `use_llm = false`, after retries fail, or when the checker rejects a paragraph.
- Model, host, temperature, and `num_ctx` come only from `Settings`. Prompts live in `llm/prompts/*.j2`, not as long strings in code.
- **No-model mode** (`BKDG_USE_LLM=false`): the whole application must still run using the fallback. Used for local development and tests.

### 9.4 Content check (`ContentChecker`)
A paragraph with `origin = LLM` is **rejected** when any of these holds:
1. `source_paths` is empty, or contains a path that is not a fact in the section being composed.
2. It contains a number not present in the values of its source facts. Normalize before comparing: strip thousand separators (`300.000`, `300,000` → `300000`), expand `ribu`/`rb`/`k` (×1 000) and `juta`/`jt` (×1 000 000), and treat ranges (`2-3`, `2–3`, `2 sampai 3`) as their individual numbers. The digits of the document date and of numbered-list markers are ignored.
3. It contains a proper term not present (case-insensitive) in its source facts' values or keys, the brand name, or the document title. A proper term is a word that starts upper-case and is not the first word of a sentence, or a token containing `&` or mixing letters and digits (`J&T`, `24s`). An allow-list constant covers common words (`Anda`, `Rp`, document type names).

Rejected paragraphs are replaced by fallback sentences for their source facts and listed in `CheckResult.replaced_paragraphs` — never silently dropped. Then a **coverage pass** runs: every fact mapped to the document that is not cited by any paragraph and not shown in a template block gets a fallback sentence appended to its section. `coverage_percent` is computed before this pass (it measures the LLM), over the facts mapped to that document; `uncovered_facts` lists the facts that needed the pass.

### 9.5 Rendering and PDF
- One Jinja2 template for both preview and PDF; `humanize_key` and `format_fact_sentence` are registered as template filters.
- **Source references** are rendered only in the preview (template flag), **never** in the PDF. In the preview, every LLM paragraph shows its `source_paths`, and every template block (table, list, `label: value`) shows the path of the fact it renders with its line, `path · L{line}`; a table shows the line range, e.g. `product.kaos boxy.size · L12–14`.
- Completeness suggestions **never** appear in documents.
- RAG-friendly PDF (PRD F8): real text, heading hierarchy `h1`→`h2`→`h3` without skipping levels, one topic per section, tables as text `<table>`, PDF metadata (title, author = brand name, subject = document type, date).
- The logo (if any) appears in the header of every page; without a logo the layout stays clean.
- Jinja2 autoescape is always on. User data is never rendered as raw HTML.

## 10. Frontend

- Screens follow `design/ui-ux/`: 3-step stepper (Write data → Review grouping → Preview & download), format-error state, generating state, logo card on the preview page. Use `design/ui-ux/tokens.md` for the Tailwind theme and `design/ui-ux/html/` for exact layout and markup.
- Server data via **TanStack Query** only (no other global state unless truly needed). API calls go through the `openapi-fetch` client with types generated by `openapi-typescript`.
- YAML editor: CodeMirror 6 + `@codemirror/lang-yaml`; 422 errors are marked at the line/column returned by the backend.
- Preview: an `<iframe>` pointing at the preview endpoint with `sandbox` (no `allow-scripts`).
- Accessibility: text contrast at least 4.5:1, touch targets ≥ 44px.
- UI copy is in English (as designed); strings live directly in components (no i18n yet).
- The Vite dev server proxies `/api` to the backend; no hard-coded backend URL.

## 11. Configuration, testing, and workflow

### Configuration
- All configuration comes from env vars read by `Settings` (prefix `BKDG_`), with an example in `backend/.env.example`.

### Testing
- Backend: `pytest`. Every service has unit tests; every endpoint has an integration test via `httpx`/`TestClient`.
- Tests must **not** call a real Ollama. Use `FakeLlmClient` (returns a `ComposedSection` defined by the test) or `use_llm=False`.
- Required fixtures: the Kaos Rimba example (PRD §5), YAML without `brand`, syntactically broken YAML, one fact mapped to two document types, valid PNG/SVG logos and a fake file.
- Required tests for product rules: no fabricated fact reaches a document, source references never appear in the PDF, completeness suggestions never appear in documents.
- Frontend: Vitest + Testing Library for important logic and components (forms, stepper, error markers).
- Gemma output-quality evaluations on Vast.ai are **separate** from unit tests (`backend/evals/`, run manually).

### Git
- One branch per task: `feat/…`, `fix/…`, `chore/…`, `docs/…`.
- Small commits using Conventional Commits: `feat(composer): add fallback section`.
- Never commit `.env`, session files, generated PDFs, `node_modules`, `.venv`, or `frontend/dist`.
- No force-pushes to `main`. Do not rewrite history that has been pushed.

### Prohibited
- Adding a database, queue, external cache, authentication, or cloud service.
- Calling paid model APIs or sending user data to external services. Models run only through local Ollama.
- Writing the user's YAML or logo to disk.
- Disabling lint/type-check rules or skipping tests to make things "pass".
- Changing the PRD, diagrams, this document, or `coding-rules.md` unless asked.

## 12. Definition of done

A task is done only when all of the following pass and are reported:

- [ ] `uv run ruff format --check && uv run ruff check && uv run mypy src` (backend)
- [ ] `uv run pytest` (backend)
- [ ] `pnpm biome check && pnpm tsc --noEmit && pnpm vitest run` (frontend, if touched)
- [ ] The style checklist in `coding-rules.md` §4 holds
- [ ] Frontend API types regenerated if the contract changed
- [ ] The app runs with `BKDG_USE_LLM=false`
- [ ] A short report: what changed, files touched, how to test, what was not done
