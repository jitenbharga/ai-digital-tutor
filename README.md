# AI Digital Tutor

An adaptive, AI-powered tutoring system that personalises instruction using reinforcement learning, knowledge tracing, and LLM-generated content. The tutor dynamically selects teaching modes, difficulty levels, and hint strategies based on a per-student model of knowledge, engagement, and frustration.

## Architecture overview

```
┌─────────────┐       ┌────────────────────────────────────┐
│  React +    │  SSE  │  FastAPI backend (serve.py)         │
│  Vite       │◄─────►│                                    │
│  frontend   │  REST │  api/inference.py  — orchestrator   │
└─────────────┘       │  api/session_manager.py — state I/O │
                      └────────┬───────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌─────────────┐   ┌────────────────┐   ┌──────────────┐
   │ Core engines │   │ RL agent       │   │ LLM layer    │
   │              │   │                │   │              │
   │ explainer    │   │ DQN (36 acts)  │   │ registry     │
   │ question_gen │   │ replay buffer  │   │ fallback     │
   │ evaluator    │   │ reward.py      │   │ cache + tele │
   │ socratic     │   │ state_vector   │   │ 4 providers  │
   │ hint         │   └────────────────┘   └──────────────┘
   │ review (FSRS)│
   │ study_planner│
   │ challenge    │
   │ quiz         │
   │ knowledge_gr │
   │ leakage_guard│
   │ retriever    │ ← RAG over /content markdown
   │ KT (BKT+DKT)│
   └─────────────┘
          │
          ▼
   ┌─────────────┐
   │  MongoDB     │
   │  (Motor)     │
   └─────────────┘
```

**Core engines** — Each engine generates LLM prompts for a specific pedagogical task (explanation, Socratic probing, hints, review scheduling, etc.). All engines are async and use versioned prompt templates under `core/prompts/`.

**RL agent** — A DQN with a 36-action space (4 teaching modes × 3 hint levels × 3 difficulty tiers) and a 16-dimensional state vector capturing student traits. Trained offline via `training/train_offline.py` using simulated students, and fine-tuned online during live sessions.

**Knowledge tracing** — Bayesian Knowledge Tracing (BKT) per topic with an optional Deep Knowledge Tracing (DKT) model. Calibrated mastery estimates feed into the DQN state vector and difficulty selection.

**LLM layer** — Provider-agnostic fallback chain (Mistral → Groq → Gemini → HuggingFace). Includes a TTL response cache, per-call telemetry, and a config-driven registry (`configs/default.yaml`).

**RAG retriever** — FAISS vector index over curated markdown notes in `/content`. TF-IDF + SVD embeddings (no API keys needed). Grounding context is injected into explainer and question generator prompts.

**Frontend** — React + Vite + Tailwind CSS SPA with auth, topic selection, chat tutor, quizzes, progress dashboard with a D3 knowledge graph, gamification (XP, streaks, badges), and a guardian dashboard for read-only parental access.

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- MongoDB 6+ (local or Atlas)
- At least one LLM provider API key (Mistral, Groq, Google Gemini, or HuggingFace)

## Setup

### 1. Clone and configure environment

```bash
git clone <repo-url> && cd ai_digital_twin
cp .env.example .env
# Edit .env — fill in MONGODB_URI, SECRET_KEY, and at least one API key
```

### 2. Backend

```bash
cd backend

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt

# Dev/test tools (pytest)
pip install -r requirements-dev.txt
```

### 3. MongoDB

Start a local MongoDB instance (or point `MONGODB_URI` in `.env` to an Atlas cluster):

```bash
mongod --dbpath ./data/db
```

Collections are created automatically on first run.

### 4. Start the backend

```bash
cd backend
uvicorn serve:app --reload --port 8000
```

The API is at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs` (disabled when `ENVIRONMENT=production`).

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173` by default.

### Docker (alternative)

If you prefer containers, a single command brings up the full stack (backend + MongoDB + frontend):

```bash
cp .env.example .env
# Edit .env — fill in SECRET_KEY and at least one LLM API key

docker compose up --build
```

This starts three services: `api` (port 8000), `mongo` (port 27017), and `frontend` (port 3000). The compose file overrides `MONGODB_URI` to point at the containerised MongoDB, mounts `checkpoints/` and `content/` as volumes, and reads remaining env vars from `.env`.

The frontend is served via nginx at `http://localhost:3000` and proxies `/api/*` requests to the backend. To tear down: `docker compose down` (add `-v` to also remove the MongoDB volume).

## Account model

The system has exactly two account types: **student** (default, self-serve) and **guardian** (read-only parental access).

A student signs up normally at `/signup` (default `account_type="student"`). A guardian signs up with `account_type="guardian"`. Guardians have no learning or write abilities — they can only view the progress of children who have explicitly invited them.

