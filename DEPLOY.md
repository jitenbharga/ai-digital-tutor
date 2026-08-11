# 🚀 Deploy Guide — AI Digital Tutor (Free tier)

**Stack chosen:** Backend → **Google Cloud Run** · Database → **MongoDB Atlas (M0 free)** · Frontend → **Vercel** · Region → **Mumbai (`asia-south1`)** for best India latency.

```
Browser
  │
  ├── https://<you>.vercel.app         (React static — Vercel CDN, free)
  │        │  /api/* rewrite (same-origin, keeps auth cookie)
  │        ▼
  └── https://<you>.run.app            (FastAPI — Cloud Run, free 2M req/mo)
           │
           ▼
     MongoDB Atlas M0                   (512 MB free, Mumbai)
     + Groq / Mistral APIs             (external, their own free tiers)
```

> **Deploy order matters.** Do the steps top-to-bottom. Tip: **decide your Vercel project name first** (e.g. `ai-tutor`) so you already know the frontend URL `https://ai-tutor.vercel.app` and can set it in the backend before the frontend even exists. That avoids back-and-forth.

---

## 0. One-time accounts (free, no cost)

| Account | Card needed? | Link |
|---|---|---|
| GitHub | No | github.com |
| MongoDB Atlas | No | mongodb.com/cloud/atlas |
| Google Cloud (for Cloud Run) | **Yes** (card on file, won't be charged on free tier) | console.cloud.google.com |
| Vercel | No | vercel.com |
| Upstash (Redis rate-limit store) | No | upstash.com |

Also install the **gcloud CLI**: https://cloud.google.com/sdk/docs/install

---

## 1. Push code to GitHub

From the project root:

```bash
git init                      # if not already a repo
git add .
git commit -m "Deploy: Cloud Run + Atlas + Vercel"
git branch -M main
git remote add origin https://github.com/<you>/ai-digital-tutor.git
git push -u origin main
```

✅ Both backend (root) and frontend (`frontend/`) live in this one repo. That's fine — we point each platform at the right folder.

> **Never commit secrets.** Make sure `.env`, `.env.local`, and `env.yaml` are in `.gitignore`.

---

## 2. Database — MongoDB Atlas (free M0)

1. Atlas → **Build a Database** → **M0 (Free)** → Provider **AWS**, Region **Mumbai (ap-south-1)** → Create.
2. **Database Access** → Add New User → username + strong password → role **Read and write to any database**.
3. **Network Access** → Add IP → **Allow access from anywhere** `0.0.0.0/0` (Cloud Run has no fixed IP).
4. **Connect → Drivers** → copy the connection string:
   ```
   mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
   Replace `<password>` with the real one. Keep this — it's your `MONGODB_URI`.

---

## 3. Backend — Google Cloud Run

### 3a. Generate a strong JWT secret (required, ≥32 chars)

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Copy the output → that's your `SECRET_KEY`.

### 3b. Create the env file (local only — DO NOT commit)

**First — free rate-limit store (REQUIRED).** The backend **refuses to boot** with `ENVIRONMENT=production` unless `RATE_LIMIT_STORAGE_URI` is set (Cloud Run can run multiple instances, so per-process in-memory limits would be bypassable — `rate_limit.py` raises `RuntimeError` at import). Set up a free **Upstash Redis** — no card:

1. upstash.com → sign in (GitHub/Google) → **Create Database → Redis** → name `ai-tutor-rl`, region near **Mumbai/Singapore**.
2. On the database page copy the **`rediss://` connection URL** (looks like `rediss://default:<password>@<host>.upstash.io:6379`) → that's your `RATE_LIMIT_STORAGE_URI`.

> Free tier = 256 MB + 500K commands/month — plenty for low-traffic rate limiting.

Now create `env.yaml` in the project root:

```yaml
ENVIRONMENT: "production"
MONGODB_URI: "mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
DB_NAME: "ai_tutor"
# Shared rate-limit store — REQUIRED in production (app won't boot without it):
RATE_LIMIT_STORAGE_URI: "rediss://default:<password>@<host>.upstash.io:6379"
SECRET_KEY: "<paste the 48-char secret>"
# Your frontend URL (decide the Vercel project name now):
APP_BASE_URL: "https://ai-tutor.vercel.app"
ALLOWED_ORIGINS: "https://ai-tutor.vercel.app"
GOOGLE_CLIENT_ID: "<your-google-client-id>.apps.googleusercontent.com"
# LLM keys:
MISTRAL_API_KEY_1: "..."
MISTRAL_API_KEY_2: "..."
MISTRAL_API_KEY_3: "..."
GROQ_API_KEY_1: "..."
GROQ_API_KEY_2: "..."
GROQ_API_KEY_3: "..."
# Email verification (Gmail: use an App Password, not your login password):
SMTP_HOST: "smtp.gmail.com"
SMTP_PORT: "587"
SMTP_USER: "youraddress@gmail.com"
SMTP_PASSWORD: "<gmail app password>"
SMTP_FROM: "AI Tutor <youraddress@gmail.com>"
```

Add it to gitignore:
```bash
echo "env.yaml" >> .gitignore
```

### 3c. Deploy (one command — Cloud Build uses your Dockerfile)

```bash
gcloud auth login
gcloud config set project <YOUR_GCP_PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

gcloud run deploy ai-tutor-api \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --timeout 300 \
  --env-vars-file env.yaml
```

- First build takes ~5–10 min (torch/faiss are large).
- `--memory 2Gi` is needed because the app loads **torch + faiss** at startup.
- When it finishes it prints a **Service URL**: `https://ai-tutor-api-xxxxx-el.a.run.app` → **copy it**.

### 3d. Verify backend is alive

```bash
curl https://ai-tutor-api-xxxxx.a.run.app/healthz
```
Should return OK. (First hit after idle = ~10–15 s cold start because torch loads — normal on free.)

> **Auto-deploy from GitHub (optional):** Cloud Run console → your service → **Set up Continuous Deployment** → pick the repo/branch. After that every `git push` rebuilds automatically. Env vars stay as you set them.

---

## 4. Frontend — Vercel

1. Edit **`frontend/vercel.json`** → replace `REPLACE_WITH_CLOUD_RUN_URL` with your Cloud Run host (no `https://`, no trailing slash), e.g.:
   ```json
   { "source": "/api/:path*", "destination": "https://ai-tutor-api-xxxxx.a.run.app/:path*" }
   ```
   Commit + push this change.
2. Vercel → **Add New Project** → import your GitHub repo.
3. **Settings:**
   - **Project Name:** `ai-tutor` (must match the URL you put in `APP_BASE_URL`/`ALLOWED_ORIGINS`).
   - **Root Directory:** `frontend`
   - **Framework Preset:** Vite (auto-detected)
   - Build command / output dir come from `vercel.json` (`npm run build` → `dist`).
4. **Environment Variables** (Vercel → Settings → Environment Variables):
   - `VITE_GOOGLE_CLIENT_ID` = `<your-google-client-id>.apps.googleusercontent.com`
5. **Deploy.** You get `https://ai-tutor.vercel.app`.

> Why the `/api` rewrite? The app calls `/api/*` on its **own** origin, and Vercel silently proxies to Cloud Run. This keeps the login **refresh cookie same-site** (httpOnly) — a direct cross-domain call would break auth cookies.

---

## 5. Google OAuth ("Continue with Google")

Google Cloud Console → **APIs & Services → Credentials** → your **OAuth 2.0 Client ID** → add under **Authorized JavaScript origins**:

```
https://ai-tutor.vercel.app
```

(Keep `http://localhost:5173` too for local dev.) Save. GIS runs on the frontend origin, so only the Vercel URL is needed here.

---

## 6. Final wiring check

If your real Vercel URL differs from what you guessed, update the backend and redeploy:

```bash
# edit env.yaml → APP_BASE_URL and ALLOWED_ORIGINS = real vercel url
gcloud run deploy ai-tutor-api --source . --region asia-south1 \
  --allow-unauthenticated --memory 2Gi --cpu 1 --timeout 300 --env-vars-file env.yaml
```

---

## 7. Smoke test (open `https://ai-tutor.vercel.app`)

- [ ] Landing page loads, no console errors
- [ ] Sign up → verification email arrives → click link → account active
- [ ] Log in (email + password) → lands on Home
- [ ] "Continue with Google" works
- [ ] Open a topic → **auto summary card** appears, then first question
- [ ] Send an answer → tutor replies (LLM working)
- [ ] Mobile: bottom nav fits, side panels open full-screen, no horizontal scroll

---

## 8. Redeploy later (routine)

| Change | Command / action |
|---|---|
| Backend code/env | `gcloud run deploy ai-tutor-api --source . --region asia-south1 --allow-unauthenticated --memory 2Gi --cpu 1 --timeout 300 --env-vars-file env.yaml` (or just `git push` if Continuous Deployment is on) |
| Frontend code | `git push` → Vercel auto-builds |

---

## 9. Free-tier notes & gotchas (read once)

- **Cold start ~10–15 s:** the app imports torch/faiss on boot; on free Cloud Run (scale-to-zero) the first request after idle is slow. To keep it always warm set `--min-instances 1` (leaves free tier → small cost). For a portfolio/demo, cold start is fine.
- **Free limits:** Cloud Run 2M requests + 360k GB-seconds/month; at 2 GiB that's ~50 hrs of *active* time/month — plenty for low traffic since idle costs nothing.
- **File uploads are ephemeral:** the Materials page writes to the container disk, which is wiped on restart. For persistent uploads add object storage (Cloudflare R2 free 10 GB, or Atlas GridFS) later.
- **Rate-limit store is required in production:** with `ENVIRONMENT=production` the app **refuses to boot** unless `RATE_LIMIT_STORAGE_URI` is set (step 3b, free Upstash Redis). This keeps limits correct across Cloud Run's multiple instances.
- **Secrets:** never commit `env.yaml` / `.env`. For extra safety, move secrets to **Google Secret Manager** and reference them with `--set-secrets` instead of `--env-vars-file`.
- **Gmail SMTP:** use an **App Password** (Google Account → Security → 2-Step Verification → App passwords), not your normal password.

---

## 10. Env var reference (backend)

| Required | Purpose |
|---|---|
| `MONGODB_URI`, `DB_NAME` | Atlas connection |
| `SECRET_KEY` | JWT signing (≥32 random chars) |
| `APP_BASE_URL` | Frontend URL — used in verification email links |
| `ALLOWED_ORIGINS` | CORS — set to the frontend URL |
| `GOOGLE_CLIENT_ID` | Verify Google sign-in tokens |
| `MISTRAL_API_KEY_1..3`, `GROQ_API_KEY_1..3` | LLM pool |
| `SMTP_HOST/PORT/USER/PASSWORD/FROM` | Email verification |
| `ENVIRONMENT=production` | Prod behaviour |
| `RATE_LIMIT_STORAGE_URI` | Shared rate-limit store (Redis) — **required** when `ENVIRONMENT=production` (free Upstash) |

| Optional | Purpose |
|---|---|
| `SENTRY_DSN` | Error tracking |
| `YOUTUBE_API_KEY`, `TAVILY_API_KEY`, `SEMANTIC_SCHOLAR_KEY` | Extra content sources |

**Frontend (Vercel):** `VITE_GOOGLE_CLIENT_ID` only.
