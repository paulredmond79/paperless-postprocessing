# AGENT Instructions for paperless-postprocessing

These instructions apply to the whole repository and to every AI coding agent
(Claude Code, Codex, Copilot and others). `CLAUDE.md` imports this file, so
keep shared guidance here.

## What this project is

Python scripts that use OpenAI to tidy up documents in a live
[Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) instance,
talking to it only through its REST API.

Paperless runs `src/post.py <DOCUMENT_ID>` as its post-consume hook, from
`post.sh` on the server (outside this repo). For each new document it runs
two steps in order:

1. **correspondent**: always runs. It chooses the correspondent, creates it if
   new, assigns it, and tags the document `gpt-correspondent`, or
   `gpt-correspondent-unable-to-determine` if none can be found.
2. **metadata**: generates a title and fills the custom fields.

A failing step is logged and the other still runs.

| Script (`src/`) | Invocation | What it does |
| --- | --- | --- |
| `post.py` | `[<document_id>] [--only correspondent\|metadata]` | The hook. Runs both steps on one document. The ID defaults to `$DOCUMENT_ID`. |
| `postprocess_all.py` | `[--with-metadata] [--limit N]` | Runs the correspondent step (and optionally metadata) on every document not tagged `gpt-correspondent`. |
| `cleanup_correspondents.py` | `[--apply]` | Renames correspondents whose name is a leaked JSON reply. Only reports without `--apply`. |
| `merge_duplicates.py` | `[--apply]` | Merges correspondents whose names differ only by case or spacing, then **deletes** the duplicates. Only reports without `--apply`. |

The scripts are thin command-line wrappers. All logic lives in the
`src/postprocessing/` package:

| Module | Responsibility |
| --- | --- |
| `config.py` | `load_env()` for `.env`, `configure_logging()`, and `Settings.from_env()`, which raises `ConfigError` naming every missing setting. |
| `paperless.py` | `PaperlessClient`: every Paperless call. It follows pagination, uses timeouts and retries, and raises `PaperlessError` with Paperless's message. Also `tag_ids()`. |
| `ai.py` | `AIClient.ask_json()`: the only place that calls OpenAI. It returns a dict or raises `AIError`, and takes an optional strict JSON `schema`. Also `chat_completion_options()`. |
| `correspondent.py` | The correspondent step: prompt, `REPLY_SCHEMA`, reply parsing, tag names. |
| `metadata.py` | The metadata step: prompt, `reply_schema()` built from the custom fields, type conversion (`clean_fields`), 128-character limits. |
| `pipeline.py` | `process_document()`: fetches the document once and runs the steps in `STEPS`. |
| `cli.py` | `run(main)` for start-up and exit codes (0 ok, 1 failed, 2 config), and `build_clients()`. |

Two scripts were removed on purpose: the Irish tax relief checker
(`ocr_tax_relief_checker.py`) and the RAG ingestion script
(`ingest_document.py`). Don't bring either back unless the user asks.

## Safety: these scripts change real data

- Never run a script against the real Paperless instance unless the user
  asks you to. `post.py` and `postprocess_all.py` change documents and
  create correspondents and tags, and every document they process is a paid
  OpenAI call. `merge_duplicates.py --apply` deletes correspondents.
- Keep the maintenance scripts reporting only by default. Anything
  destructive needs an explicit `--apply`.
- Verify changes with the test suite. It uses in-memory fakes and must never
  make network calls.
- Don't commit `.env` files, API tokens or document content (OCR text holds
  personal and financial data).
- Never log document content at any level. That covers OCR text, prompts
  (they contain it), full document records (their `content` field is the OCR
  text) and model replies (they hold extracted values). Log IDs, counts,
  field names and lengths instead.
  `tests/test_pipeline.py::test_document_text_is_never_logged` checks this;
  extend it when you log near document data.

## Environment

- Settings: `PAPERLESS_URL` (default `http://localhost:8000`),
  `PAPERLESS_API_TOKEN` (required), `OPENAI_API_KEY` (required by the
  OpenAI scripts), `OPENAI_MODEL` (default `gpt-6-luna`),
  `OPENAI_REASONING_EFFORT` (default `none`) and `LOG_LEVEL` (default
  `INFO`).
