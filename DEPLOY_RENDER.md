# 🚀 Deploy Guide — Backend on Render + Frontend on Vercel

**Final stack:** Backend → **Render** (Docker) · Database → **MongoDB Atlas (free)** · Frontend → **Vercel**.

```
Browser ─▶ https://<you>.vercel.app        (React SPA — Vercel CDN, free)
              │  /api/* rewrite (same-origin → auth cookie works)
              ▼
           https://<you>.onrender.com       (FastAPI — Render, free* )
              ▼
           MongoDB Atlas M0                  (512 MB free, Mumbai)
           + Groq / Mistral APIs             (external free tiers)
```

Repo already has: **`render.yaml`** (Render blueprint), **`frontend/vercel.json`** (proxy + SPA), **`Dockerfile`** ($PORT-ready).

---

## ⚠️ READ FIRST — Render free RAM vs this app

Render's **free** instance = **512 MB RAM, 0.5 CPU**. This app imports **torch + faiss at startup** (the RL tutor engine), which alone usually needs **more than 512 MB**. So on the free plan the backend will **very likely crash on boot with an out-of-memory (OOM) error**.

Your options:

1. **Try free first.** Deploy as-is; if it boots and answers, great (low-traffic demos sometimes squeak by).
2. **If it OOMs (most likely):**
   - **Cheapest that works:** switch backend to **Google Cloud Run** (2 GB free) — frontend stays on Vercel, only `vercel.json` changes. See `DEPLOY.md`. Or **Oracle VM** (12 GB free) — see `DEPLOY_ORACLE.md`.
   - **Stay on Render:** upgrade the service to **Standard (2 GB)** in `render.yaml` (`plan: standard`) — paid.
   - **Slim the app:** I can add a "lite mode" that lazy-loads / disables torch+faiss so it fits 512 MB (rule-based tutor). Ask me and I'll wire it.

Everything below still applies to whichever plan you pick.

---

## 0. Accounts (all free, no card)
GitHub · MongoDB Atlas · Render · Vercel.

> Tip: **decide your Vercel project name first** (e.g. `ai-tutor`) so you already know the frontend URL `https://ai-tutor.vercel.app` and can set it in the backend upfront.

---

## 1. Push to GitHub
```bash
git add .
git commit -m "Deploy: Render + Vercel"
git branch -M main
git remote add origin https://github.com/<you>/ai-digital-tutor.git
git push -u origin main
```
> Never commit secrets — keep `.env`, `.env.local` in `.gitignore`.

---

## 2. Database — MongoDB Atlas (free M0)
1. Atlas → **Build a Database → M0 (Free)** → AWS, **Mumbai (ap-south-1)** → Create.
2. **Database Access** → add user (username + strong password), role *Read/write to any database*.
3. **Network Access** → **Allow from anywhere** `0.0.0.0/0` (Render has no fixed IP).
4. **Connect → Drivers** → copy the URI:
   ```
   mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
   That's your `MONGODB_URI`.

---

## 3. Backend — Render

### 3a. Generate the JWT secret
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
→ this is `SECRET_KEY`.

### 3b. Deploy via Blueprint (uses `render.yaml`)
1. Render dashboard → **New + → Blueprint** → connect your GitHub repo → it detects `render.yaml`.
2. It creates a **Docker web service** in **Singapore**, health check `/healthz`.
3. Fill the **Environment Variables** it asks for (the `sync: false` ones):
   - `MONGODB_URI` = your Atlas URI
   - `SECRET_KEY` = the 48-char secret
   - `APP_BASE_URL` = `https://ai-tutor.vercel.app` (your Vercel URL)
   - `ALLOWED_ORIGINS` = `https://ai-tutor.vercel.app`
   - `GOOGLE_CLIENT_ID` = `<id>.apps.googleusercontent.com`
   - `MISTRAL_API_KEY_1..3`, `GROQ_API_KEY_1..3`
   - `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD` (Gmail **App Password**), `SMTP_FROM`
4. **Create** → first build ~10–15 min (torch/faiss are large).

> **No Blueprint?** New + → **Web Service** → connect repo → **Runtime: Docker** → Region **Singapore** → Instance **Free** → Health Check Path `/healthz` → add the env vars above → Create.

### 3c. Get the URL & verify
Your backend: `https://ai-tutor-api.onrender.com`
```bash
curl https://ai-tutor-api.onrender.com/healthz
```
Watch **Logs** in Render. If you see an **OOM / "Killed"** on boot → that's the 512 MB limit (see the warning at the top).

---

## 4. Frontend — Vercel
1. Edit **`frontend/vercel.json`** → replace `REPLACE_WITH_BACKEND_URL` with your Render host (no `https://`, no trailing slash):
   ```json
   { "source": "/api/:path*", "destination": "https://ai-tutor-api.onrender.com/:path*" }
   ```
   Commit + push.
2. Vercel → **Add New Project** → import the repo.
   - **Project Name:** `ai-tutor` (match `APP_BASE_URL`/`ALLOWED_ORIGINS`).
   - **Root Directory:** `frontend`
   - **Framework:** Vite (auto).
3. **Environment Variables:** `VITE_GOOGLE_CLIENT_ID` = `<id>.apps.googleusercontent.com`.
4. **Deploy** → `https://ai-tutor.vercel.app`.

> The `/api` rewrite makes the browser talk to its **own** origin (Vercel), which proxies to Render — so the httpOnly **refresh cookie stays same-site** and login works. A direct cross-domain call would break the cookie.

---

## 5. Google OAuth
Google Cloud Console → **Credentials** → your OAuth Client → **Authorized JavaScript origins** → add:
```
https://ai-tutor.vercel.app
```
(Keep `http://localhost:5173` for dev.) Save.

---

## 6. Smoke test — open `https://ai-tutor.vercel.app`
- [ ] Loads over HTTPS, no console errors
- [ ] Sign up → verification email → click → log in
- [ ] "Continue with Google" works
- [ ] Open a topic → auto summary card → first question → answer → tutor replies
- [ ] Mobile: nav fits, side panels full-screen, no horizontal scroll

---

## 7. Redeploy later
| Change | Action |
|---|---|
| Backend | `git push` → Render auto-builds (`autoDeploy: true`) |
| Frontend | `git push` → Vercel auto-builds |

---

## 8. Render-specific notes
- **Cold start:** free services **spin down after 15 min idle** → next visitor waits **~50–60 s**. To reduce it, ping `/healthz` every ~10 min with a free **UptimeRobot** monitor (fits within the 750 free instance-hours/month).
- **Memory:** see the warning at the top — 512 MB is the real risk for this app.
- **File uploads (Materials page):** Render's disk is **ephemeral** (wiped on redeploy/restart). For persistent uploads add object storage (Cloudflare R2 free, or Atlas GridFS) later.
- **Rate limiting** is in-memory per instance — fine on one free instance.
- **Secrets:** set only in the Render dashboard; never in `render.yaml` or git.

---

## Env var reference (backend)
**Required:** `MONGODB_URI`, `DB_NAME`, `SECRET_KEY`, `APP_BASE_URL`, `ALLOWED_ORIGINS`, `GOOGLE_CLIENT_ID`, `MISTRAL_API_KEY_1..3`, `GROQ_API_KEY_1..3`, `SMTP_HOST/PORT/USER/PASSWORD/FROM`, `ENVIRONMENT=production`.
**Frontend (Vercel):** `VITE_GOOGLE_CLIENT_ID` only.
