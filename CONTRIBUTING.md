# Contributing to ForgeMCP

ForgeMCP is an actively developed local integration. Keep changes original and
within documented native operation profiles. Do not add arbitrary Python, shell,
console or eval execution tools. Preserve explicit sessions, authentication,
preview/apply authorization, stale checks, source protection and rollback reports.

Use Python 3.11+ and install development dependencies with:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]' -c requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check server tests
```

Native checks require separately installed Unreal Engine or Blender. Run them only
in disposable projects/profiles; preserve open application work. Distinguish unit,
MCP subprocess, native background and visible interactive evidence in contributions.
Never commit credentials, local registrations, Unreal build outputs or API indexes.

Document new limits, unsupported requests and recovery outcomes. Report failures
with reproducible steps and redacted logs. Do not post session tokens or private
project files in issues. Component license notices must remain intact.
