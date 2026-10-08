# ADR-013: Deploy to Render as one Docker image, not a separate frontend host

- **Status:** Accepted; amended by ADR-014/015 (2026-10-07): services are web / worker / scheduler,
  ArangoDB is the only stateful service (no managed Redis, no SQLite auth file).
- **Date:** 2026-09-26

## Context
The project's frontend was mistakenly deployed to Vercel (`quake-watch-mu.vercel.app`), which
404s because there is no separate frontend build: QuakeWatch is a server-rendered Django monolith
with API islands (ADR-011), and the ESD's only deployment profile (§18) is the Docker Compose
stack (web / worker / beat / ArangoDB / Redis) used for local/college-demo deployment.

The owner asked to make the existing repo deployable on Render, a platform that hosts Docker
images and offers managed Redis but not managed ArangoDB.

## Decision
1. Deploy the existing `docker/Dockerfile` image unchanged to Render as three services —
   `quakewatch-web` (Gunicorn), `quakewatch-worker`, `quakewatch-beat` — using the same
   `docker/entrypoint.sh web|worker|beat` commands as `docker-compose.yml`, so behaviour cannot
   drift between local and Render.
2. Run ArangoDB as a Render **private service** from the upstream `arangodb` image with a
   persistent disk, since Render has no managed ArangoDB offering. It is reachable only
   internally, at `quakewatch-arangodb:8529`.
3. Use Render's managed Redis for the Celery broker/cache, matching ADR-009's "Redis is
   broker/cache only" boundary.
4. Encode all of this as a `render.yaml` Blueprint at the repo root so the whole stack is
   reproducible from one dashboard action, instead of manually wiring five services.
5. No frontend rewrite. The task description's "quickly rebuild in React" option was rejected:
   there is no product requirement for a decoupled frontend, and doing so would be an
   unrequested architecture change to ADR-011.

## Consequences
- One public URL (`quakewatch-web`'s Render URL) serves both pages and the API, as it does today
  in Compose — no CORS or dual-deploy concerns.
- `QW_ALLOWED_HOSTS` / `QW_CSRF_TRUSTED_ORIGINS` are set to accept `*.onrender.com` by default;
  a custom domain requires adding it explicitly (docs/RENDER_DEPLOY.md).
- ArangoDB on a single private-service disk has no managed HA/backups the way a managed database
  would; acceptable for the current demo-scale deployment profile, same tradeoff already accepted
  for the Compose profile in ESD §18.
- Vercel project should be retired — it was never the right target for this architecture.

## Alternatives considered
- **Rebuild the frontend in React, deployed on Vercel** — rejected. No requirement calls for a
  decoupled SPA; it would duplicate all page logic already implemented in Django templates and
  contradicts ADR-011 without a documented product reason.
- **ArangoDB via a third-party managed service (e.g. ArangoDB Oasis)** — viable alternative if
  Render's private-service disk proves insufficient (no automated backups/HA). Not adopted now to
  keep the deployment profile identical to the already-validated Compose stack.