The consent-based linking flow works as follows: a student calls `POST /me/guardian-invite` to generate a short-lived invite code (24 h). The guardian redeems it via `POST /guardian/redeem-invite` to gain read-only access to that student. Guardian read endpoints are `GET /guardian/children` and `GET /guardian/child/{id}/overview`.

There are no teacher or admin roles. If upgrading from an older deployment that had `teacher`/`admin` roles, run the migration script:

```bash
# Preview changes (read-only):
python scripts/migrate_roles.py --dry-run

# Execute:
python scripts/migrate_roles.py
```

The migration converts legacy teacher/admin users to students, drops the old `linked_students` field, and creates the `guardian_links` collection with indexes. It is idempotent — re-running is a no-op.

## Age policy and COPPA compliance

The product is available to users aged **13 and above only**. Under-13 users are blocked at onboarding with a clear message ("This product is currently available for users aged 13 and above"). This restriction exists because the amended COPPA rule (effective April 2026) requires verifiable parental consent infrastructure for under-13 users, which is not yet implemented.

**Voice features** (TTS/STT) are gated behind the `voice_enabled` feature flag (default `false`) because voiceprints are classified as protected biometric data under amended COPPA. The voice toggles are hidden from the Settings UI when the flag is off. To enable voice for an adult-only deployment, set `VOICE_ENABLED=true` in the environment or `features.voice_enabled: true` in `configs/default.yaml`.

## Feature flags

All deferred/experimental features are controlled via `configs/default.yaml` under the `features:` key. Each flag can also be overridden by an environment variable of the same name (uppercase). Defaults are all `false`:

| Flag | Controls | Why off |
|---|---|---|
| `rl_enabled` | DQN action selection (vs. simple mastery rule) | Unvalidated on real users |
| `gamification_enabled` | XP, levels, badges, streaks, daily goals | Retention feature for unproven product |
| `quests_enabled` | Daily quests from weak areas | Same |
| `guardian_enabled` | Guardian/parental read-only access | Same |
| `certificates_enabled` | Mastery certificates + PDF export | Same |
| `dkt_enabled` | Deep Knowledge Tracing in hot path | Needs thousands of interactions; BKT suffices |
| `voice_enabled` | TTS/STT in frontend | COPPA biometric risk for minors |

## Training

### Offline RL training (simulated students)

```bash
python training/train_offline.py --config configs/default.yaml --episodes 5000
```

Checkpoints are saved to `checkpoints/`. The production server loads the latest checkpoint on startup.

### DKT model training

```bash
python training/train_dkt.py --data data/interactions.csv --epochs 50
```

Requires an interaction log (exported via `scripts/export_pykt.py`).

### Policy evaluation

```bash
python training/eval_policies.py --checkpoint checkpoints/dqn_model.pt --learners 200 --seed 42
python training/eval_policies.py --output-json eval_results.json --output-markdown eval_table.md
```

Compares the trained DQN against baseline policies (Random, FixedLadder, MasteryThreshold). The `--output-json` flag saves results for the production startup gate (see below), and `--output-markdown` generates a pasteable table.

**Latest evaluation results** (regenerate after retraining):

| Policy | Knowledge Gain | Mean Reward | Frustration | Engagement | Mastery % | Q-to-Mastery |
|--------|---------------|-------------|-------------|------------|-----------|-------------|
| Random | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |
| FixedLadder | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |
| MasteryThreshold | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |
| DQN | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ | _pending_ |

> Run `python training/eval_policies.py --output-markdown -` to regenerate this table after training. The production server gates DQN serving on the DQN beating all non-random baselines in both mean reward and knowledge gain (see `eval_results.json`).

### DKT retraining

The DKT (Deep Knowledge Tracing) model should be retrained periodically as new student interactions accumulate. A recommended cron schedule:

```bash
# Retrain DKT weekly (Sunday 3 AM) — add to crontab
0 3 * * 0 cd /path/to/ai_digital_twin && python training/train_dkt.py --epochs 50 --checkpoint checkpoints/dkt_model.pt
```

The DKT checkpoint includes a `trained_at` ISO timestamp. Staleness is exposed via `GET /health` → `capabilities.kt_model_age_days`. If the model is older than 14 days, the health endpoint flags it as stale.

### A/B experiment: RL vs simple rule (Phase 4)

The DQN must earn its way back by beating the simple mastery rule on real users. An A/B experiment framework (`core/ab_experiment.py`) handles this:

**How it works:** Every user is hash-assigned to an arm (control = mastery_rule, treatment = DQN). Assignment is deterministic and stable. Per-answer metrics (accuracy, frustration, mastery, response time) are tracked in MongoDB per arm.

