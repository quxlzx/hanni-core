# Contributing

Thanks for helping improve H.A.N.N.I.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev,speech]"
python -m pytest -q
```

## Pull requests

- Keep changes focused and well-scoped.
- Update docs when behavior changes.
- Add or update tests for important fixes.
- Follow the project’s local-first and privacy-first operating principles.

## Reporting issues

Please include:

- OS version and Python version
- reproduction steps
- redacted logs or screenshots (remove account names, paths, tokens, and private content)
- expected vs actual behavior

## Security

Please do not open public issues for security vulnerabilities. Use the private security policy in [SECURITY.md](SECURITY.md).