- They come from the environment and from a gitignored `.env` in the repo
  root. Environment variables win over the file. `cli.run()` loads `.env`
  and sets up logging, so a new script only needs
  `sys.exit(run(main))`. Read settings through `Settings.from_env()`, never
  with `os.getenv` in a step.
- Never read, print or commit `.env`, because it holds real tokens. If a
  task needs a setting, ask the user. `tests/conftest.py` sets
  `PAPERLESS_POSTPROCESSING_NO_DOTENV=1`, so tests never load it.
- Send every OpenAI call through `AIClient`. Don't hardcode a model name: a
  hardcoded `gpt-4` broke every call when OpenAI retired it. `temperature`
  is only sent when reasoning effort is `none`, because OpenAI rejects
  sampling parameters otherwise. `gpt-6-astra` and `gpt-6.1-sol` don't
  accept `none`.
- Python 3.9+ syntax (the Paperless container's Python). The local `.venv`
  runs Python 3.14. Dependencies are `openai`, `requests` and
  `python-dotenv`.

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

- `pytest.ini` puts `src` on `sys.path`. Tests import the package
  (`from postprocessing.metadata import ...`) and scripts (`import post`)
  directly, and import the fakes with `from conftest import ...`.
- Config: `.flake8` sets `max-line-length = 120` and `.isort.cfg` uses the
  black profile. Black uses its defaults (88 columns).
- On Windows, set `PYTHONUTF8=1` before running isort. Without it, isort fails
  to read files with non-ASCII characters (such as the `…` in
  `metadata.py`) and still exits 0. Likewise, pass `encoding="utf-8"` when a
  script reads or writes repo files.
- Run all four checks before committing.

## Coding conventions

- Use 4-space indents and give every public function a docstring.
- Keep the layers apart. Scripts parse arguments and call the package.
  Steps take `(paperless, ai, document)` and raise `PaperlessError` or
  `AIError`. Only `paperless.py` uses `requests`, and only `ai.py` uses
  `openai`.
- No work at import time: no API clients, environment reads or logging
  set-up at module level.
- To add a step, write `def my_step(paperless, ai, document)` in its own
  module and register it in `pipeline.STEPS`. `post.py --only` picks it up.
- Test with `FakePaperless` and `FakeAI` from `tests/conftest.py`, and with
  `FakeSession` in `tests/test_paperless.py` for the HTTP layer. Add a test
  with every behaviour change.

## Gotchas

- Paperless rejects text over 128 characters (titles and string custom
  fields), and one bad value rejects the whole PATCH. `metadata.clean_fields`
  converts and truncates every value. Keep it that way for new field types.
- A PATCH with `custom_fields` replaces the document's entire list.
  `metadata.build_update` merges in the existing values first.
- Paperless returns document `tags` as ints or `{"id": ...}` dicts. Use
  `paperless.tag_ids()`.
- Your Paperless may contain duplicate custom fields left by the old tax
  checker, such as `Confidence Score` and `confidence_score`.
  `field_definitions` keeps the oldest (lowest ID) and logs a warning.
- Prompts: fixed instructions go in each step's `SYSTEM_MESSAGE`, and the
  user message holds only the varying data (the correspondent list and the
  OCR text inside `<<<` `>>>`). Both steps pass a strict JSON schema, so
  OpenAI enforces the reply's shape. Strict mode needs every property
  listed in `required` and `additionalProperties: false`, so optional
  values are nullable rather than left out. `clean_fields` skips nulls.
  Changing a prompt changes results on real documents. Say in the PR
  that it was only checked with the fakes, unless the user ran it live.
- `.gitignore` ignores `*.yaml`, so a YAML file you add won't be tracked
  unless you force-add it or change the rule.

## Commits and pull requests

- Commit messages: a short imperative summary under 50 characters, then a
  body wrapped at 72 columns if needed. Reference issues or PRs where
  relevant.
- Work on a branch and open a PR against `main`.
- In the PR description, summarize the changes, name the files touched, and
  state the test and lint results (and anything you didn't verify, such as a
  live API run).
- Update `README.md` and this file when you add a script, a step, a setting
  or a workflow.
