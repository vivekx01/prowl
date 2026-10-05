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
                        ├── PostgreSQL :5432  (bundled container, or your existing server)
                        └── Redis :6379       (bundled container, or your existing server)
                               ↑
                        Celery workers + beat
```

By default the setup script starts PostgreSQL and Redis as containers alongside the app. If you already run PostgreSQL and Redis on this machine or elsewhere, you can point Prowl at them instead and skip those containers. Section 3 explains both options.

---

## Prerequisites

A server running Ubuntu 22.04 or 24.04 with:
- At least 1 GB RAM (2 GB recommended)
- Git installed (`sudo apt install git`)
- Ports 80 open in the firewall

If you use existing PostgreSQL and Redis servers, they must be reachable from this server, and the PostgreSQL database and user must already exist.

---

## Quick Start (setup script)

The setup script installs Docker if needed, generates secrets, asks a few questions, and starts everything:

```bash
git clone https://github.com/vivekx01/prowl.git
cd prowl
chmod +x setup.sh
./setup.sh
```

It asks for:
1. **Where PostgreSQL and Redis come from** — containers created by Prowl (option 1), or servers you already run (option 2). See section 3.
2. **OpenRouter API key** and **admin password**.

It then writes `.env.production` and starts the stack. The sections below cover the same steps by hand, plus the commands for day-to-day use.

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

Run `./setup.sh` to generate `.env.production` for you. To write it by hand, copy the template and fill in the values for your database mode:

```bash
cp .env.example .env.production
nano .env.production
```

Every deployment needs:

```env
OPENROUTER_API_KEY=sk-or-v1-...        # your OpenRouter key
SECRET_KEY=                            # any long random string (openssl rand -hex 32)
ADMIN_EMAIL=admin@prowl.app
ADMIN_PASSWORD=                        # initial admin password
PROWL_URL=http://<your-server-ip>
```

Then pick one database mode.

### Option 1 — Bundled containers (Prowl creates PostgreSQL and Redis)

Set a database password and use the in-network hostnames:

```env
POSTGRES_PASSWORD=CHANGE_ME            # pick a strong password
DATABASE_URL=postgresql://prowl:CHANGE_ME@db:5432/prowl   # same password here
REDIS_URL=redis://redis:6379/0
```

Start with the bundled override file (see section 4).

### Option 2 — Existing PostgreSQL and Redis

Point Prowl at your servers. Create an empty database for Prowl first; tables are created automatically on first start.

```env
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
REDIS_URL=redis://<host>:6379/0
```

If PostgreSQL or Redis runs directly on this server (not in another container), use `host.docker.internal` as the host. The containers are configured to resolve it to the host machine:

```env
DATABASE_URL=postgresql://prowl:<password>@host.docker.internal:5432/prowl
REDIS_URL=redis://host.docker.internal:6379/0
```

Make sure PostgreSQL accepts connections from the Docker network (for example, by listening on that interface and allowing the Docker subnet in `pg_hba.conf`). Otherwise the API and workers will fail to start.

Start with the base compose file only (section 4).

Everything else in the file is pre-configured with sensible defaults.

---

## 4. Build and Start

Pick the command that matches the database mode you chose in section 3.

**Option 1 — bundled containers:**

```bash
docker compose -f docker-compose.yaml -f docker-compose.bundled.yaml --env-file .env.production up -d --build
```

This will:
1. Pull the Postgres 16 and Redis 7 images
2. Build the Python backend image
3. Build the React frontend and bundle it into an Nginx image
4. Start the app, worker, beat, database and Redis containers

**Option 2 — existing PostgreSQL and Redis:**

```bash
docker compose --env-file .env.production up -d --build
```

This will:
1. Build the Python backend image
2. Build the React frontend and bundle it into an Nginx image
3. Start the app, worker, beat and Nginx containers

The `coolify` network is declared in the compose file. If it doesn't exist on your server, create it once with `docker network create coolify`. The setup script does this for you.

First build takes 3–5 minutes. Subsequent builds are faster due to layer caching.

**Check everything is running:**

```bash
docker compose ps
```

With bundled containers you should see these services `running` (`db` and `redis` report `healthy`):

```
NAME                    STATUS
prowl-db-1              running (healthy)
prowl-redis-1           running (healthy)
prowl-api-1             running
prowl-worker-scrape-1   running
prowl-worker-score-1    running
prowl-beat-1            running
prowl-nginx-1           running
```

With existing servers, the `db` and `redis` containers are absent.

Open `http://<your-server-ip>` in a browser. The login page should appear.

> **Note:** `nginx` exposes port 80 inside the Docker network but does not publish it to the host. If you're not running behind Coolify or another reverse proxy, you need to publish the port yourself (for example, add `ports: ["80:80"]` to the `nginx` service) before the URL above will load.

---

## 5. First Login

The first user to register is automatically given admin access. Go to:

```
http://<your-server-ip>
```

Register an account — this becomes your admin account. Don't share the registration link before doing this.

The admin account created by the setup script (`admin@prowl.app`) is seeded at startup. Use the admin page to create other users.

---

## Common Commands

These commands assume you are in the project directory. For bundled mode, add `-f docker-compose.yaml -f docker-compose.bundled.yaml` after `docker compose`, as in section 4. The examples below use the existing-servers form.

**View logs for a specific service:**
```bash
docker compose logs -f api              # FastAPI
docker compose logs -f worker-scrape    # Celery worker: scrape queue
docker compose logs -f worker-score     # Celery worker: score queue
docker compose logs -f beat             # Celery beat scheduler
docker compose logs -f nginx            # Nginx
```

**Restart a single service:**
```bash
docker compose restart api
```

**Stop everything:**
```bash
docker compose down
```

**Stop and wipe bundled database and Redis data (destructive):**
```bash
docker compose -f docker-compose.yaml -f docker-compose.bundled.yaml down -v
```

**Open a Postgres shell (bundled mode only):**
```bash
docker compose -f docker-compose.yaml -f docker-compose.bundled.yaml exec db psql -U prowl -d prowl
```

With existing servers, connect with your normal PostgreSQL client using the credentials in `DATABASE_URL`.

---

## Updating to a New Version

```bash
# Pull latest code
git pull

# Rebuild and restart (bundled mode: add the -f flags from section 4)
docker compose --env-file .env.production up -d --build
```

Docker Compose only rebuilds the containers whose source changed and restarts them. Bundled Postgres and Redis data is kept in named volumes (`pgdata`, `redisdata`) and survives updates.

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
Usually a missing or wrong env var. Check `.env.production`, especially `DATABASE_URL` (and `POSTGRES_PASSWORD` in bundled mode, which must match the password in `DATABASE_URL`).

**"could not translate host name" / "Connection refused" on startup (existing servers):**

The host in `DATABASE_URL` or `REDIS_URL` isn't reachable from the containers. Check that:
- You used `host.docker.internal` (not `localhost`) for a server on this machine.
- PostgreSQL and Redis listen on an address the Docker network can reach.
- Firewall rules allow the connection.

**Database connection refused on startup (bundled containers):**

The app containers wait for Postgres and Redis to pass their healthchecks before starting. If Postgres is slow to initialise on the first run, `docker compose ps` may show a restart or two. This is normal.

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
