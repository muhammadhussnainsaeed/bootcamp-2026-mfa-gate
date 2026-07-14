# MFA Gate

MFA Gate is a FastAPI-based authentication service that demonstrates two-factor login flows with both SMS PINs and TOTP codes. The current architecture uses PostgreSQL for user records and permanent TOTP secrets, Redis for short-lived login state, and Temporal for MFA escalation and account lockout workflows.

## What It Does

- Registers users with a generated TOTP secret.
- Starts an SMS PIN challenge on login.
- Verifies either an SMS PIN or a TOTP code.
- Enforces cooldowns, retry limits, and account lockouts.
- Exposes a QR code endpoint for authenticator app enrollment.

## Architecture

The implementation is documented in [docs/architecture.md](docs/architecture.md). In short:

- FastAPI serves the HTTP API.
- PostgreSQL stores user profiles and TOTP secrets.
- Redis stores login PINs, retry counters, cooldown timers, and lock flags.
- Temporal tracks MFA verification state and supports escalation workflows.

## Setup

Prerequisites: Python 3.10+ and Docker if you want to run the supporting services locally.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Optional Docker startup:

```bash
docker-compose up --build
```

## Run

Start the API locally with Uvicorn:

```bash
uvicorn src.main:app --reload
```

The API will be available with the interactive docs at `/docs`.

## API Surface

- `POST /auth/register` creates a user and TOTP secret.
- `POST /auth/login` issues an SMS PIN and starts MFA tracking.
- `POST /auth/verify` checks either an SMS PIN or a TOTP code.
- `GET /auth/qr-code/{username}` returns a base64 QR code for authenticator setup.
- `POST /auth/unlock/{user_id}` clears lockout state using the internal API key.