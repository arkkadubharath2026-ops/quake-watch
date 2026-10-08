# Deploying to Render

QuakeWatch is a server-rendered Django monolith (ADR-011): there is no separate frontend to
deploy. `render.yaml` runs the same image as `docker-compose.yml`, split into the same
web / worker / scheduler roles, against ArangoDB (private service + disk) — the only stateful
service (ADR-014/015: no managed Redis, no SQLite file).

## One-time setup

1. Push this repo to GitHub (already done) and note the branch to deploy from.
2. In the Render dashboard: **New +** → **Blueprint**, pick this repo/branch. Render reads
   `render.yaml` at the repo root and proposes 4 services: `quakewatch-web`, `quakewatch-worker`,
   `quakewatch-scheduler`, `quakewatch-arangodb`.
3. Before the first deploy, set these secrets on **each** service that lists them (dashboard →
   service → Environment):
   - `quakewatch-arangodb`: `ARANGO_ROOT_PASSWORD` — a strong password.
   - `quakewatch-web`, `quakewatch-worker`, `quakewatch-scheduler`: `QW_SECRET_KEY` (50+ random chars,
     e.g. `python -c "import secrets; print(secrets.token_urlsafe(64))"`) and `QW_ARANGO_PASSWORD`
     — use the **same** value as `ARANGO_ROOT_PASSWORD` above (this deployment profile uses the
     Arango root user directly, matching `docker-compose.yml`).
4. Deploy. Render builds `docker/Dockerfile` once and reuses the image for all three app
   services. `quakewatch-arangodb` starts from the upstream `arangodb` image on its own disk.
5. First boot of `quakewatch-web` runs `manage.py arango_migrate`
   automatically (`docker/entrypoint.sh`) — no manual migration step.

## The 5-step procedure (after render.yaml is in the repo)

1. Render dashboard → **New +** → **Blueprint** → select this repo/branch.
2. Fill in the secrets Render prompts for (`QW_SECRET_KEY`, `QW_ARANGO_PASSWORD`,
   `ARANGO_ROOT_PASSWORD` — same value as `QW_ARANGO_PASSWORD`).
3. Click **Apply** — Render provisions `quakewatch-web`, `quakewatch-worker`, `quakewatch-scheduler`,
   `quakewatch-arangodb` and builds the image.
4. Wait for `quakewatch-web` to go green (health check hits `/health/ready`).
5. Open the URL Render assigns to `quakewatch-web` (see below) — the whole app (pages + API)
   is live there.

## Does the frontend get its own URL?

No separate frontend URL — there is no separate frontend. Render gives the **`quakewatch-web`
service** a single public URL, e.g. `https://quakewatch-web.onrender.com` (or a name you choose /
a custom domain you attach later). That one URL serves everything: the server-rendered pages
(dashboard, explorer, alerts UI) **and** the JSON API under `/api/...` used by their "API islands"
(ADR-011). `quakewatch-worker`, `quakewatch-scheduler`, and `quakewatch-arangodb` are private/background
services with no public URL — they're only reachable internally by `quakewatch-web`.

## Notes / follow-ups

- `QW_ALLOWED_HOSTS=.onrender.com` and `QW_CSRF_TRUSTED_ORIGINS=https://*.onrender.com` accept
  Render's default `*.onrender.com` hostname. If you attach a custom domain, add it explicitly to
  both (comma-separated) in the `quakewatch-web` environment.
- The `starter` plans in `render.yaml` are a starting point — pick sizes that fit your budget in
  the dashboard; the free tier's private-service disks and always-on workers have restrictions
  that don't fit the always-on worker/scheduler well.
- Render's Blueprint schema evolves; if `render.yaml` fails to validate on sync, check the
  specific field the error names against Render's current Blueprint docs — the shape of this file
  (image-based private service, `dockerCommand` override) was correct as of this writing but field names occasionally change upstream.
- Retire the old Vercel project (`quake-watch-mu.vercel.app`) — it was serving no build output for
  this architecture and 404s by design; there is nothing there to fix.
