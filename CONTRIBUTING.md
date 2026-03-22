<!--
  © Clearview Geographic LLC -- All Rights Reserved | Est. 2018
  CVG Rainfall Wizard — CONTRIBUTING
-->

# Contributing to CVG Rainfall Wizard

> **Proprietary / Internal Use** — This is not an open-source project.
> All contributions must be authorized by Clearview Geographic LLC.

---

## Development Setup

```bash
git clone https://github.com/clearview-geographic/cvg-rainfall-wizard.git
cd cvg-rainfall-wizard

python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS / Linux

pip install -e ".[web]"
pip install pytest pytest-cov pytest-mock scipy

rainfall-wizard --help
```

---

## Code Standards

- **Python 3.10+** — `from __future__ import annotations`, full type hints
- **CVG Header**: every `.py` file must carry the full CVG copyright header block
- **Docstrings**: Google-style for all public functions/classes
- **Logging**: `log = logging.getLogger(__name__)` — no bare `print()` in library code
- **Paths**: resolve all paths through `paths.py`

---

## Testing

```bash
# All tests
pytest

# With coverage report
pytest --cov=rainfall_wizard --cov-report=html

# Unit tests only (no network)
pytest -m unit
```

New code must include tests. Mark tests that require network as `@pytest.mark.integration`.

---

## ChangeLog

Each PR must add an entry to `05_ChangeLogs/master_changelog.md`.

---

## Branch Naming

`feature/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/`

---

*© Clearview Geographic LLC — All Rights Reserved*
