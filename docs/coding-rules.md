# Coding Rules

**Version:** 0.2 · **Date:** 2026-10-12 · **Owner:** Arya · **Applies to:** anyone (human or AI model) writing code in this repository

This document contains **only code-writing style**: how code is formatted, named, ordered, and structured. It says nothing about what this project builds.
Project design — repository layout, stack, models, API, module behavior, testing requirements, workflow — lives in [`technical-design.md`](technical-design.md).

---

## 1. Principles

1. **As simple as still sufficient.** Add complexity only for a reason that exists now, not for one that might come later.
2. **Build only what is used.** Empty folders and empty layers confuse more than they help.
3. **Code is read more often than written.** Names and writing order must show each function's role and reach.

## 2. Python

### 2.1 Formatting and type checking
- `ruff format` + `ruff check` (rules: `E,F,I,B,UP,SIM,RUF`), line length 100.
- `mypy --strict` passes for application code. Checks in tests may be relaxed.
- Language: code, identifiers, docstrings, comments, and log messages in **English**.

### 2.2 Function roles

Every function has one **flow role** and one **job role**. The reader must be able to tell both from the name and position alone.

**Flow roles**

| Role | Job | Name | Where |
|---|---|---|---|
| Entry point | Receives the call from the framework or terminal and hands it to a process. Contains no logic | The action name, or `main` | API routers, scripts, CLI commands |
| Process | Chains steps. Its body reads like a list of steps | Verb, no leading `_` | Public methods of service classes |
| Sub-process | One step of a process in the same class or file | `_verb` | Above the process that calls it (§2.3) |

**Job roles**

| Role | Job | Name prefix |
|---|---|---|
| Builder | Creates a ready-to-use object with its dependencies | `build_`, `create_` |
| External accessor | Touches files, a database, the network, or a model | `load_`, `save_`, `fetch_`, `delete_`, or the service's own verb (`search`, `generate`, `embed`) |
| Shape converter | Turns data into another shape with no side effects | `parse_`, `to_`, `from_`, `format_` |
| Checker | Answers yes/no, or raises when invalid | `is_`, `has_`, `can_` / `validate_` |
| Helper | Small, stateless, general-purpose work | A verb that describes the work |

Rules:
- **Calls always go down:** entry point → process → sub-process → job role. External accessors, shape converters, checkers, and helpers never call a process.
- **The outside world is reached only through external accessors.** No query, API call, model call, or file access written directly inside a process.
- **One function, one role.** A name containing "and" (`load_and_parse`) means it must be split.

### 2.3 Naming scope and order inside a class

**Scope:**

| Called by | Name |
|---|---|
| Only the same class or file | `_name` — sub-process or internal part |
| Another class or file | `name` |

- Decide who the caller is before naming. When the caller changes, rename everywhere.
- Never use `__name` (double leading underscore), and never invent `__name__` names.
- Never call another class's `_method`.
- Everything else follows PEP 8: modules, functions, and variables `snake_case`; classes `PascalCase`; constants `UPPER_SNAKE`.

**Order inside a class:**
1. `__init__` first.
2. Sub-processes, in the order they are called. A deeper sub-process is written above its caller.
3. The public method that chains them, below its sub-processes.

A class with several public processes: each process forms one group (its sub-processes, then the process). A sub-process shared by several processes lives in the group of its first user. Module-level functions follow the same pattern.

**Sub-process limits:**
- At most two levels deep (`answer` → `_retrieve` → `_is_relevant`).
- Do not create a sub-process that only forwards a call to another class. The process calls the other class's public method directly.

### 2.4 Class or function

| Role | Form |
|---|---|
| Process, external accessor | Class — holds dependencies and settings |
| Helper, checker, shape converter used across files | Function in `utils/` |
| Shape converter tied to its data shape | Method on the Pydantic class (`from_`, `to_`) |
| Builder | Function in `factory.py` |
| Entry point | Function, as the framework expects |

Outside the table: use a class when there is stored state, several methods share the same settings, or more than one implementation is swapped. Otherwise use a plain function.

A `Protocol` (or interface module) is created only when two implementations are used interchangeably in application code. A fake class in tests does not count as a second implementation. Exceptions are recorded in `technical-design.md` with their reason.

