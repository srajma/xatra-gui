# Xatra Web Deployment Plan (`indica.org/xatra`)

As of February 24, 2026.

## Scope
This plan covers the remaining must-do items:
- Render worker queue/pool
- DB migration plan (SQLite -> Postgres)
- Observability (metrics + alerts)
- Backup/restore
- Production deployment at `https://indica.org/xatra`
- Google OAuth integration

`Trusted Python sandboxing` is intentionally out of scope for now.

## Current Gaps (Short)
- Rendering is process-per-request with no global queue/cap and 60s wait.
- SQLite is the primary DB and will become a write/concurrency bottleneck.
- No production observability stack (metrics, dashboards, alerts).
- No formal backup/restore runbook.
- Google auth endpoint is currently a placeholder (`POST /auth/google`).

## Phase Plan

### Phase 0 (1 week): Production Baseline
1. Path-prefix readiness (`/xatra`):
   - Add frontend base path support (`/xatra/`) in Vite build.
   - Add API base support (`/xatra/api`) so frontend and API share same origin.
2. Deploy topology:
   - Nginx reverse proxy + TLS
   - FastAPI backend as a `systemd` service
   - Static frontend build served by Nginx
3. Security baseline:
   - Strong `XATRA_ADMIN_PASSWORD`
   - Cookie secure mode enabled behind TLS
   - Firewall: only `80/443` public, backend bound to localhost.

Exit criteria:
- `https://indica.org/xatra` loads and all API calls work through `/xatra/api`.

### Phase 1 (1-2 weeks): Render Queue/Pool
1. Introduce bounded render concurrency:
   - Global queue + fixed worker pool (start with `N = vCPU - 1`).
   - Reject or queue overflow with clear 429/503 response.
2. Keep per-user cancellation semantics but cancel queued/running jobs safely.
3. Add queue metrics:
   - queue depth
   - job wait time
   - render duration p50/p95
   - timeout/error rates

Exit criteria:
- Under load, backend stays responsive and render latency degrades gracefully.

### Phase 2 (1-2 weeks): SQLite -> Postgres
1. Schema strategy:
   - Move SQL into a migration-managed layer (Alembic or equivalent).
   - Keep table names and semantics close to current hub schema.
2. Dual-run migration:
   - One-time SQLite export/import to Postgres in staging.
   - Validate row counts, indexes, unique constraints, auth/session behavior.
3. Cutover:
   - Brief maintenance window
   - Back up SQLite file first
   - Switch app DB connection to Postgres

Exit criteria:
- All auth/hub/draft/publish flows pass against Postgres in production.

### Phase 3 (3-5 days): Observability + Backup/Restore
1. Observability:
   - Structured app logs (JSON)
   - Prometheus metrics endpoint
   - Grafana dashboard
   - Alerts: high error rate, high queue depth, high p95 render, DB errors, low disk
2. Backups:
   - Daily Postgres backup + retention policy
   - Weekly restore drill in staging
   - Documented RPO/RTO (example: RPO 24h, RTO 2h initially)

Exit criteria:
- On-call can detect failures quickly and recover data from backup.

## Infra Sizing and Cost Estimate

These are planning ranges, not quotes. Actual costs vary by region/provider and traffic profile.

### Quick Sizing Formula
- `required_render_slots ~= peak_render_requests_per_sec * p95_render_seconds * 1.3`
- Start with:
  - worker slots ~= available CPU cores for render workers
  - memory budget ~= `(memory per render worker * slots) + 30-40% headroom`

### Practical Starting Tiers
1. **Small beta** (up to ~50 active editors, low burst)
   - App VM: 4 vCPU / 8 GB RAM
   - Postgres: managed 1-2 vCPU / 2-4 GB
   - Estimated monthly: **$70-$150**
2. **Early production** (~50-150 active editors, moderate burst)
   - App VM: 8 vCPU / 16 GB RAM
   - Postgres: managed 2 vCPU / 8 GB
   - Optional Redis for queue/cache
   - Estimated monthly: **$180-$400**
3. **Growth** (higher concurrency / bursty render load)
   - 2 app nodes + load balancer
   - Managed Postgres with read replica
   - Estimated monthly: **$450-$1,000+**

Notes:
- 1000 registered users is easy; 1000 simultaneous heavy renders is not.
- Rendering throughput, not HTTP QPS, is the dominant cost driver.

## Deployment Runbook (`indica.org/xatra`)

### 1. DNS and Host
1. Point `A/AAAA` records for `indica.org` to your server.
2. SSH into host (Ubuntu 24.04 LTS recommended).
3. Install packages:
   ```bash
   sudo apt update
   sudo apt install -y nginx certbot python3-certbot-nginx git build-essential
   ```