**Running the experiment:**

```bash
# The experiment auto-creates at startup (rl_vs_rule_v1).
# Monitor live results via API:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/experiments/rl_vs_rule_v1/results

# Check your arm:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me/experiment

# Offline analysis with statistical tests:
python scripts/analyze_ab.py --experiment rl_vs_rule_v1

# Conclude when sample size reached:
python scripts/analyze_ab.py --experiment rl_vs_rule_v1 --conclude
```

**Pre-registered win conditions:** Treatment must beat control on normalized learning gain by Cohen's d ≥ 0.1 at p < 0.05 (Mann-Whitney U). If it doesn't, delete the DQN and keep the simple rule.

### Phase 5: Delight features with retention measurement

Each engagement feature is gated behind a feature flag AND an A/B experiment. Users in the "treatment" arm get the feature; "control" does not. Primary metric: day-7 retention.

**Features under experiment:**
- **Gamification** (gamification_v1): XP, levels, badges, streaks, daily goals
- **Leaderboard** (leaderboard_v1): Weekly opt-in cohort leaderboard with anonymized names
- **Certificates** (certificates_v1): Mastery certificates with PDF export

**New modules:**
- `core/retention_tracker.py` — Per-user day-1/day-7 retention measurement
- `core/reminder_engine.py` — Streak-at-risk, daily goal, welcome-back reminders
- `core/leaderboard.py` — Weekly XP leaderboard with opt-in + anonymization

**New endpoints:**
- `GET /me/leaderboard` — This week's top 20 + your rank
- `PUT /me/leaderboard/opt-in` — Opt in/out of leaderboard
- `GET /me/reminders` — Pending unread reminders
- `POST /me/reminders/read-all` — Mark all reminders read
- `GET /me/reminder-prefs` / `PUT /me/reminder-prefs` — Reminder preferences
- `GET /me/retention` — Your retention data
- `GET /retention-summary` — Aggregate retention metrics (admin)

**Rule:** Any feature that doesn't lift day-7 retention by Cohen's d ≥ 0.1 at p < 0.05 gets dropped.

## Tests

```bash
pytest tests/ -v
```

Key test classes cover: utility functions, LLM infrastructure, prompt templates, DQN agent, async engines (mocked LLM), API schemas, FSRS scheduling, leakage guard, and reward source integrity.

## Project structure

```
ai_digital_twin/
├── serve.py                 # FastAPI app entry point
├── database.py              # MongoDB connection (Motor async)
├── auth.py / security.py    # JWT auth + password hashing
├── api/
│   ├── inference.py         # Main orchestrator (decide, learn, submit_answer)
│   ├── session_manager.py   # Student state persistence
│   └── schemas.py           # Pydantic request/response models
├── core/
│   ├── adaptive_explainer.py, question_generator.py, ...  # Pedagogical engines
│   ├── knowledge_tracing/   # BKT + DKT implementations
│   ├── prompts/             # Versioned prompt templates (one per engine)
│   ├── retriever.py         # RAG: FAISS vector index over /content
│   ├── leakage_guard.py     # Answer-extraction / prompt-injection detector
│   ├── reward.py            # Canonical RL reward function
│   ├── llm_registry.py      # Provider fallback chain
│   ├── llm_cache.py         # TTL response cache
│   └── llm_telemetry.py     # Per-call logging to MongoDB
├── models/
│   ├── dqn.py               # DQN network + agent
│   ├── replay_buffer.py     # MongoDB-backed experience replay
│   └── student.py           # Student + Concept data model
├── training/
│   ├── train_offline.py     # Offline RL trainer (simulated students)
│   ├── train_dkt.py         # DKT model trainer
│   ├── simulator.py         # SimStudent for offline training
│   ├── baselines.py         # Baseline policies for comparison
│   └── eval_policies.py     # Multi-policy evaluation harness
├── utils/                   # Shared helpers (state_vector, tone, metrics)
├── configs/default.yaml     # RL + LLM hyperparameters
├── content/                 # Curated markdown notes for RAG grounding
├── scripts/                 # Migration & data export utilities
├── tests/                   # pytest suite
├── frontend/                # React + Vite + Tailwind SPA
├── requirements.txt         # Pinned runtime dependencies
├── requirements-dev.txt     # Test/dev dependencies
└── .env.example             # Environment variable template
```

## Configuration

Runtime behaviour is controlled by two mechanisms:

- **Environment variables** (`.env`) — secrets, connection strings, and deployment-specific settings. See `.env.example` for the full list.
- **`configs/default.yaml`** — RL hyperparameters, LLM settings (temperature, cache TTL), and offline training config. Passed to training scripts via `--config`.

## License

Private — not yet licensed for distribution.
