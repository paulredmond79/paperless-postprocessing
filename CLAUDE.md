# CLAUDE.md

@AGENTS.md

`AGENTS.md` above holds the shared instructions for every agent. Put
project rules there, and keep only Claude Code-specific notes in this file.

## Claude Code notes

- On Windows, the repo's virtualenv is `.venv`. In Git Bash, activate it with
  `source .venv/Scripts/activate`, or call `.venv/Scripts/python -m pytest`
  directly.
- Don't run scripts in `src/` to "try" a change, because they act on the
  user's live Paperless library (see "Safety" in AGENTS.md). Use the tests,
  or a short `python -c` that monkeypatches the HTTP and OpenAI calls.
- For questions about the Paperless API, the OpenAPI spec of the separate
  RAG service is `paperless-rag.json`. There's no Paperless API spec in the
  repo, because `.gitignore` excludes the downloaded YAML.
