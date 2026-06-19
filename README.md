**Project Overview**
- **Name:**: MFA Gate (Bootcamp project) — a small Python service demonstrating multi-factor authentication (TOTP) and auth plumbing.
- **Purpose:**: Provide an example authentication service with TOTP support, Redis session/cache integration, and simple user modeling for educational use.

**Setup Instructions**
- **Prerequisites:**: Python 3.10+, pip, and Docker (optional).
- **Install dependencies:**: Install into a virtual environment and install requirements.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r [requirements.txt](requirements.txt)
```
- **Optional (Docker):**: The repository includes a Docker Compose file; to start services via Docker:

```bash
docker-compose up --build
```

**How to Run the Application**
- **Direct (development):**: Run the app with Uvicorn (auto-reload for development).

```bash
uvicorn src.main:app --reload
```
- **Containerized:**: Use the `docker-compose.yml` file to bring up the app and any required services.

**Architecture / Design Decisions**
- **Package layout:**: `api/` contains route and auth handlers; `core/` holds infrastructure integrations (`database.py`, `redis.py`); `models/` and `schemas/` define data shapes; `services/` contain business logic like `auth_service.py` and `totp_service.py`.
- **Separation of concerns:**: Authentication logic is split between HTTP handlers (`api/`) and application services (`services/`) to make unit testing easier.
- **State and caching:**: Redis is used for ephemeral state (sessions, rate-limiting, or TOTP challenge tracking) to keep the design scalable.
- **Simplicity for teaching:**: The code favors clarity and small, focused modules over heavy abstraction to make it approachable for bootcamp learners.

**Assumptions Made During Implementation**
- **Entry point:**: `src/main.py` is the application's primary entrypoint and will start any HTTP server or CLI used by the project.
- **Environment variables:**: Database and Redis connection details are provided via environment variables (not hard-coded). If running locally without Docker, ensure those services are reachable or mocked for tests.
- **Python version:**: The project targets Python 3.10+ features (type hints, modern stdlib conveniences).
- **Testing:**: Tests live in the `tests/` folder and assume a test-friendly configuration; see `tests/pytest_configuration.py` for test setup.

---

If you want, I can also:
- add a short `Contributing` section,
- include example environment variable names and sample `.env` file,
- or run the test suite and report results.