### 2.5 Type hints
- Required for every parameter and return value in application code, including `-> None`.
- Modern syntax: `list[str]`, `dict[str, int]`, `X | None`. Import from `typing` only what has no built-in equivalent: `Protocol`, `Callable`, `TypeVar`, `Any`.
- `Any` only with a written reason in the docstring. Prefer a Pydantic class for data whose shape is known.
- List or dict default values use `None`, never `[]` or `{}`.

### 2.6 Docstrings and comments
- Short docstrings (one to three lines) for public classes and functions whose behavior is not obvious from the name.
- Comments explain **why**, not what — except the mandatory comments below.
- **Mandatory comment** directly above every pattern that cannot be read at a glance, stating its intent or an example of its result:
  - regular expressions;
  - logging format strings (`%(asctime)s ...`);
  - date and time formats (`%Y-%m-%d`).

  ```python
  # Matches numbers such as "300000", "2-3", "24s" → captures the digits only
  NUMBER_PATTERN = re.compile(r"\d+")
  ```
- Forbidden in docstrings and comments: AI reasoning, opening sentences ("This function will…"), closing sentences, and filler.

### 2.7 Errors
- Risky code — files, network, models, rendering libraries, heavy computation — is wrapped in `try`/`except` **inside the external accessor** and converted into a project error class defined in `errors.py`.
- Catch specific exceptions. `except Exception` is allowed only at the outermost entry point, and must be logged.
- No bare `except:`. Never swallow errors silently.
- Log with `exc_info=True`, then re-raise with `raise ProjectError(...) from e`.
- Entry points only translate project errors into responses (e.g. HTTP statuses), with no other logic.

### 2.8 Logging
- No `print()` for diagnostics; use `logging`. `print()` is only for output meant for the user (CLI results).
- One helper `setup_logger(name)` in `utils/logger.py`. Every module calls `logger = setup_logger(__name__)`.
- Format is chosen by a `LOG_FORMAT` setting: `text` for development, `json` for production (`python-json-logger`). Default level `INFO`.
- Never log secrets or personal data, at any level.

### 2.9 Configuration
- One `Settings` class (`pydantic-settings`) reads the environment; other code takes values from the settings object, never from `os.getenv`.
- No keys, passwords, hosts, or URLs written in code.
- Every new setting is added to `.env.example` with an empty or safe example value.

### 2.10 `async def`
Use `async def` only when the whole call chain uses async clients. If a client in the chain is synchronous, use plain `def`.

### 2.11 Avoid
- `from module import *`
- List or dict default arguments
- Bare `except:` or silently swallowed errors
- `print()` for diagnostics
- Secrets in code
- Docstrings or comments containing AI reasoning or filler
- A class with only one static method
- Old-style type hints (`List`, `Optional`, `Union`)
- Function bodies longer than 50 lines — a sign that part of it should become a sub-process
- Comprehensions nested more than two levels
- Mutable global state (create shared objects in `factory.py` and inject them)
- Calling another class's `_method`

## 3. TypeScript / React

- TypeScript with `strict: true`. Lint and format with **Biome** only (no ESLint/Prettier).
- Function components and hooks; no class components.
- One component per file, file name `PascalCase.tsx`; hooks in `useXxx.ts`; other modules `camelCase.ts`.
- Never hand-write types that can be generated from a schema; never edit generated files.
- Interactive elements use native `<button>`, `<a href>`, `<input>` with a `<label>`; icon-only buttons have `aria-label`.

## 4. Style checklist

- [ ] Formatter, linter, and type checker pass
- [ ] Names match scope and role; order inside classes is correct (§2.2–2.3)
- [ ] The outside world is reached only through external accessors
- [ ] Errors caught specifically and converted to project errors (§2.7)
- [ ] Diagnostics use `logging`, not `print()` (§2.8)
- [ ] Type hints complete; public docstrings present without filler (§2.5–2.6)
- [ ] Regexes and format strings have comments (§2.6)
- [ ] Nothing from the "Avoid" list (§2.11)
- [ ] `.env.example` updated when a setting is added (§2.9)
