# Security Operations

## Secret scanning (SEC-9)

CI runs **gitleaks** on every push/PR (see `.github/workflows/ci.yml`,
`secret-scan` job) and fails the build if a secret is committed.

Add the same check locally as a pre-commit hook. Create
`.pre-commit-config.yaml` at the repo root with:

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
```

Then:

```bash
pip install pre-commit
pre-commit install
```

Every `git commit` now scans the staged diff and blocks commits containing
API keys, tokens, or `.env` values.

## Key rotation

Secrets live only in `.env` (git-ignored; `.env.example` documents the keys).
Rotate on a schedule and immediately after any suspected exposure.

1. **`SECRET_KEY` (JWT signing).** Generate a new value
   (`python -c "import secrets; print(secrets.token_urlsafe(64))"`), update
   `.env`, and restart the API. All existing access **and** refresh tokens are
   invalidated, so every user must log in again — expected behaviour on
   rotation. For zero-downtime rotation, support a key-ID/`kid` scheme.
2. **LLM / provider API keys** (`OPENAI_API_KEY`, etc.). Issue a new key in the
   provider dashboard, update `.env`, restart, then revoke the old key.
3. **`MONGODB_URI` credentials.** Create a new DB user, update `.env`, restart,
   then drop the old user.
4. **`SENTRY_DSN`.** Rotate in the Sentry dashboard; update `.env`; restart.

After any rotation, confirm the old credential is fully revoked (not just
replaced) and grep history/logs to ensure it was never committed. If a secret
was ever committed, treat it as compromised: rotate **and** purge it from git
history (`git filter-repo`) since the public remote retains old commits.

## Deployment (SEC-9)

The API image runs multiple `uvicorn` workers (`--workers`, defaulting to CPU
count). Because the per-route rate limits (SEC-3) use slowapi's in-memory store
by default, that store is **per-worker** — set `RATE_LIMIT_STORAGE_URI` to a
shared backend (e.g. `redis://host:6379`) in production so limits are enforced
globally across workers.

## Dependency-audit gate (MF-1)

CI runs a blocking `dependency-audit` job (`.github/workflows/ci.yml`) on every
push/PR:

- **Frontend** — `frontend/scripts/check-npm-audit.mjs` wraps
  `npm audit --omit=dev --json` and fails on any **high/critical** advisory in
  shipped runtime deps. Dev-only tooling advisories (vitest/vite/esbuild) are
  out of scope via `--omit=dev`.
- **Backend** — `pip-audit -r requirements.txt` fails on advisories in the
  pinned runtime deps.

### Accepted advisories (allowlist)

Every accepted advisory must be listed here **and** in the relevant gate script,
each with a justification. Re-check on every dependency upgrade.

| Advisory | Package | Severity | Why accepted |
|---|---|---|---|
| [GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) | react-router `7.12.0–<8.3.0` | High | "RSC Mode CSRF Bypass." Only affects react-router's **RSC / framework (server) mode**. This app is a Vite SPA using declarative `<BrowserRouter>`/`<Routes>` only, so the vulnerable path is **unreachable**. We stay on `7.18.2` (which fixes the reachable open-redirect→XSS advisory affecting `≤7.17.0`); no CSRF-patched release `≥8.3.0` exists yet. Remove this entry once one ships. |
