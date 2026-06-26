#!/usr/bin/env bash
# scripts/dev-setup.sh
# One-command local dev environment setup for Finance Monitoring AI System.
# Run from repo root: bash scripts/dev-setup.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[setup]${NC} $1"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $1"; }
error()   { echo -e "${RED}[error]${NC} $1"; exit 1; }

info "Starting Finance Monitor local dev setup..."

# ── 1. Check required tools ───────────────────────────────────────────────────
info "Checking prerequisites..."

command -v node   >/dev/null 2>&1 || error "Node.js not found. Install v20+ from https://nodejs.org"
command -v python3 >/dev/null 2>&1 || error "Python 3 not found. Install v3.11+ from https://python.org"
command -v git    >/dev/null 2>&1 || error "Git not found."
command -v docker >/dev/null 2>&1 || warn  "Docker not found. Local Postgres won't start automatically."

NODE_VER=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
PY_VER=$(python3 -c "import sys; print(sys.version_info.minor)")

[ "$NODE_VER" -ge 20 ] || error "Node.js v20+ required (found v${NODE_VER})."
[ "$PY_VER"   -ge 11 ] || error "Python 3.11+ required."

info "Node $(node -v), Python $(python3 --version) — OK"

# ── 2. Git config: branch protection reminder ─────────────────────────────────
info "Configuring git hooks..."
mkdir -p .git/hooks

cat > .git/hooks/pre-push << 'HOOK'
#!/usr/bin/env bash
# Block direct pushes to main or develop
branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$branch" == "main" || "$branch" == "develop" ]]; then
  echo "Direct push to '$branch' is not allowed."
  echo "Please create a feature branch: git checkout -b feat/<name>"
  exit 1
fi
HOOK
chmod +x .git/hooks/pre-push
info "Pre-push hook installed (blocks direct push to main/develop)."

cat > .git/hooks/commit-msg << 'HOOK'
#!/usr/bin/env bash
# Enforce conventional commit format
commit_msg=$(cat "$1")
pattern='^(feat|fix|chore|docs|style|refactor|perf|test|ci|hotfix)(\(.+\))?: .{1,72}$'
if ! echo "$commit_msg" | grep -qE "$pattern"; then
  echo "Commit message format: <type>(<scope>): <description>"
  echo "Types: feat fix chore docs style refactor perf test ci hotfix"
  echo "Example: feat(review-queue): add duplicate detection modal"
  exit 1
fi
HOOK
chmod +x .git/hooks/commit-msg
info "Commit message linter installed."

# ── 3. Backend Python setup ───────────────────────────────────────────────────
info "Setting up Python backend..."
cd backend

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  info "Virtual environment created."
fi

source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -r requirements-dev.txt -q
info "Backend Python dependencies installed."

# Copy .env if not exists
if [ ! -f ".env" ]; then
  cp .env.example .env
  warn "backend/.env created from example. Fill in your secrets."
fi

cd ..

# ── 4. Frontend Node setup ────────────────────────────────────────────────────
info "Setting up Next.js frontend..."
cd frontend

npm ci --silent
info "Frontend dependencies installed."

if [ ! -f ".env.local" ]; then
  cp .env.example .env.local
  warn "frontend/.env.local created from example. Fill in your secrets."
fi

cd ..

# ── 5. Local Postgres via Docker (optional) ───────────────────────────────────
if command -v docker >/dev/null 2>&1; then
  info "Starting local PostgreSQL via Docker..."
  docker compose -f docker-compose.dev.yml up -d postgres
  info "Waiting for Postgres to be ready..."
  sleep 4

  # Run migrations against local DB
  if [ -f "supabase/migrations/001_review_queue_and_duplicates.sql" ]; then
    export $(grep -v '^#' backend/.env | xargs) 2>/dev/null || true
    PGPASSWORD=${LOCAL_DB_PASSWORD:-postgres} psql \
      -h localhost -p 5432 \
      -U ${LOCAL_DB_USER:-postgres} \
      -d ${LOCAL_DB_NAME:-finance_dev} \
      -f supabase/migrations/001_review_queue_and_duplicates.sql \
      && info "Migration applied to local DB." \
      || warn "Migration failed — check Postgres connection."
  fi
else
  warn "Docker not found — skipping local Postgres. Use Supabase cloud for dev DB."
fi

# ── 6. Supabase CLI check ─────────────────────────────────────────────────────
if ! command -v supabase >/dev/null 2>&1; then
  warn "Supabase CLI not found. Install: https://supabase.com/docs/guides/cli"
else
  info "Supabase CLI found: $(supabase --version)"
fi

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Dev environment ready!                         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Start backend:   cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "  Start frontend:  cd frontend && npm run dev"
echo "  DB UI:           http://localhost:54323  (if using Supabase local)"
echo ""
warn "Don't forget to fill in .env, backend/.env, and frontend/.env.local"
