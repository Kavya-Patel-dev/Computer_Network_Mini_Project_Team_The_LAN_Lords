# Frontend

The web interface for The LAN Lords is a React 18 and TypeScript single-page application. It uses Vite for development/builds, Tailwind CSS for styling, Recharts for charts, and Lucide for icons. Routes are hash-based, so pages appear as `http://localhost:5173/#/plans`.

## Run locally

From this folder in PowerShell:

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

The development server prints its local URL. The API base defaults to `http://localhost:8000/api/v1`; set `VITE_API_BASE_URL` in `.env.local` if the backend uses another address. Start the backend separately using the instructions in [`../backend/README.md`](../backend/README.md).

Build and type-check the frontend with:

```powershell
npm run build
```

There is no standalone frontend test script configured in `package.json`.

## Main user flows

- Register or sign in, then create a plan using the topology canvas, structured form, JSON import, or needs-based generator.
- Edit router/host devices and links, set traffic flows and scenarios, and submit the plan for review.
- After approval, run the saved simulation and view the persisted aggregate results.
- Administrators can review plans and manage users through the admin routes.

The API client in `src/api/client.ts` sends cookie credentials and the CSRF header for state-changing requests. The backend owns persistence and invokes the frozen model; the frontend does not train or run the model in the browser.

## Current limits

- The public demo is intentionally marked unavailable unless a demo service is configured.
- JSON topology import is supported; GraphML import is not implemented.
- The Cisco device/cable catalog under `src/mock/ciscoHardware.ts` is local catalog data, not a connection to Cisco Packet Tracer or a complete catalog of every Cisco product.
- Results are the aggregate metrics returned by the backend. Per-step heatmap history, Q-values/attention traces, and live packet-level telemetry are not provided by the current API.
- What-if, version-diff, email verification, and password-reset screens should not be interpreted as proof that their corresponding backend services are fully implemented. See the backend README for integration status.

## Configuration

Copy `.env.example` to `.env.local` for local configuration. Vite exposes `VITE_*` values in browser code, so never put database passwords, session secrets, or other private credentials in this file.
