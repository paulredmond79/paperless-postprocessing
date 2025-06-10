# AGENT Instructions for paperless-postprocessing

These instructions apply to the entire repository. Follow them when modifying
files or creating pull requests.

## Coding style
- Format Python code with **black** using the default configuration.
- Run **flake8** to check style and linting. Install via `pip install flake8` if
  necessary.
- Keep imports sorted (for example with `isort`).
- Use 4 spaces per indentation level and include docstrings for public
  functions.

## Tests
- Install dependencies with `pip install -r requirements.txt`.
- Run all tests with `pytest` from the repository root before committing.

## Commit messages
- Begin with a short imperative summary under 50 characters.
- Include a body if needed, wrapping lines at 72 characters.
- Reference related issues or PRs when applicable.

## Pull requests
- Summarize the key changes and reference relevant files in the description.
- Mention the outcome of running the test suite.

## Environment
- The scripts rely on the following environment variables which can be
  provided via a `.env` file or exported in the shell:
  - `PAPERLESS_URL`
  - `PAPERLESS_API_TOKEN`
  - `OPENAI_API_KEY`
