# Failure Mode Demonstrations: State Management, Temporal, & System Resilience

## The Problem Statement
A core requirement of the bootcamp was to demonstrate the failure mode of storing temporary authentication state in memory. If a login script stores a generated PIN inside a local Python dictionary or list, that data is inherently tied to the application's process lifecycle. 

If the server crashes, restarts, or scales horizontally during a user's 5-minute login window, the in-memory data is completely purged. The user's pending verification disappears, causing a failed login state despite a valid PIN attempt.

## The Solution
To build a resilient MFA gateway, temporary state management was decoupled from the application process and offloaded to an external Redis cache. The MFA escalation lifecycle is also tracked through Temporal, so authentication can survive process restarts while still handling workflow start and signal failures in a controlled way.

Below are the demonstrations proving the resilience of this architecture.

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

---

## 4. Workflow Failure Handling (Temporal Outage)

The login and verification flow also depends on Temporal for MFA escalation tracking. If the workflow engine is unavailable, the application should fail safely rather than leaving partial auth state behind.

1. **Trigger Login:** A user initiates a login and the server generates a PIN in Redis.
2. **Simulate Temporal Failure:** The Temporal service or worker becomes unavailable before the workflow can start.
3. **Login Safeguard:** The `/auth/login` endpoint aborts the flow, deletes `pin:{user_id}`, `attempts:{user_id}`, and `cooldown:{user_id}`, and returns `503 Service Unavailable`.
4. **Outcome:** No partial MFA session is left behind, so the user can retry cleanly once Temporal is restored.

Temporal can also fail later during verification signal delivery:

1. **Trigger Verify:** The user submits a valid SMS PIN or TOTP code.
2. **Simulate Signal Failure:** The workflow handle cannot be signaled because Temporal is unavailable.
3. **Graceful Handling:** The API accepts the authentication attempt but returns a warning payload indicating cleanup could not be confirmed.
4. **Outcome:** Authentication is not lost, and the workflow state can be reconciled once Temporal recovers.