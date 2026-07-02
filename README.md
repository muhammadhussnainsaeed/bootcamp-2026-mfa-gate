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
pip install -r requirements.txt
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