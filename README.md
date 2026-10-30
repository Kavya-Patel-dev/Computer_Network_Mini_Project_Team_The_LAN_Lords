# The LAN Lords

This repository combines the AI simulator, web backend, and frontend in one project. The backend remains a separate Python package and virtual environment from the AI code:

```text
Project/
  AI/          Routing simulator, frozen model, baselines, data, and tests
  backend/     FastAPI service, Alembic migrations, tests, and its own .venv
  frontend/    React + TypeScript web application
```

The backend virtual environment is `backend/.venv`; it is not nested under `AI/`. The service imports the frozen model from `AI/` at inference time and does not modify or train it. The pinned model is `AI/runs/day5/final_routing_model.pt`, SHA-256 `45957597f56cf163c5ae5d69f6fe6959ddb638601c7ade97b865a848151fff28`.

Each application folder has its own setup guide: [AI](AI/README.md), [backend](backend/README.md), and [frontend](frontend/README.md). This root README is the combined setup and integration guide.

## Local setup

Run PowerShell commands from this directory. Python 3.12 and Node.js/npm are required. Set up the AI environment separately if you want to run its tests or command-line simulator:

```powershell
py -3.12 -m venv .\AI\venv
& .\AI\venv\Scripts\python.exe -m pip install -r .\AI\requirements.lock.txt
```

```powershell
py -3.12 -m venv .\backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
Copy-Item .\backend\.env.example .\backend\.env
```

If `ensurepip` fails on Windows, recreate only the backend environment without
pip and bootstrap pip into that interpreter with the existing AI environment's
pip. Do not install backend packages into `AI/venv`:

```powershell
py -3.12 -m venv --without-pip .\backend\.venv
& .\AI\venv\Scripts\python.exe -m pip --python .\backend\.venv\Scripts\python.exe install pip
& .\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

For local development, the backend loads `backend/.env`; process environment variables override that file. Do not put secrets in frontend configuration or commit a real `.env` file. In production inject `DATABASE_URL` and `SESSION_SECRET` through the secret manager, set `FRONTEND_ORIGINS` to the exact frontend origin, and use `COOKIE_SECURE=true` behind HTTPS.

Inspect the Neon project and its existing schema before migration. The initial migration only creates missing tables and never drops existing tables:

```powershell
& .\backend\.venv\Scripts\alembic.exe -c .\backend\alembic.ini upgrade head
& .\backend\.venv\Scripts\python.exe -m backend.app.cli create-admin --email admin@example.com --name 'Initial Admin'
```

The admin bootstrap prompts for a password, is allowed only when no administrator exists, and refuses SQLite. Public registration always creates a `user` account.

Start the backend from the project root:

```powershell
& .\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location .\frontend
npm install
npm run dev
```

The API docs are at `http://127.0.0.1:8000/docs` in development. Frontend API URL defaults to `http://localhost:8000/api/v1`; override it with `frontend/.env.local` based on `frontend/.env.example` if needed.

## Checks

```powershell
Set-Location ..
& .\backend\.venv\Scripts\python.exe -m pytest .\backend\tests -q
& .\backend\.venv\Scripts\python.exe -m pip check
Set-Location .\frontend
npm run build
```

`backend/requirements.txt` pins direct dependencies and `backend/requirements.lock` records the tested Windows/Python 3.12 environment. The backend tests use an isolated in-memory SQLite database only for tests; production and migrations require PostgreSQL.

## Integration status

The backend supports registration/login/logout, cookie sessions with CSRF checks, profile updates, plans and review, persistent simulation runs, result access, share links, notifications, admin user management, audit events, and real model inference. The model adapter translates the frontend canvas's node/link/flow fields into the frozen model API schema. The frontend result pages now read saved aggregate metrics; views requiring per-step traces explicitly state that those traces are unavailable.

Database credentials belong only in the local `backend/.env` or the deployment secret manager; that file is excluded from Git. Verify the configured database and migration in your own environment before running the app. Email delivery is not configured, so email invitations and password reset/verification are unavailable. Public demo execution, temporary what-if simulation, immutable topology snapshots/diffs, and per-step heatmap/Q-value histories are not implemented; the UI identifies these limitations instead of showing invented results.

## Repository contents and exclusions

The repository includes source code, tests, setup examples, the frozen routing checkpoint, and the network data already used by the project. It excludes local virtual environments, `node_modules`, `.env` secrets, generated training/evaluation outputs, and submission PPT/report files. See [`.gitignore`](.gitignore). The standalone AI repository history is kept as a local backup and is not nested into this unified repository.
