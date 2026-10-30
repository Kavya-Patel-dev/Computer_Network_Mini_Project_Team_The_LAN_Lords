# LAN Lords backend

The FastAPI service is a separate project-root `backend/` package with its own
`.venv`. It stores application users, plans, reviews, run results, share links,
notifications, and audit events in Neon PostgreSQL. It calls the existing
frozen AI routing API in `AI/models/api.py`; it does not train, rewrite, or
replace the checkpoint.

## Local setup

Run these from the project root in PowerShell:

```powershell
py -3.12 -m venv .\backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
Copy-Item .\backend\.env.example .\backend\.env
```

If Windows `ensurepip` fails while creating the environment, create only the
backend environment without pip and bootstrap pip into that interpreter. This
uses the existing AI environment as a pip installer only; runtime dependencies
remain installed exclusively in `backend/.venv`:

```powershell
py -3.12 -m venv --without-pip .\backend\.venv
& .\AI\venv\Scripts\python.exe -m pip --python .\backend\.venv\Scripts\python.exe install pip
& .\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

For local development, `backend/.env` is loaded automatically. It is ignored by
Git, and variables already set in the process environment take precedence. In
production, inject `DATABASE_URL` and a random `SESSION_SECRET` (at least 32
characters) through the deployment secret manager. Set `COOKIE_SECURE=true`
behind HTTPS and set `FRONTEND_ORIGINS` to the exact deployed frontend origin(s).

Example local variables (replace the database placeholder with the Neon URL;
never commit the real value):

```powershell
$env:APP_ENV = 'development'
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require'
$env:SESSION_SECRET = 'replace-this-with-a-random-secret-at-least-32-chars'
$env:FRONTEND_ORIGINS = 'http://localhost:5173'
```

Check liveness and readiness separately:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
```

`/ready` checks PostgreSQL and the pinned model artifact. A missing DB URL or
checkpoint fails readiness rather than returning substitute data.

## Migrations and first administrator

Inspect the target Neon project and its existing schema before applying the
initial migration. Back up important data first. The migration only creates
missing application tables and its downgrade is intentionally a no-op to avoid
accidental data deletion.

```powershell
& .\backend\.venv\Scripts\alembic.exe -c .\backend\alembic.ini upgrade head
& .\backend\.venv\Scripts\python.exe -m backend.app.cli create-admin --email admin@example.com --name 'Initial Admin'
```

Admin bootstrap prompts for the password, is refused if any admin already
exists, and is the only code path that grants the `admin` role. Public signup
always creates a `user`.

## Run services

```powershell
& .\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd .\frontend
npm install
npm run dev
```

OpenAPI is served at `/docs` in development; docs are disabled in production.
Set `frontend/.env.local` from `.env.example` if the API is not at the local
default.

## Test

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest .\backend\tests -q
cd .\frontend
npm run build
```

Backend unit/integration tests use an isolated in-memory SQLite database only
for tests. Production and migration paths reject SQLite and require PostgreSQL.
`requirements.txt` pins direct dependencies; `requirements.lock` captures the
tested Windows/Python 3.12 environment.
Neon connectivity, actual migration execution, and model inference through the
HTTP service remain unverified until valid deployment credentials and runtime
dependencies are configured.

## Contract

The API prefix is `/api/v1`. Authentication uses an opaque server-side session
cookie (`HttpOnly`, `SameSite=Strict`) and a separate CSRF token cookie/header.
All data mutations require CSRF validation. User-facing plan, result, share, and
notification queries enforce ownership; admins can read all plans/results and
manage account status, but cannot review their own plan. Only roles `user` and
`admin` are accepted.

Frontend editor nodes are translated to the Day 1 model schema (`router` or
`host`); link bandwidth/latency/loss units are passed in Mbps/ms/percent. Traffic
classes and `link_failure` are translated to the model's `QoSClass` and
`link_failures` names. The model currently returns aggregate loss, mean/p95
latency, throughput, congestion fraction, flapping, and fallback information.
It does not return per-step telemetry, a median latency, or path-history arrays;
the API does not fabricate those fields.
