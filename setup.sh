#!/bin/bash
set -e

echo "=== Prowl Setup ==="

# ── Generate secrets ───────────────────────────────────────────
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)

# ── Prompt for OpenRouter API key ─────────────────────────────
read -p "Enter your OpenRouter API key: " OPENROUTER_API_KEY

# ── Write .env.production ──────────────────────────────────────
cat > .env.production <<EOF
# ── Secrets ────────────────────────────────────────────────────
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
SECRET_KEY=${SECRET_KEY}

DATABASE_URL=postgresql://prowl:${POSTGRES_PASSWORD}@db:5432/prowl
REDIS_URL=redis://redis:6379/0
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

ALLOWED_ORIGINS=*

# ── LLM ────────────────────────────────────────────────────────
FILTER_MODEL=nvidia/llama-3.1-nemotron-70b-instruct
SCORE_MODEL=nvidia/llama-3.1-nemotron-70b-instruct
FILTER_MODEL_PRICE_IN=0.12
FILTER_MODEL_PRICE_OUT=0.30
SCORE_MODEL_PRICE_IN=0.12
SCORE_MODEL_PRICE_OUT=0.30
SCORE_MODEL_CACHE_DISCOUNT=1.0

# ── Scraper ────────────────────────────────────────────────────
REQUEST_DELAY=1.5
MAX_JOBS_PER_COMPANY=200
EOF

echo ".env.production created"

# ── Start containers ───────────────────────────────────────────
docker compose --env-file .env.production up -d --build

echo ""
echo "=== Done ==="
echo "Prowl is running at http://$(hostname -I | awk '{print $1}')"
echo "Register your account — the first user gets admin access."
