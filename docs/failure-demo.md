# Failure Mode Demonstration: Server Restarts

## The Problem Statement
A core requirement of the bootcamp was to demonstrate the failure mode of storing temporary authentication state in memory. If a login script stores a generated PIN inside a local Python dictionary or list, that data is inherently tied to the application's process lifecycle. 

If the server crashes, restarts, or scales horizontally during a user's 5-minute login window, the in-memory data is completely purged. The user's pending verification disappears, causing a failed login state despite a valid PIN attempt.

## The Solution
To build a resilient MFA gateway, temporary state management was decoupled from the application process and offloaded to an external Redis cache.

## Steps to Reproduce the Failure & Verification

To verify that the MFA Gate Server survives process restarts, the following steps were demonstrated:

1. **Trigger Login:** A user initiates a login via the `/auth/login` endpoint.
2. **State Creation:** The server generates a 6-digit PIN and stores it in Redis with a 300-second (5-minute) TTL, alongside an attempt counter.
3. **Simulate Crash:** The Uvicorn FastAPI process is manually terminated (`Ctrl+C`) and immediately restarted while the 5-minute window is still active.
4. **Verify Resilience:** The user submits the PIN to the `/auth/verify` endpoint on the newly booted server process.
5. **Outcome:** Authentication succeeds. Because Redis independently tracks the keys and TTL timers, the new FastAPI process successfully retrieves and validates the PIN, proving that active login sessions survive application crashes.