# Contributing

Thanks for helping improve **smartsheet-mcp**.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Checks

- **Lint / format:** `ruff check src && ruff format --check src`  
  Auto-fix: `ruff check --fix src` and `ruff format src`
- **Smoke test:** `python -c "from smartsheet_mcp.server import mcp; print(mcp.name)"`

CI runs the same on pull requests to `main`.

## Pull requests

- Keep changes focused on one concern.
- Do not commit tokens, `.env`, or secrets. Use `.env.example` only for public variable names.

## Security

Report sensitive issues (e.g. token leaks in code) privately to the maintainer rather than in a public issue.
