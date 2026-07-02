# Failure Mode Demonstrations: State Management & System Resilience

## The Problem Statement
A core requirement of the bootcamp was to demonstrate the failure mode of storing temporary authentication state in memory. If a login script stores a generated PIN inside a local Python dictionary or list, that data is inherently tied to the application's process lifecycle. 

If the server crashes, restarts, or scales horizontally during a user's 5-minute login window, the in-memory data is completely purged. The user's pending verification disappears, causing a failed login state despite a valid PIN attempt.

## The Solution
To build a resilient MFA gateway, temporary state management was decoupled from the application process and offloaded to an external Redis cache. This stateless architectural approach not only protects against process crashes but also enables horizontal scaling and graceful error handling during dependency failures.

Below are the three demonstrations proving the resilience of this architecture.

---

## 1. Process Lifecycle Resilience (Server Restarts)

To verify that the MFA Gate Server survives Uvicorn process restarts, the following steps were demonstrated:

1. **Trigger Login:** A user initiates a login via the `/auth/login` endpoint.
2. **State Creation:** The server generates a 6-digit PIN and stores it in Redis with a 300-second (5-minute) TTL, alongside an attempt counter.
3. **Simulate Crash:** The Uvicorn FastAPI process is manually terminated (`Ctrl+C`) and immediately restarted while the 5-minute window is still active.
4. **Verify Resilience:** The user submits the PIN to the `/auth/verify` endpoint on the newly booted server process.
5. **Outcome:** Authentication succeeds. Because Redis independently tracks the keys and TTL timers, the new FastAPI process successfully retrieves and validates the PIN.

---

## 2. Distributed System Ready (Horizontal Scaling)

Because the architecture is entirely stateless, the API can run multiple copies concurrently behind a load balancer without dropping verification sessions.

1. **Spin Up Multiple Instances:** Two separate Uvicorn instances are started (e.g., Instance A on port `8000` and Instance B on port `8001`).
2. **Trigger Login on Node A:** A user initiates the login request by hitting Instance A. Redis stores the PIN.
3. **Verify PIN on Node B:** Instead of returning to Instance A, the user submits their PIN to the `/auth/verify` endpoint on Instance B.
4. **Outcome:** Authentication succeeds perfectly. This proves the system is not pinned to a single process memory space and is fully prepared for horizontal scaling and load balancing.

---

## 3. Dependency Failure Handling (Redis Outage)

Offloading state to Redis introduces a new dependency. If Redis fails mid-window, the application must handle the outage gracefully rather than crashing or throwing unhandled exceptions.

1. **Trigger Login:** A user initiates a login. The PIN is successfully stored in Redis.
2. **Simulate Dependency Crash:** The Redis Docker container is manually killed mid-window.
3. **Attempt Verification (Failure State):** The user submits the PIN to `/auth/verify`. 
4. **Graceful Handling:** Instead of exposing a raw `500 Internal Server Error`, the API catches the Redis connection failure and returns a friendly `503 Service Unavailable` message (e.g., *"Server is busy right now, please try again later"*). 
5. **Simulate Dependency Recovery:** The Redis container is started back up. 
6. **Verify Resilience:** The user submits the PIN one more time within the original 5-minute TTL. 
7. **Outcome:** Authentication succeeds, proving the API can survive upstream dependency disruptions without corrupting active sessions.