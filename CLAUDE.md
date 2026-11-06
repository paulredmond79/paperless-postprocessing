# CLAUDE.md

@AGENTS.md

`AGENTS.md` above holds the shared instructions for every agent. Put
project rules there, and keep only Claude Code-specific notes in this file.

## Claude Code notes

- On Windows, the repo's virtualenv is `.venv`. In Git Bash, activate it with
  `source .venv/Scripts/activate`, or call `.venv/Scripts/python -m pytest`
  directly.
- Permission rules block reading and writing `.env*` files, including any
  example file. Don't work around them; ask the user to edit `.env`.
- Don't run scripts in `src/` to "try" a change, because they act on the
  user's live Paperless library (see "Safety" in AGENTS.md). Use the tests,
  or a short script that drives the package with `FakePaperless` and
  `FakeAI`. When the user does ask for a live run, record the document's
  title and fields before and after, without printing its OCR text.
- There's no Paperless API spec in the repo, because `.gitignore` excludes
  the downloaded YAML. For API questions, use the Paperless-ngx docs.
