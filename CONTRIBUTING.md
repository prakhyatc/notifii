# Contributing to Notifii

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/your-user/notifii.git
cd notifii

# Option 1: Docker (recommended)
docker-compose up --build

# Option 2: Local Python
python -m venv .venv
source .venv/bin/activate
pip install -r services/notification-api/requirements.txt
pip install pytest httpx ruff black
```

## Running Tests

```bash
# Unit tests (no Docker needed)
make test

# Docker-based integration tests
make test-docker
```

## Code Style

- Python: formatted with [Black](https://github.com/psf/black), linted with [Ruff](https://github.com/astral-sh/ruff)
- Run `make format` before committing
- Run `make lint` to check

## Project Structure

```
services/
  shared/           # Abstraction layers (queue, email, idempotency, observability)
  notification-api/ # FastAPI ingress plane
  email-worker/     # Queue consumer + delivery plane
dashboard/          # React + Vite admin UI
deploy/             # Deployment configs (Fly.io, Railway, Render)
docs/               # Architecture diagrams
scripts/            # Demo and utility scripts
```

## Adding a New Queue Backend

1. Create `services/shared/queue/your_adapter.py`
2. Implement the `QueueAdapter` ABC from `base.py`
3. Register it in `factory.py`
4. Add tests

## Adding a New Email Provider

1. Create `services/shared/email/your_adapter.py`
2. Implement the `EmailAdapter` ABC from `base.py`
3. Register it in `factory.py`
4. Add tests

## Pull Request Process

1. Fork and create a feature branch
2. Make your changes with tests
3. Run `make lint` and `make test`
4. Open a PR with a clear description
5. Ensure CI passes

## Commit Messages

Use conventional commits:
- `feat: add webhook delivery channel`
- `fix: handle redis connection timeout`
- `docs: update deployment guide`
- `test: add idempotency edge cases`
- `refactor: extract queue retry logic`
