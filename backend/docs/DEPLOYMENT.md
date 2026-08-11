# Deployment Runbook (W8)

Production deploy, configuration, scaling, observability, scheduling, and rollback.
See also `docs/BACKUP.md` (backups/restore) and `docs/ARCHITECTURE.md` (layering).

## 1. Prerequisites / secrets

Provide via a secret store (not committed):

| Var | Required | Notes |
|---|---|---|
| `SECRET_KEY` | ✅ | ≥ 32 random chars — the app refuses to boot otherwise (H-3). `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `MONGODB_URI` | ✅ | authenticated in prod (`...@mongo:27017/?authSource=admin`) |
| `MONGO_ROOT_USER` / `MONGO_ROOT_PASSWORD` | ✅ (compose) | Mongo `--auth` (M-9) |
| `RATE_LIMIT_STORAGE_URI` | ✅ prod | e.g. `redis://redis:6379` — required in prod so limits hold across workers (H-4) |
| `ENVIRONMENT` | ✅ | `production` (enables HSTS, disables `/docs`, enforces the above) |
| ≥1 LLM key | ✅ | `GEMINI_API_KEY` / `GROQ_API_KEY` / `MISTRAL_API_KEY` — engines build a model at import |
| `AUTO_ENSURE_INDEXES` | prod=`0` | indexes owned by the migration step, not startup |
| `SENTRY_DSN` | optional | error tracking (no-op if unset) |
| `LOG_FORMAT` | optional | `json` for structured logs (ELK/Loki/CloudWatch) |
| `SMTP_*` | optional | password-reset / verification / guardian digest email |
| `USER_CACHE_TTL_SECONDS` | optional | auth user-lookup cache TTL (default 30; 0 disables) |
| `RETAIN_*_DAYS` | optional | telemetry retention |

Full list + defaults: `.env.example`.

## 2. Deploy sequence

```bash
# 1. Migrate indexes as an explicit, fail-loud step (blocks a bad rollout).
python -m scripts.migrate_indexes

# 2. Bring up the stack (base + prod overrides: Mongo --auth, no exposed DB ports).
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 3. Readiness: 200 with {"mongo": true, "rate_limit_store": true}
curl -fsS http://localhost:8000/healthz
```

Zero-downtime: roll workers/replicas behind the load balancer; `/healthz` gates
traffic. Index migrations here are additive/idempotent (safe during a rolling deploy).

## 3. Scaling

- **Stateless API** — scale horizontally (more uvicorn workers / replicas). Shared
  state (rate limits, LLM budget) is already externalized to Mongo/Redis, so scaling
  is correct (H-4). The user cache is per-worker (short TTL, write-invalidated); move
  it to Redis behind the `core/user_cache` seam if cross-worker staleness matters.
- **Mongo** — start as a replica set (also enables PITR); design shard keys before
  the append-heavy collections (`interactions`, `rl_transitions`, `llm_calls`) get large.
- **Redis** — single instance is fine for rate limiting; use managed/HA for prod.

## 4. Observability

- **Metrics:** `GET /metrics` (Prometheus text). `http_requests_total{method,route,status}`
  and `http_request_duration_seconds{method,route}`, labeled by **route template** (bounded
  cardinality). Per-worker — scrape each worker, or run prometheus_client in multiprocess
  mode (`PROMETHEUS_MULTIPROC_DIR`) behind multiple workers.
- **Health:** `GET /healthz` → `{status, mongo, rate_limit_store}` (503 if Mongo down).
  Wire to the LB health check + an uptime monitor.
- **Errors:** set `SENTRY_DSN`.
- **Logs:** `LOG_FORMAT=json` for structured logs; every request carries `X-Request-ID`
  (echoed in logs) for correlation.
- **Suggested alerts:** `/healthz` != 200; 5xx rate (from `http_requests_total`); p95
  latency; LLM daily-budget 429 spikes; rate-limit store unreachable.

## 5. Scheduled maintenance

Run on a scheduler (cron / systemd timer / a Cowork scheduled task):

```cron
# Nightly telemetry prune (bounds unbounded growth)
30 3 * * *  cd /app && python -m scripts.telemetry_maintenance
# Nightly Mongo backup (see docs/BACKUP.md)
0  2 * * *  mongodump --uri "$MONGODB_URI" --archive=/backups/ai_tutor-$(date +\%F).gz --gzip
```

## 6. Rollback

- **App:** redeploy the previous image tag (stateless; safe).
- **Indexes:** additive — a rollback needs no index revert. If a specific index is
  problematic, drop it explicitly; don't roll the whole schema back.
- **Data:** restore from the latest `mongodump` (`docs/BACKUP.md`) only for data
  corruption — not for app rollbacks.

## 7. Tracked follow-up — react-router v7 migration

Two moderate advisories (open redirect, SSR-hydration injection) are only patched in
**react-router 7.18+** (a breaking major bump). They're non-exploitable in this CSR SPA
(no SSR; internal-literal navigation only), so the upgrade is deferred — **do it as its
own change, gated on E2E**:

1. `npm i react-router-dom@^7` and regenerate the lock.
2. Update imports/config for v7 (mostly compatible with v6 data routers).
3. Run the Playwright E2E suite (login/tutor/quiz/guardian) — must stay green.
4. `npm audit` → 0 moderate; then ship.
