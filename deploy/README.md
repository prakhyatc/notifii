# Deployment Guide

Notifii can be deployed to any of these free-tier platforms in under 5 minutes.

## Prerequisites

All deployment options need:
- **Redis** — use [Upstash](https://upstash.com) free tier (10,000 commands/day, no credit card)
- **Email** — set `EMAIL_PROVIDER=console` for demo, or use [Resend](https://resend.com) free tier (3,000 emails/mo) for real delivery

## Fly.io (Recommended)

Free tier: 3 shared-cpu VMs with 256MB RAM each.

```bash
# Install flyctl: https://fly.io/docs/flyctl/install/
fly auth login

# Deploy API
fly launch --config deploy/fly/fly.api.toml --no-deploy
fly secrets set REDIS_URL="rediss://default:xxx@your-upstash-url:6379" -a notifii-api
fly deploy --config deploy/fly/fly.api.toml

# Deploy Worker
fly launch --config deploy/fly/fly.worker.toml --no-deploy
fly secrets set REDIS_URL="rediss://default:xxx@your-upstash-url:6379" -a notifii-worker
fly deploy --config deploy/fly/fly.worker.toml
```

## Render

Free tier: 750 hours/month for web services (spins down after inactivity).

```bash
# Push to GitHub, then in Render dashboard:
# New > Blueprint > Connect your repo > Select render.yaml
```

The `render.yaml` blueprint auto-provisions API, Worker, Dashboard, and Redis.

Or deploy manually:
1. New Web Service > Docker > Set dockerfile to `services/notification-api/Dockerfile`
2. New Background Worker > Docker > Set dockerfile to `services/email-worker/Dockerfile`
3. Add Redis (free plan)
4. Set environment variables

## Koyeb

Free tier: 1 nano instance (runs 24/7, no sleep).

```bash
# Install Koyeb CLI: https://www.koyeb.com/docs/build-and-deploy/cli
koyeb login

# Deploy API
koyeb service create notifii-api \
  --docker "ghcr.io/your-user/notifii-api:latest" \
  --port 8000:http \
  --env QUEUE_BACKEND=redis \
  --env REDIS_URL="your-upstash-url" \
  --env EMAIL_PROVIDER=console \
  --env DEMO_MODE=true \
  --instance-type nano \
  --region was

# Deploy Worker
koyeb service create notifii-worker \
  --docker "ghcr.io/your-user/notifii-worker:latest" \
  --env QUEUE_BACKEND=redis \
  --env REDIS_URL="your-upstash-url" \
  --env EMAIL_PROVIDER=console \
  --instance-type nano \
  --region was
```

Or use the YAML configs in `deploy/koyeb/`.

## Free Redis: Upstash

1. Sign up at [upstash.com](https://upstash.com) (no credit card)
2. Create a Redis database (free tier: 10K commands/day)
3. Copy the `REDIS_URL` (use the TLS endpoint: `rediss://...`)
4. Set it as a secret/env var in your deployment platform

## Free Email: Resend

1. Sign up at [resend.com](https://resend.com) (free tier: 3,000 emails/month)
2. Get your API key
3. Set `EMAIL_PROVIDER=resend` and `RESEND_API_KEY=re_xxx` in your env vars

For demo purposes, `EMAIL_PROVIDER=console` works perfectly — it logs emails to stdout.

## Dashboard

Deploy the dashboard separately as a static site (completely free):

```bash
cd dashboard
npm run build
# Upload dist/ to Vercel, Netlify, or Cloudflare Pages
```

Set `VITE_API_URL` to your deployed API URL before building.

| Platform | Deploy Command |
|---|---|
| Vercel | `npx vercel --prod` |
| Netlify | `npx netlify deploy --prod --dir=dist` |
| Cloudflare Pages | Connect GitHub repo in dashboard |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `REDIS_URL` | Yes | Redis connection string (use Upstash TLS URL) |
| `QUEUE_BACKEND` | No | `redis` (default) or `sqs` |
| `EMAIL_PROVIDER` | No | `console` (default), `smtp`, `resend`, `ses` |
| `IDEMPOTENCY_BACKEND` | No | `redis` (default) or `memory` |
| `DEMO_MODE` | No | `true` for public demo |
| `RESEND_API_KEY` | If using Resend | API key from resend.com |
| `APP_ENV` | No | `dev`, `staging`, `prod` |
| `RATE_LIMIT_PER_MIN` | No | Rate limit in demo mode (default: 60) |

## Cost Summary

| Component | Platform | Cost |
|---|---|---|
| API | Fly.io / Render / Koyeb | $0 |
| Worker | Fly.io / Render / Koyeb | $0 |
| Redis | Upstash | $0 |
| Email | Resend / Console | $0 |
| Dashboard | Vercel / Netlify | $0 |
| **Total** | | **$0/month** |
