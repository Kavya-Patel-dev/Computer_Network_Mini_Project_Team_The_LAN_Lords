# Frontend/backend integration map

| Frontend operation | API | Persistence / service |
| --- | --- | --- |
| Register, login, restore session, logout | `/api/v1/auth/*` | Argon2id password hash, DB-backed sessions, CSRF cookie/header |
| Profile and password changes | `/api/v1/users/me*` | User row; password change revokes other sessions |
| Current session list/revoke other sessions | `/api/v1/users/me/sessions*` | Session metadata only; session secrets are never returned |
| Create, list, edit, submit, withdraw plan | `/api/v1/records*` | Owner FK, plan JSON, version-event history, model-input validation |
| Admin review queue and decisions | `GET /api/v1/records`, `POST /api/v1/records/{id}/review` | Admin-only decision, blocks self-review, persists review, notification, and audit event |
| Run approved plan | `POST /api/v1/records/{id}/runs` | Genuine frozen `models.api.simulate`, persisted result and checkpoint hash |
| Results catalog/detail | `/api/v1/results*` | Owner-filtered; admin can inspect all; raw scenario metrics included |
| Share result | `/api/v1/results/{id}/share`, `/api/v1/shares*` | Random bearer token stored as HMAC digest, 14-day expiry, view count, revocation |
| Notifications | `/api/v1/notifications*` | Per-user persistent notices, read state |
| User/admin dashboards | `/api/v1/dashboard/*` | Counts and review analytics queried from PostgreSQL |
| Admin users, role/status changes, and audit | `/api/v1/admin/users*`, `/api/v1/admin/audit` | Admin-only; no self role/status change; last active admin protected |
| Admin model page | `GET /api/v1/admin/model` | Verifies the pinned checkpoint SHA-256 from disk |
| Readiness | `/health`, `/ready` | Liveness is separate from Neon and checkpoint readiness |

## Verified compatibility

- The frontend canvas node, link, flow, bandwidth, latency, loss, and QoS fields are translated by `backend/app/services.py` to the Day 1 model API shape.
- A real short simulation used `AI/examples/topology.json`, the frozen checkpoint, and the backend environment. All three policies returned metrics and shared the same request-sequence hash.
- A short backend suite covers registration/session/CSRF, owner isolation, admin authorization, user role changes, session revocation, share creation/revocation, model hash, analytics and the schema adapter.
- `frontend/.env.example` points to the backend API; cookie credentials and CSRF headers are sent by the centralized client.

## Still unverified or incomplete

- No Neon `DATABASE_URL` is configured. Neon connectivity and applying the migration to a real project are not verified.
- Email delivery credentials are absent; password reset, verification, and invitations are not available. Their pages now state this instead of reporting a false success.
- The topology form, topology generator, review actions, run overview, shared result, and version history now use saved backend records. Version history stores event summaries, not immutable topology snapshots, so structural diffs are unavailable.
- The public demo and what-if page are intentionally unavailable until real public demo/temporary-topology endpoints exist. They no longer present hardcoded benchmark improvements as live results.
- Heatmap, explainability, and failure views show only aggregate metrics available in the saved result. Per-step heatmap history, candidate paths, Q-values, attention attribution, and event-level recovery traces are not produced by the frozen model API.
- The model returns aggregate metrics. It does not expose per-step heatmap history, attention attribution for a saved run, or median latency; those must not be fabricated.
- Admin platform settings, account deletion, and persistent notification preferences are not connected to server storage yet.
- The root Project directory has no Git repository. The nested `AI/` repo remains dirty from earlier work; frozen `AI/env/`, `AI/baselines/`, `AI/data/splits.json`, and `AI/data/splits.lock` currently have no diff from HEAD. The new `backend/` folder and its `.venv` are outside `AI/`.
