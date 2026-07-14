# System Architecture: MFA Gate Server

## Overview

The MFA Gate Server is an asynchronous backend service for multi-factor authentication. The current design combines SMS PIN verification, TOTP verification, Redis-backed ephemeral state, and a Temporal workflow that tracks escalation and account lockout conditions.

## Core Technology Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| Framework | FastAPI | Async REST API and dependency injection. |
| Database | PostgreSQL (SQLModel + asyncpg) | Stores users and permanent TOTP secrets. |
| Cache & State | Redis (redis.asyncio) | Stores PINs, retry counters, cooldowns, and lock flags. |
| Workflow Engine | Temporal | Tracks MFA verification state and escalation lifecycle. |
| Cryptography | pyotp | Generates and validates TOTP codes. |

## Endpoint Reference

| Method | Path | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| POST | `/auth/register` | No | Create a new user and generate a TOTP secret. |
| POST | `/auth/login` | No | Look up the user, store a 6-digit PIN in Redis, apply cooldown checks, and start the Temporal watcher. |
| POST | `/auth/verify` | No | Verify an SMS PIN or TOTP code and signal the Temporal workflow. |
| GET | `/auth/qr-code/{username}` | No | Return a Base64 QR code image for authenticator enrollment. |
| POST | `/auth/unlock/{user_id}` | Yes, internal API key | Clear lockout, PIN, and cooldown state for a user. |

## Authentication Flow Diagram

### POST /auth/register

```mermaid
flowchart TD
    R1[Client sends username + phone] --> R2[FastAPI generates TOTP secret via pyotp]
    R2 --> R3[(PostgreSQL - save user + totp_secret)]
    R3 --> R4[Return 201 + user_id]
```

### POST /auth/login

```mermaid
flowchart TD
    L1[Client sends username] --> L2[(PostgreSQL - lookup user by username)]
    L2 --> L3{User found?}
    L3 -- No --> L4[404 Not Found]
    L3 -- Yes --> L5{Locked or cooling down?}
    L5 -- Locked --> L6[403 Locked account]
    L5 -- Cooling down --> L7[429 Too many requests]
    L5 -- No --> L8[(Redis - store PIN + attempts, TTL 300s)]
    L8 --> L9[(Redis - set cooldown key, TTL 60s)]
    L9 --> L10[Temporal - start MFA watcher]
    L10 --> L11[Return user_id]
```

### POST /auth/verify - SMS

```mermaid
flowchart TD
    S1[Client sends user_id + PIN] --> S2[(Redis - GET pin and attempts)]
    S2 --> S3{PIN exists?}
    S3 -- No --> S4[400 PIN expired or never requested]
    S3 -- Yes --> S5[(Redis - INCR attempts)]
    S5 --> S6{Attempts > 3?}
    S6 -- Yes --> S7[400 Max attempts reached]
    S6 -- No --> S8{PIN matches?}
    S8 -- No --> S9[400 Invalid PIN]
    S8 -- Yes --> S10[(Redis - delete PIN + attempts)]
    S10 --> S11[Temporal - signal verified]
    S11 --> S12[200 Success]
```

### POST /auth/verify - TOTP

```mermaid
flowchart TD
    T1[Client sends user_id + TOTP code] --> T2[(PostgreSQL - fetch totp_secret)]
    T2 --> T3{pyotp validates code?}
    T3 -- No --> T4[400 Invalid TOTP code]
    T3 -- Yes --> T5[Temporal - signal verified]
    T5 --> T6[200 Success]
```

### GET /auth/qr-code/{username}

```mermaid
flowchart TD
    Q1[Client requests QR code] --> Q2[(PostgreSQL - fetch totp_secret)]
    Q2 --> Q3[Build otpauth:// URI]
    Q3 --> Q4[Encode as Base64 PNG]
    Q4 --> Q5[Return qr_image to client]
```

## Data Storage Model

### PostgreSQL - persistent identity data

Stores everything that must survive a server restart.

| Field | Type | Notes |
| :--- | :--- | :--- |
| `id` | integer (PK) | Stable identifier for user state and workflow correlation. |
| `username` | string (unique) | Login handle. |
| `phone_number` | string (unique) | Destination for SMS-based MFA. |
| `totp_secret` | string | Base32 secret generated at registration. |

### Redis - ephemeral auth state

All keys are scoped to `user_id` and carry a TTL.

| Key pattern | Value | TTL | Purpose |
| :--- | :--- | :--- | :--- |
| `pin:{user_id}` | 6-digit PIN string | 300s | Active SMS PIN for the login attempt. |
| `attempts:{user_id}` | integer string | 300s | Failed PIN counter with lockout at more than 3 attempts. |
| `cooldown:{user_id}` | marker value | 60s | Prevents repeated PIN requests during the SMS cooldown window. |
| `locked:{user_id}` | lock reason | 600s | Marks an account as temporarily locked after escalation. |

## Key Design Decisions

### Asynchronous I/O

The service uses `async`/`await` throughout. PostgreSQL and Redis access stay non-blocking, so API traffic does not stall the ASGI event loop.

### Separation of state by lifetime

| | SMS (stateful) | TOTP (stateless) |
| :--- | :--- | :--- |
| Storage | Redis (ephemeral) | PostgreSQL (permanent secret) |
| Expiry | 5-minute PIN TTL plus 60-second cooldown | 30-second moving time window |
| Verification | String comparison against stored PIN | `pyotp.TOTP.verify()` |
| Cleanup needed? | Yes, on success or unlock | No temporary state stored |

### Security behaviours worth noting

- PIN generation uses a cryptographically secure random 6-digit value.
- PIN writes and attempt resets are performed atomically in a Redis pipeline.
- Login requests are rate-limited by a cooldown key to reduce repeated SMS requests.
- A Temporal workflow tracks verification progress and supports escalation and lockout handling.
- The unlock endpoint is protected by an internal API key dependency.

### Infrastructure-agnostic testing

The Pytest suite overrides PostgreSQL, Redis, and Temporal dependencies with in-memory fakes. This keeps the auth flow testable without requiring external services during CI.
