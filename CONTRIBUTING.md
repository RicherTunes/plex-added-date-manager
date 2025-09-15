# Contributing

Thanks for taking the time to contribute!

## Development Setup
- Python 3.11 or 3.12
- pip install -r requirements.txt
- Optional: pip install -r requirements-dev.txt (if present)
- Run the UI: streamlit run src/app.py
- Run tests: pytest -q

## Style & Lint
- CI runs uff and lack --check.
- Suggested local commands:
  - uff check .
  - lack .

## Commit Guidelines
- Use concise, descriptive messages.
- Prefix with type when possible: eat:, ix:, docs:, efactor:, chore:, ci:.

## PRs
- Include a short summary, screenshots (if UI), and a test plan.
- Allow CI to run and keep diffs focused.

## Secrets
- Do not commit tokens or .env files.
- Use example.env for placeholders.
