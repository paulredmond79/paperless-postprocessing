# AGENT Instructions for paperless-postprocessing

These instructions apply to the whole repository and to every AI coding agent
(Claude Code, Codex, Copilot and others). `CLAUDE.md` imports this file, so
keep shared guidance here.

## What this project is

These are standalone Python scripts that run against a live
[Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) instance,
mostly as post-consume hooks. They use OpenAI to fill in document metadata,
and the scripts talk to Paperless only through its REST API. There's no
package, no CLI framework and no shared config object. Each script reads
environment variables at import time and runs on its own.

| Script (`src/`) | Invocation | What it does |
| --- | --- | --- |
| `postprocess.py` | `<document_id>` | Uses OpenAI to choose or create the correspondent, then adds the `gpt-correspondent` tag (or `gpt-correspondent-unable-to-determine`). |
| `post.py` | `<document_id>` | Uses OpenAI to generate a title and fill the existing custom fields. |
| `ocr_tax_relief_checker.py` | `<document_id>` | Checks for Irish tax relief, writes custom fields and a note, and tags `tax-check-failed` on error. |
| `ingest_document.py` | `<document_id> [--force-refresh] [-v]` | POSTs the document to the separate RAG service (`paperless-rag.json` is its OpenAPI spec). |
| `postprocess_all.py` | none | Runs `postprocess.main` on every document that lacks `gpt-correspondent`. |
| `cleanup_correspondents.py` | none | Renames correspondents whose name is a leaked JSON blob. |
| `merge_duplicates.py` | none | Merges correspondents whose names differ only by case, then **deletes** the duplicates. |

Shared Paperless API calls live in `src/utils/api_helpers.py`. Prompts,
schemas and field mappings for the tax checker are the JSON files in `src/`
(`tax_relief_prompts.json`, `tax_relief_schema.json`, `field_mapping.json`).
Change those files rather than hardcoding prompt text in Python.

## Safety: these scripts change real data

- Never run a script in `src/` against a real Paperless instance unless the
  user asks you to. Each one PATCHes documents, creates tags and
  correspondents, and posts notes. `merge_duplicates.py` deletes
  correspondents, and `postprocess_all.py` touches every document and makes
  one paid OpenAI call per document.
- Verify changes with the test suite, where every HTTP and OpenAI call is
  mocked. Tests must never make network calls.
- Don't commit `.env` files, API tokens or document content (OCR text can
  contain personal and financial data).

## Environment

- Variables: `PAPERLESS_URL` (default `http://localhost:8000`),
  `PAPERLESS_API_TOKEN`, `OPENAI_API_KEY` and `OPENAI_MODEL` (optional,
  default `gpt-4.1`). `ingest_document.py` uses `RAG_API_URL` and
  `RAG_API_KEY` instead.
- Nothing loads a `.env` file (`python-dotenv` isn't a dependency). Export the
  variables in the shell or in the Paperless container's environment.
- Read the model name from `OPENAI_MODEL`. Don't hardcode one: a hardcoded
  `gpt-4` broke every OpenAI call when OpenAI retired it. `post.py` and
  `postprocess.py` send `temperature=0.2`, which reasoning models reject.
- The scripts use Python 3.9+ syntax. The local `.venv` runs Python 3.14.

## Setup, tests and linting

Run these from the repository root:

```bash
pip install -r requirements.txt
pip install pytest black flake8 isort   # dev tools aren't in requirements.txt
pytest
black --check src tests
flake8 src tests
isort --check-only src tests
```

- `pytest.ini` puts `src` on `sys.path`, so tests import modules directly
  (`import postprocess`, `from utils.api_helpers import ...`).
- Config: `.flake8` sets `max-line-length = 120` and `.isort.cfg` uses the
  black profile. Black uses its defaults (88 columns).
- On Windows, set `PYTHONUTF8=1` before running isort. Without it, isort fails
  to read `ingest_document.py` (which logs emoji) and still exits 0.
- Run all four checks before committing. Every one passes on `main`.

## Coding conventions

- Use 4-space indents and give every public function a docstring.
- Keep the import layout the tests rely on: `from utils.api_helpers import ...`,
  not `src.utils...`.
- Module-level globals (`paperless_url`, `headers`, `client`) are created at
  import time. Tests monkeypatch them directly, so keep them module-level
  unless you also update the tests.
- Mock network calls with `monkeypatch.setattr(<module>.requests, "get", ...)`
  or `unittest.mock.patch`, following the existing tests. Add a test with
  every behaviour change.

## Gotchas

- Paperless list endpoints are paginated. Use
  `api_helpers.fetch_all_results(url, headers)` (it follows `next`) rather
  than reading `results` from a single response, or a tag past page one will
  look missing.
- In tests, a `MagicMock` response without a real `json()` return value has
  a truthy `next`. Give every mocked list response a real dict.
- `api_helpers.fetch_or_create_tag` returns a tag **ID** (int), while
  `postprocess.fetch_tags` and `postprocess.create_tag` return tag **dicts**.
  Check which one you have before indexing `["id"]`.
- `postprocess.py` and `api_helpers.py` each have their own
  `fetch_tags`, `create_tag` and `add_tag_to_document`, with different
  signatures and return types. `postprocess_all.py` imports the
  `postprocess.py` versions.
- Several scripts call `sys.exit` on error, and exit code 0 means "skipped"
  (for example, no OCR text). `postprocess_all.py` catches `SystemExit` and
  exceptions for each document, carries on, and exits 1 at the end if any
  document failed.
- In `ocr_tax_relief_checker.py`, `analyze_document_with_openai` records its
  own failures (tag plus note). Callers must not call `record_failure`
  again, or the document gets duplicate notes.
- `.gitignore` ignores `*.yaml`, so a YAML file you add won't be tracked
  unless you force-add it or change the rule.
- Paperless returns document `tags` as ints or as `{"id": ...}` dicts,
  depending on the endpoint. Handle both, as the existing code does.

## Commits and pull requests

- Commit messages: a short imperative summary under 50 characters, then a
  body wrapped at 72 columns if needed. Reference issues or PRs where
  relevant.
- Work on a branch and open a PR against `main`.
- In the PR description, summarize the changes, name the files touched, and
  state the test and lint results (and anything you didn't verify, such as a
  live API run).
- Update `README.md` and this file when you add a script, an environment
  variable or a workflow.
