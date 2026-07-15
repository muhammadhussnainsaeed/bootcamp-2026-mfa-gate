# MFA Gate

MFA Gate is a FastAPI authentication service that demonstrates multi-factor login flows with both SMS PINs and TOTP codes. It uses PostgreSQL for persistent user data, Redis for short-lived login state, and Temporal for the MFA watcher and lockout workflow.

## What The Project Does

- Registers users with a generated TOTP secret.
- Starts an SMS PIN challenge when a user logs in.
- Verifies either the SMS PIN or a TOTP code.
- Enforces retry limits, cooldowns, and temporary lockouts.
- Returns a QR code payload for authenticator app enrollment.

## Stack

- FastAPI for the HTTP API.
- SQLModel and asyncpg for PostgreSQL access.
- redis.asyncio for ephemeral MFA state.
- Temporal for escalation and workflow tracking.
- pyotp and qrcode for TOTP and enrollment QR generation.

## Project Layout

- `src/main.py` boots the app, initializes the database, and connects to Temporal.
- `src/api/auth.py` contains the authentication routes.
- `src/services/` contains PIN, TOTP, and auth helpers.
- `src/temporal/` contains the worker, workflows, and activities.
- `tests/` contains the async integration-style test suite with fake Redis and fake Temporal.
- `docs/architecture.md` explains the system design in more detail.

## Requirements

- Python 3.10 or newer.
- PostgreSQL.
- Redis.
- Temporal, running locally on `localhost:7233`.

The repository includes a `docker-compose.yml` for PostgreSQL and Redis, but Temporal still needs to be started separately.

## Local Setup

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If you want PostgreSQL and Redis from Docker:

```bash
docker compose up -d
```

## Environment Variables

The app reads these variables from your environment or `.env` file:

- `DATABASE_URL` for the async PostgreSQL connection string.
- `REDIS_URL` for Redis.
- `UNLOCK_KEY` for the internal unlock endpoint.

## Run Locally

Start Temporal first:

```bash
temporal server start-dev
```

Start the Temporal worker in a second terminal:

```bash
python -m src.temporal.worker
```

Then start the API:

```bash
uvicorn src.main:app --reload
```

The interactive API docs are available at `/docs`.

## API Endpoints

- `POST /auth/register` creates a user and TOTP secret.
- `POST /auth/login` looks up a user, issues a 6-digit PIN, applies cooldown checks, and starts the Temporal watcher.
- `POST /auth/verify` verifies either an SMS PIN or a TOTP code and signals the workflow.
- `GET /auth/qr-code/{username}` returns a Base64-encoded QR image for authenticator setup.
- `POST /auth/unlock/{user_id}` clears lockout, PIN, attempt, and cooldown state using the internal API key.

## Testing

Run the full test suite with:

```bash
pytest
```

The test fixtures replace PostgreSQL, Redis, and Temporal with in-memory fakes, so the suite can run without external services.

## Reference Docs

- [docs/architecture.md](docs/architecture.md) for the system design and flow diagrams.
- [docs/failure-demo.md](docs/failure-demo.md) for a failure-mode walkthrough.
- [docs/ai-review-summary.md](docs/ai-review-summary.md) for the project review notes.