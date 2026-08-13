# 🟢 Deploy Guide — Oracle Cloud Always-Free ARM VM (all-in-one)

Everything runs on **one always-free ARM VM**: FastAPI + MongoDB + the React SPA, fronted by **Caddy** (automatic free HTTPS). Single origin → **no CORS/cookie issues**. Always-on → **zero cold start**. Cost → **$0**.

```
Internet ──HTTPS──▶ Caddy (:443)  ─ /api/* ─▶ api  (FastAPI :8000)
                      │                          │
                      └─ everything else ─▶ SPA  └─▶ mongo (internal)
                         (frontend/dist)
        all three containers on ONE Oracle ARM VM (2 OCPU / 12 GB)
```

Files already added to your repo: **`docker-compose.yml`**, **`Caddyfile`** (and the `Dockerfile` is already Cloud-Run/ARM-ready). You mostly run commands on the VM.

---

## 0. What you need
- Oracle Cloud account (credit/debit card for verification — **Always Free never charges**).
- A domain that points to the VM. Easiest free option: **DuckDNS** (`something.duckdns.org`). HTTPS needs a domain (Google Sign-In + secure cookies won't work on a bare IP).

---

## 1. Create the Always-Free ARM VM

1. Oracle Cloud → **Compute → Instances → Create Instance**.
2. **Image:** Canonical **Ubuntu 22.04**.
3. **Shape:** Change shape → **Ampere (ARM)** → **VM.Standard.A1.Flex** → **2 OCPU / 12 GB** (the free allowance).
4. **Region:** pick **Mumbai** or **Hyderabad** (India latency).
5. **SSH keys:** upload your public key (or let it generate one — download the private key).
6. Create. If you see **"Out of host capacity"** — Ampere free capacity is often full. Retry after a while, try another Availability Domain, or a different region.
7. **Reserve a static public IP** (so it survives restarts): Instance → attached VNIC → IP address → **edit ephemeral → reserved**. Note the **public IP**.

---

## 2. Open ports 80 + 443 (two places — both required)

**a) Oracle firewall (VCN Security List):**
Networking → Virtual Cloud Network → your VCN → **Security Lists → Default** → **Add Ingress Rules**:
- Source `0.0.0.0/0`, IP Protocol **TCP**, Destination port **80**
- Source `0.0.0.0/0`, IP Protocol **TCP**, Destination port **443**

**b) The VM's own iptables** (Ubuntu Oracle images block everything except SSH). SSH in, then:
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

---

## 3. Point your domain to the VM (DuckDNS)

1. https://www.duckdns.org → sign in (GitHub/Google) → create a subdomain, e.g. `ai-tutor`.
2. Set its IP to your VM's **public IP** → Update. Now `ai-tutor.duckdns.org` → your VM.

---

## 4. SSH in and install Docker + Node + Git

```bash
ssh -i /path/to/private.key ubuntu@<VM_PUBLIC_IP>

# Docker (includes Compose v2)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
sudo systemctl enable docker
# log out & back in so the docker group applies:
exit
ssh -i /path/to/private.key ubuntu@<VM_PUBLIC_IP>

# Node 20 (to build the frontend) + git
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs git
```

---

## 5. Get the code

```bash
git clone https://github.com/<you>/ai-digital-tutor.git
cd ai-digital-tutor
```

---

## 6. Backend secrets → `.env` (root, never commit)

Generate a JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Create `.env`:
```bash
nano .env
```
```env
ENVIRONMENT=production
# Mongo runs inside compose — use the service name, not localhost:
MONGODB_URI=mongodb://mongo:27017
DB_NAME=ai_tutor
SECRET_KEY=<paste the 48-char secret>
APP_BASE_URL=https://ai-tutor.duckdns.org
ALLOWED_ORIGINS=https://ai-tutor.duckdns.org
GOOGLE_CLIENT_ID=<your-id>.apps.googleusercontent.com
MISTRAL_API_KEY_1=...
MISTRAL_API_KEY_2=...
MISTRAL_API_KEY_3=...
GROQ_API_KEY_1=...
GROQ_API_KEY_2=...
GROQ_API_KEY_3=...
```
```bash
echo ".env" >> .gitignore
```

