#!/bin/bash
set -e

echo "=== Prowl Setup ==="

# ── Guard: don't clobber an existing install ───────────────────
if [ -f .env.production ]; then
    echo ""
    echo "WARNING: .env.production already exists."
    echo "Re-running setup will regenerate secrets and break your existing database."
    read -p "Continue anyway? [y/N]: " CONFIRM
    case "$CONFIRM" in
        [yY][eE][sS]|[yY]) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi

# ── Install Docker if not present ─────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "Docker not found — installing..."

    if ! command -v apt-get &> /dev/null; then
        echo "ERROR: This script only supports Ubuntu/Debian. Install Docker manually and re-run."
        exit 1
    fi

    sudo apt-get update -qq
    sudo apt-get install -y -qq ca-certificates curl gnupg

    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    echo "Docker installed."
else
    echo "Docker already installed — skipping."
fi

# ── Generate secrets ───────────────────────────────────────────
SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)

# ── Prompt for config ─────────────────────────────────────────
while [ -z "$OPENROUTER_API_KEY" ]; do
    read -p "Enter your OpenRouter API key: " OPENROUTER_API_KEY
    if [ -z "$OPENROUTER_API_KEY" ]; then
        echo "API key cannot be empty."
    fi
done

read -p "Enter admin password [admin123]: " ADMIN_PASSWORD
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
PROWL_URL="http://${SERVER_IP:-localhost}"

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
ALLOWED_ORIGINS=*

# ── LLM ────────────────────────────────────────────────────────
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
FILTER_MODEL=openai/gpt-4o-mini
SCORE_MODEL=nvidia/nemotron-3-super-120b-a12b
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
LISTING_RETENTION_DAYS=15

# ── Telegram notifications (optional) ─────────────────────────
NEXUS_NOTIFY_URL=
NEXUS_API_KEY=
PROWL_URL=${PROWL_URL}
EOF

echo ".env.production created."

# ── Start containers ───────────────────────────────────────────
docker compose --env-file .env.production up -d --build

echo ""
echo "=== Done ==="
echo "Prowl is running at ${PROWL_URL}"
echo "Log in with admin@prowl.app and the password you set."
echo ""
echo "To enable Telegram notifications:"
echo "  1. Create a simple webhook API (any language/platform) that accepts POST requests"
echo "     from Prowl and forwards them to Telegram using the Telegram Bot API."
echo "  2. Prowl will POST to your endpoint with header 'X-Api-Key' and a JSON body"
echo "     containing the matched jobs, count, chat_id, and a link back to Prowl."
echo "  3. Set NEXUS_NOTIFY_URL (your webhook URL) and NEXUS_API_KEY (a secret you choose)"
echo "     in .env.production, then run:"
echo "     docker compose --env-file .env.production restart api worker"
echo "  4. Set your Telegram chat ID in Prowl's Settings page."
