# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Notifii, please report it responsibly.

**Do NOT open a public issue.**

Instead, email: **security@notifii.dev** (or open a private security advisory on GitHub).

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Security Practices

### Secrets Management
- All secrets are loaded from environment variables, never hardcoded
- `.env` files are in `.gitignore` and never committed
- `.env.example` contains only placeholder values

### Authentication
- In production mode, API authentication should be added via middleware
- Demo mode (`DEMO_MODE=true`) is rate-limited to prevent abuse
- Internal simulation endpoints are isolated under `/internal/` prefix

### Container Security
- Docker images use non-root `app` user
- Multi-stage builds minimize attack surface
- Base images are pinned to `python:3.11-slim`
- No unnecessary system packages installed

### Dependencies
- Dependencies are pinned to specific versions
- Regular audits recommended via `pip-audit` and `npm audit`

### Network
- CORS is configured (restrict `allow_origins` in production)
- Health endpoints don't leak sensitive information
- Error responses use generic messages (no stack traces)

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x     | Yes       |
| 1.x     | No        |