---

## 7. Build the frontend

The Google Client ID is baked in at build time:
```bash
cd frontend
npm ci
echo "VITE_GOOGLE_CLIENT_ID=<your-id>.apps.googleusercontent.com" > .env.production
npm run build            # outputs frontend/dist  (Caddy serves this)
cd ..
```

---

## 8. Set your domain in the Caddyfile

```bash
nano Caddyfile
```
Change the first line from `your-subdomain.duckdns.org` to **`ai-tutor.duckdns.org`**. Save.

---

## 9. Launch 🎉

```bash
docker compose up -d --build
```
- First build takes ~10–20 min on ARM (torch/faiss compile/download).
- Caddy auto-fetches the HTTPS cert within ~30 s (needs ports 80/443 open + DNS pointing correctly).

Check:
```bash
docker compose ps
docker compose logs -f api      # watch backend startup
```

Open **https://ai-tutor.duckdns.org** 🚀

---

## 10. Google OAuth

Google Cloud Console → APIs & Services → Credentials → your OAuth Client → **Authorized JavaScript origins** → add:
```
https://ai-tutor.duckdns.org
```
(Keep `http://localhost:5173` for local dev.) Save.

---

## 11. Smoke test
- [ ] Site loads over HTTPS (padlock), no console errors
- [ ] Sign up → verify email → log in
- [ ] "Continue with Google" works
- [ ] Open a topic → auto summary card → first question → answer gets a reply (LLM ok)
- [ ] Mobile: nav fits, side panels full-screen, no horizontal scroll

---

## 12. Maintenance

| Task | Command |
|---|---|
| Update backend | `git pull && docker compose up -d --build` |
| Update frontend | `cd frontend && npm run build && cd .. && docker compose restart caddy` |
| Logs | `docker compose logs -f api` |
| Restart all | `docker compose restart` |
| Stop / start | `docker compose down` / `docker compose up -d` |
| Mongo backup | `docker compose exec mongo mongodump --archive=/data/db/backup.gz --gzip` |

Containers auto-restart on reboot (`restart: unless-stopped` + Docker enabled on boot).

---

## 13. Caveats — read once

- **ARM (aarch64) wheels:** `torch` has ARM CPU wheels; **`faiss-cpu` sometimes lacks a prebuilt ARM wheel**. If `docker compose up --build` fails on faiss, tell me — options are: pin a faiss version that ships aarch64 wheels, install faiss via conda-forge, or gate the vector-search feature off. Everything else installs fine on ARM.
- **Oracle capacity / reclaim:** the A1 free shape is often "out of capacity" (just retry / other AD). Oracle also **reclaims idle** Always-Free compute — an always-on web server counts as active, so you're fine; optionally upgrade the account to **Pay-As-You-Go** (still $0 within Always-Free limits) to avoid reclaim entirely.
- **Free ARM allowance halved (June 2026):** now 2 OCPU / 12 GB per tenancy — enough for this whole stack.
- **Security hardening (recommended):**
  - Mongo is internal-only (not port-mapped) — good. For extra safety add a Mongo user/password and put it in `MONGODB_URI`.
  - `sudo apt install -y unattended-upgrades` for auto security patches.
  - SSH: keys only (disable password auth), keep port 22 restricted if possible.
- **This is a single VM** (no auto-scaling/HA). Perfect for a project/portfolio/real early users; scale later if traffic grows.

---

### Oracle vs Cloud Run (quick reminder)
| | Oracle VM (this guide) | Cloud Run (`DEPLOY.md`) |
|---|---|---|
| Cold start | **None (always on)** | ~10–15 s after idle |
| Perf | Best (dedicated 2 OCPU/12 GB) | Good |
| Setup effort | Higher (VM, DNS, firewall) | Lower (one command) |
| DB | Self-hosted Mongo (same box) | MongoDB Atlas |
| File uploads | **Persistent** (VM disk) | Ephemeral (needs R2/GridFS) |
