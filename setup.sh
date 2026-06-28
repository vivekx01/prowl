#!/bin/bash
set -e

echo "=== Prowl Setup ==="

# ── Install Docker if not present ─────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "Docker not found — installing..."
    sudo apt update
    sudo apt install -y ca-certificates curl gnupg

    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    echo "Docker installed"
else
    echo "Docker already installed — skipping"
fi

# ── Generate secrets ───────────────────────────────────────────
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)

# ── Prompt for config ─────────────────────────────────────────
read -p "Enter your OpenRouter API key: " OPENROUTER_API_KEY

read -p "Enter admin password [admin123]: " ADMIN_PASSWORD
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}

SERVER_IP=$(hostname -I | awk '{print $1}')
read -p "Enter your server domain or IP [http://${SERVER_IP}]: " PROWL_URL
PROWL_URL=${PROWL_URL:-http://${SERVER_IP}}

# ── Write .env.production ──────────────────────────────────────
cat > .env.production <<EOF
# ── Auth ───────────────────────────────────────────────────────
SECRET_KEY=${SECRET_KEY}
ADMIN_EMAIL=admin@prowl.app
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# ── Database ───────────────────────────────────────────────────
DATABASE_URL=postgresql://prowl:${POSTGRES_PASSWORD}@db:5432/prowl
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# ── Redis ──────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── CORS ───────────────────────────────────────────────────────
ALLOWED_ORIGINS=${PROWL_URL}

# ── LLM ────────────────────────────────────────────────────────
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
FILTER_MODEL=google/gemini-2.5-flash-lite
SCORE_MODEL=google/gemini-2.5-flash
INSIGHTS_MODEL=openai/gpt-4o-mini

# ── Pricing per million tokens (USD) ──────────────────────────
FILTER_MODEL_PRICE_IN=0.15
FILTER_MODEL_PRICE_OUT=0.60
SCORE_MODEL_PRICE_IN=0.09
SCORE_MODEL_PRICE_OUT=0.45
SCORE_MODEL_CACHE_DISCOUNT=1.0

# ── Scraper ────────────────────────────────────────────────────
REQUEST_DELAY=1.5
MAX_JOBS_PER_COMPANY=200
LISTING_RETENTION_DAYS=60

# ── Telegram notifications (optional) ─────────────────────────
NEXUS_NOTIFY_URL=
NEXUS_API_KEY=
PROWL_URL=${PROWL_URL}
EOF

echo ".env.production created"

# ── Start containers ───────────────────────────────────────────
docker compose --env-file .env.production up -d --build

echo ""
echo "=== Done ==="
echo "Prowl is running at ${PROWL_URL}"
echo "Log in with admin@prowl.app and the password you set."
echo ""
echo "To enable Telegram notifications, set NEXUS_NOTIFY_URL and NEXUS_API_KEY in .env.production"
echo "then run: docker compose --env-file .env.production restart api worker"
