# Deployment Guide

This guide covers deploying The Prowl on a single Ubuntu server — tested on Ubuntu 22.04/24.04. The same steps work on a local VM and on a DigitalOcean droplet.

## Architecture

```
Browser
  │
  ▼
Nginx :80
  ├── /          → serves React static files (built into the image)
  └── /api/      → proxies to FastAPI :8000
                        │
                        ├── PostgreSQL :5432  (persistent volume)
                        └── Redis :6379  ←── Celery Worker
```

All five services run as Docker containers managed by Docker Compose.

---

## Prerequisites

A server running Ubuntu 22.04 or 24.04 with:
- At least 1 GB RAM (2 GB recommended)
- Git installed (`sudo apt install git`)
- Ports 80 open in the firewall

---

## 1. Install Docker

```bash
# Remove any old Docker packages
sudo apt remove docker docker-engine docker.io containerd runc 2>/dev/null

# Install dependencies
sudo apt update
sudo apt install -y ca-certificates curl gnupg

# Add Docker's GPG key and repo
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine and Compose plugin
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow running Docker without sudo (log out and back in after this)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/vivekx01/prowl.git
cd prowl
```

---

## 3. Configure Environment

Copy the production env template and fill in your secrets:

```bash
cp .env.production .env.production
nano .env.production
```

The three required fields are:

```env
OPENROUTER_API_KEY=sk-or-v1-...        # your OpenRouter key
SECRET_KEY=                             # any long random string
POSTGRES_PASSWORD=CHANGE_ME            # pick a strong password
DATABASE_URL=postgresql://prowl:CHANGE_ME@db:5432/prowl  # same password here
```

Everything else in the file is pre-configured with sensible defaults.

**Generate a secure SECRET_KEY:**

```bash
openssl rand -hex 32
```

---

## 4. Build and Start

```bash
docker compose --env-file .env.production up -d --build
```

This will:
1. Pull Postgres 16 and Redis 7 images
2. Build the Python backend image
3. Build the React frontend and bundle it into an Nginx image
4. Start all five containers

First build takes 3–5 minutes. Subsequent builds are faster due to layer caching.

**Check everything is running:**

```bash
docker compose ps
```

You should see all five services with status `running` or `healthy`:

```
NAME             STATUS
prowl-db-1       running (healthy)
prowl-redis-1    running
prowl-api-1      running
prowl-worker-1   running
prowl-nginx-1    running
```

Open `http://<your-server-ip>` in a browser. The login page should appear.

---

## 5. First Login

The first user to register is automatically given admin access. Go to:

```
http://<your-server-ip>
```

Register an account — this becomes your admin account. Don't share the registration link before doing this.

---

## Common Commands

**View logs for a specific service:**
```bash
docker compose logs -f api       # FastAPI
docker compose logs -f worker    # Celery worker
docker compose logs -f nginx     # Nginx
```

**Restart a single service:**
```bash
docker compose restart api
```

**Stop everything:**
```bash
docker compose down
```

**Stop and wipe the database (destructive):**
```bash
docker compose down -v
```

**Open a Postgres shell:**
```bash
docker compose exec db psql -U prowl -d prowl
```

---

## Updating to a New Version

```bash
# Pull latest code
git pull

# Rebuild and restart (zero-downtime for the DB and Redis)
docker compose --env-file .env.production up -d --build
```

Docker Compose will only rebuild the containers whose source changed and restart them. The Postgres volume is preserved.

---

## Troubleshooting

**Port 80 already in use:**
```bash
sudo lsof -i :80
# Stop whatever is using it (commonly Apache or another Nginx)
sudo systemctl stop apache2
sudo systemctl stop nginx
```

**API container keeps restarting:**
```bash
docker compose logs api
```
Usually a missing or wrong env var — double-check `.env.production`, especially `DATABASE_URL` and `POSTGRES_PASSWORD` match.

**Database connection refused on startup:**

The API waits for Postgres to pass its healthcheck before starting. If Postgres is slow to initialise (first run), the API may restart once before succeeding. This is normal — Docker Compose will retry automatically.

**Frontend shows blank page or 404 on refresh:**

If Nginx is running but the page is blank, check the frontend build:
```bash
docker compose logs nginx
```
A failed `npm run build` during the image build will produce an empty dist. Rebuild with:
```bash
docker compose build nginx
docker compose up -d nginx
```

---

## Adding a Domain (Later)

When you have a domain pointed at your server's IP:

1. Install Certbot:
```bash
sudo apt install certbot python3-certbot-nginx
```

2. Update `ALLOWED_ORIGINS` in `.env.production`:
```env
ALLOWED_ORIGINS=https://yourdomain.com
```

3. Update `frontend/nginx.conf` to add your domain to `server_name` and add an SSL server block. Then rebuild the nginx image:
```bash
docker compose build nginx
docker compose up -d nginx
```

4. Run Certbot to get a certificate and auto-patch the Nginx config:
```bash
sudo certbot --nginx -d yourdomain.com
```
