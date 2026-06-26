# Dev Environment & Git Setup Guide
## Finance Monitoring AI System

---

## 1. First-Time Setup (every team member does this once)

```bash
# Clone the repo
git clone https://github.com/Migspajela23/Finance-Monitoring-AI-System.git
cd Finance-Monitoring-AI-System

# Run the automated setup script
bash scripts/dev-setup.sh
```

The script installs:
- Python venv + backend deps
- Node modules for frontend
- Git hooks (commit linter + branch protection)
- Local Postgres via Docker (optional)

---

## 2. Branch Strategy

```
main          ← production (protected, no direct push)
  └─ develop  ← integration/staging (protected, no direct push)
       ├─ feat/review-queue-ui
       ├─ feat/duplicate-detection
       ├─ fix/upload-hash-collision
       └─ hotfix/...  (→ PR into main, then backmerge to develop)
```

### Daily workflow

```bash
# Start new work
git checkout develop
git pull origin develop
git checkout -b feat/your-feature-name

# ... do work ...

git add .
git commit -m "feat(review-queue): add hard duplicate confirmation modal"
git push origin feat/your-feature-name

# Open PR → develop on GitHub
```

### Commit message format (enforced by git hook)

```
<type>(<scope>): <short description>

Types: feat  fix  chore  docs  style  refactor  perf  test  ci  hotfix
```

Examples:
```
feat(review-queue): implement approval state machine
fix(duplicate-detector): handle null merchant name
chore(deps): upgrade supabase-js to 2.43.0
docs(api): add review queue endpoint examples
```

---

## 3. GitHub Secrets to Add

Go to: **Settings → Secrets and variables → Actions → New repository secret**

Add each of these (get values from team lead / your own accounts):

| Secret name | Where to get it |
|---|---|
| `SUPABASE_ACCESS_TOKEN` | supabase.com → Account → Access Tokens |
| `SUPABASE_DB_PASSWORD` | Supabase project → Settings → Database |
| `SUPABASE_PROJECT_ID` | Supabase project → Settings → General |
| `SUPABASE_URL` | Supabase project → Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase project → Settings → API (service_role) |
| `GEMINI_API_KEY` | Google AI Studio → API Keys |
| `RENDER_API_KEY` | render.com → Account → API Keys |
| `RENDER_SERVICE_ID` | Render service → Settings → Service ID |
| `VERCEL_TOKEN` | vercel.com → Settings → Tokens |
| `VERCEL_ORG_ID` | Vercel → Settings → General → Team ID |
| `VERCEL_PROJECT_ID` | Vercel project → Settings → General |
| `SNYK_TOKEN` | snyk.io → Account Settings → API Token |
| `SENTRY_DSN` | sentry.io → Project → Settings → Client Keys |
| `LOGTAIL_TOKEN` | betterstack.com → Logs → Source → Token |
| `SLACK_WEBHOOK_URL` | Slack → Apps → Incoming Webhooks |

---

## 4. Local Dev Commands

```bash
# Backend (terminal 1)
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm run dev          # starts on http://localhost:3000

# Local DB (if using Docker)
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f postgres

# Run backend tests
cd backend && pytest -q

# Run frontend tests
cd frontend && npm test
```

---

## 5. Monitoring Setup

After first deploy, set up these free-tier monitors:

| Tool | What it monitors | Setup |
|---|---|---|
| **UptimeRobot** | FastAPI `/health` endpoint every 5 min → Slack alert | uptimerobot.com → New Monitor → HTTPS |
| **Sentry** | Next.js frontend JS errors | Already wired via `SENTRY_DSN` |
| **Logtail** | FastAPI structured logs + AI API failures | Already wired via `LOGTAIL_TOKEN` |
| **Supabase Dashboard** | DB query performance, slow queries | Supabase → Database → Performance |

**Logtail alert rule to create** (catches AI failures):
- Field: `alert` = `true`  
- Action: Send Slack notification to `#dev-alerts`

---

## 6. Database: Running Migrations

```bash
# Against local Docker Postgres
psql -h localhost -U postgres -d finance_dev \
  -f supabase/migrations/001_review_queue_and_duplicates.sql

# Against Supabase cloud (CI does this automatically on deploy to main)
supabase link --project-ref <your-project-id>
supabase db push

# Check migration status
supabase migration list
```

**Rule:** Never edit an existing migration file. Always create a new numbered file:
```
supabase/migrations/002_add_categories_table.sql
supabase/migrations/003_add_user_settings.sql
```
