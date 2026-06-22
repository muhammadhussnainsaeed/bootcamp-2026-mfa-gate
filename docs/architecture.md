# System Architecture: MFA Gate Server

## Overview
The MFA Gate Server is an asynchronous backend service designed to orchestrate Multi-Factor Authentication. It implements two distinct security models: a stateful SMS-based PIN verification system and a stateless Time-Based One-Time Password (TOTP) system.

## Core Technology Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Framework** | FastAPI | Provides a high-performance, asynchronous REST API infrastructure. |
| **Database** | PostgreSQL (SQLModel + asyncpg) | Acts as the persistent storage layer for user accounts and permanent TOTP Base32 secrets. |
| **Cache & State** | Redis (redis.asyncio) | Manages transient state for SMS PINs, handling 5-minute TTL expirations and atomic lockout counters. |
| **Cryptography** | pyotp | Generates and validates HMAC-SHA1 time-based tokens for the Authenticator app flow. |

## Key Design Decisions

* **Asynchronous I/O:** The entire application stack utilizes `async`/`await`. By using `asyncpg` for PostgreSQL and `redis.asyncio` for Redis, the server ensures that database queries and cache lookups never block the ASGI event loop.
* **Separation of State:** 
  * *Stateful (SMS):* PINs must exist for exactly 5 minutes. This state is offloaded to Redis rather than in-memory Python structures to guarantee process resilience.
  * *Stateless (TOTP):* Authenticator codes require no temporary storage. The server mathematically verifies the token using the permanent user secret and the current epoch time, avoiding unnecessary database writes.
* **Infrastructure-Agnostic Testing:** The Pytest suite utilizes FastAPI's dependency injection to swap the production PostgreSQL and Redis clients with `aiosqlite` and `fakeredis`. This allows the CI/CD pipeline to execute hundreds of isolated tests in milliseconds without Docker container overhead.