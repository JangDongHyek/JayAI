# JayAI

JayAI is split into two parts:

- central server
  stores projects, devices, workspace bindings, conversations, messages, and runs
- local app
  opens the UI, reads local files, runs `Codex CLI` and `Claude Code CLI`, then syncs results back to the server

This matches the intended flow:

1. install and log in to CLIs on each local machine
2. keep project/session data on the central server
3. bind a local folder on each machine and continue work from shared sessions

## Current architecture

### Central server

- no local file access
- no Codex or Claude execution
- data/API only

Main files:

- `src/jayai/main.py`
- `src/jayai/routers/projects.py`
- `src/jayai/routers/devices.py`
- `src/jayai/templates/server.html`

### Local app

- local browser UI
- local workspace scan
- local git actions
- local Codex/Claude execution
- syncs runs and messages to the central server

Main files:

- `src/jayai/local_main.py`
- `src/jayai/routers/local.py`
- `src/jayai/services/orchestrator.py`
- `src/jayai/services/server_api.py`
- `src/jayai/services/local_config.py`
- `src/jayai/templates/index.html`
- `start-jayai-local.bat`

## Central server run

```powershell
cd C:\Users\fove1\OneDrive\문서\codex\life\jayai
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m uvicorn jayai.main:app --host 0.0.0.0 --port 8000
```

Health:

- `http://<server-host>:8000/api/health`

If you want a path behind nginx:

```powershell
$env:JAYAI_BASE_PATH="/jayai-api"
.\.venv\Scripts\python.exe -m uvicorn jayai.main:app --host 0.0.0.0 --port 8000
```

## Local app run

CLI:

```powershell
cd C:\Users\fove1\OneDrive\문서\codex\life\jayai
.\.venv\Scripts\python.exe -m jayai.cli local-ui --open-browser
```

Double-click launcher:

- `start-jayai-local.bat`

Optional first run with server URL:

```powershell
.\.venv\Scripts\python.exe -m jayai.cli local-ui --server-url http://43.203.252.40:8000 --open-browser
```

After that, the local app stores the server URL in:

- `data/local-config.json`

## Local workflow

1. open local UI
2. set central server URL once
3. check local CLI status
4. pick or create a project
5. bind the local workspace path
6. open or create a conversation
7. run prompts locally

Examples:

- `Read README and summarize the core structure in 5 lines`
- `Show git status`
- `Clone the repo and pull latest changes`

## Project config files

JayAI checks these files in the workspace root:

- `.jayai.json`
- `jayai.json`
- `.orchestrator.json`
- `orchestrator.json`

Default behavior:

- Codex reads heavy context first
- Claude reviews Codex output

## Data paths

Central server DB default:

- `data/jayai.db`

Local run artifacts:

- `data/runs/<timestamp>/`

Artifacts include:

- `codex.txt`
- `claude.txt`
- `summary.txt`
- `meta.json`

## Postgres switch

Default DB is SQLite.

For Postgres:

```powershell
$env:JAYAI_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/jayai"
.\.venv\Scripts\python.exe -m uvicorn jayai.main:app --host 0.0.0.0 --port 8000
```

Note:

- `psycopg` is not installed yet
- add it during server deployment if needed

## CLI commands

```powershell
jayai serve --host 0.0.0.0 --port 8000
jayai local-ui --open-browser
jayai probe
jayai scan-workspace C:\path\to\repo
```

## Current limits

- local app is still browser-based, not a packaged desktop app
- no streaming token view yet
- no background local runner service yet
- no natural language `commit / push / PR` yet
