# Paperless Post-Processing Scripts

Python scripts that use OpenAI to tidy up documents in [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx). Paperless runs `post.py` as a post-consume hook, so every new document gets:

1. **A correspondent.** The model picks one of your existing correspondents or suggests a new one. The script creates it if needed, assigns it, and tags the document `gpt-correspondent`. If no correspondent can be found, the document is tagged `gpt-correspondent-unable-to-determine` instead.
2. **A title and custom fields.** The model writes a title and fills your custom fields. Each value is converted to its field's type and kept within Paperless's 128-character limit.

If one step fails, the other still runs. There are also scripts to process your existing documents in bulk and to clean up correspondents.

## Project structure

```
paperless-postprocessing
├── src
│   ├── post.py                   # Post-consume hook: processes one document
│   ├── postprocess_all.py        # Processes every document not yet tagged gpt-correspondent
│   ├── cleanup_correspondents.py # Renames correspondents whose name is a JSON reply
│   ├── merge_duplicates.py       # Merges correspondents that differ only by case
│   └── postprocessing            # Shared package used by the scripts
│       ├── config.py             # Settings from .env and the environment; logging
│       ├── paperless.py          # Paperless REST API client
│       ├── ai.py                 # OpenAI wrapper that returns parsed JSON
│       ├── correspondent.py      # Correspondent step
│       ├── metadata.py           # Title and custom fields step
│       ├── pipeline.py           # Runs the steps on one document
│       └── cli.py                # Shared start-up and exit codes
├── tests                         # pytest suite (no network access)
├── AGENTS.md / CLAUDE.md         # Instructions for AI coding agents
└── requirements.txt
```

## Setup

1. **Install dependencies** (Python 3.9 or later):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure settings.** Create a file named `.env` in the repository root (it's gitignored). Every script loads it on start-up. Variables that are already set in the environment, such as a Paperless container's own settings, take precedence over the file.
   ```bash
   PAPERLESS_URL=<your-paperless-url>          # default http://localhost:8000
   PAPERLESS_API_TOKEN=<your-paperless-api-token>
   OPENAI_API_KEY=<your-openai-api-key>
   OPENAI_MODEL=gpt-6-luna         # optional; chat model used for all OpenAI calls
   OPENAI_REASONING_EFFORT=none    # optional; temperature is only sent when this is none
   LOG_LEVEL=INFO                  # optional; DEBUG, INFO, WARNING or ERROR
   ```
   If a required setting is missing, the scripts stop with exit code 2 and name it.

3. **Hook it into Paperless.** Point Paperless's post-consume script at something like this:
   ```bash
   #!/usr/bin/env bash
   echo "Post-processing document ${DOCUMENT_ID} (${DOCUMENT_FILE_NAME})"
   /usr/src/paperless/scripts/paperless-postprocessing/src/post.py "${DOCUMENT_ID}"
   ```

## Usage

All scripts accept `--help`.

### Process one document
Runs both steps. Paperless's `DOCUMENT_ID` is used if you leave out the ID.
```bash
python src/post.py <document_id>
python src/post.py <document_id> --only correspondent   # or --only metadata
```
Exit codes: 0 means every step succeeded, 1 means a step failed, and 2 means a setting is missing.

### Process existing documents
Runs the correspondent step on every document not yet tagged `gpt-correspondent`. Each document is one paid OpenAI call (two with `--with-metadata`), so start with `--limit`.
```bash
python src/postprocess_all.py --limit 10
python src/postprocess_all.py --with-metadata
```

### Clean up correspondents
Both scripts only report what they would change. Add `--apply` to make the changes.
```bash
python src/cleanup_correspondents.py            # names that are leaked JSON replies
python src/merge_duplicates.py                  # names that differ only by case or spacing
python src/merge_duplicates.py --apply          # moves documents, then DELETES the duplicates
```

## Development

```bash
pip install pytest black flake8 isort
pytest
black --check src tests && flake8 src tests && isort --check-only src tests
```

## License

This project is licensed under the MIT License. See the LICENSE file for details.