### 2. App Setup
1. Clone repo to `/srv/xatra_gui`.
2. Install Python 3.12, `uv`, Node 20+.
3. Build frontend for subpath:
   - Set Vite base to `/xatra/`.
   - Set `VITE_API_BASE=/xatra/api`.
4. Backend env (`/srv/xatra_gui/.env`):
   - `XATRA_BACKEND_HOST=127.0.0.1`
   - `XATRA_BACKEND_PORT=8088`
   - `XATRA_COOKIE_SECURE=true`
   - `XATRA_ADMIN_PASSWORD=<strong-secret>`
   - `XATRA_EXTRA_CORS_ORIGINS=https://indica.org` (safe default even if same-origin)

### 3. Systemd Service (Backend)
Create `/etc/systemd/system/xatra-backend.service`:
```ini
[Unit]
Description=Xatra Backend
After=network.target

[Service]
User=www-data
WorkingDirectory=/srv/xatra_gui
EnvironmentFile=/srv/xatra_gui/.env
ExecStart=/srv/xatra_gui/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8088
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now xatra-backend
sudo systemctl status xatra-backend
```

### 4. Nginx Config (`/xatra` + `/xatra/api`)
Create `/etc/nginx/sites-available/indica.org`:
```nginx
server {
    listen 80;
    server_name indica.org;

    location = /xatra { return 301 /xatra/; }

    location /xatra/api/ {
        proxy_pass http://127.0.0.1:8088/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Prefix /xatra;
    }

    location /xatra/ {
        alias /srv/xatra_gui/frontend/dist/;
        try_files $uri $uri/ /xatra/index.html;
    }
}
```

Enable and test:
```bash
sudo ln -s /etc/nginx/sites-available/indica.org /etc/nginx/sites-enabled/indica.org
sudo nginx -t
sudo systemctl reload nginx
```

### 5. TLS
```bash
sudo certbot --nginx -d indica.org
sudo systemctl reload nginx
```

### 6. Release Procedure
1. Pull latest code.
2. Rebuild frontend.
3. Restart backend service.
4. Smoke-test:
   - `/xatra/`
   - `/xatra/api/health`
   - login, render, publish, explore.

## Google OAuth Integration Plan

## Product choice
Use Google Identity Services with ID token verification on backend (no custom OAuth code flow needed for basic login).

### 1. Google Cloud Setup
1. In Google Cloud Console, configure OAuth consent screen.
2. Create OAuth Client ID (Web application).
3. Authorized JavaScript origin:
   - `https://indica.org`
4. (If using redirect flow) Authorized redirect URI:
   - `https://indica.org/xatra`

### 2. Backend Changes
1. Add columns to `hub_users`:
   - `google_sub` (unique, nullable)
   - `email` (nullable)
   - `email_verified` (bool)
2. Replace `/auth/google` placeholder:
   - Accept Google ID token from frontend.
   - Verify token signature and claims (`iss`, `aud`, `exp`, `email_verified`).
   - Upsert local user by `google_sub` (or verified email linking policy).
   - Issue existing session cookie via current session mechanism.
3. Add env vars:
   - `GOOGLE_CLIENT_ID`
   - optional allowed hosted domain (`GOOGLE_HD`) if needed.

### 3. Frontend Changes
1. Add “Sign in with Google” button on login screen.
2. Load GIS script and request credential.
3. POST credential to `/xatra/api/auth/google`.
4. On success, refresh `/auth/me` and continue existing auth state flow.

### 4. Security Policy Decisions
1. Email linking policy:
   - safest: link only by `google_sub`; do not auto-merge by email unless verified and confirmed.
2. Username policy:
   - generate from email prefix + suffix if collision.
3. Account recovery:
   - Google users can remain passwordless; keep local password optional.

## Minimal Monitoring/Alert Set (Day 1)
- `render_requests_total`, `render_errors_total`, `render_timeout_total`
- `render_duration_seconds` histogram
- `render_queue_depth`, `render_queue_wait_seconds`
- DB latency/error counters
- host CPU, RAM, disk, load

Alerts:
- p95 render > 15s for 10m
- queue depth > worker_count * 2 for 5m
- error rate > 5% for 5m
- disk free < 15%

## References
- Vite `base` for sub-path deploy: https://vite.dev/config/shared-options#base
- Google Identity Services (web): https://developers.google.com/identity/gsi/web/guides/overview
- Verify Google ID tokens: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- OpenID Connect claims (`iss`, `aud`, etc.): https://openid.net/specs/openid-connect-core-1_0.html

