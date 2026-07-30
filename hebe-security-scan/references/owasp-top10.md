# OWASP Top 10 (2021) Mapping

Where each OWASP Top 10 item shows up in this skill's own numbered category system (1 secrets, 2 access control, 3 database rules, 4 authentication, 5 public endpoints, 6 race conditions, 7 input validation, 8 injection, 9 mass assignment, 10 business logic, 11 rate limiting, 12 payments, 13 AI/LLM, 14 mobile, 15 config/headers/CORS, 16 deployment, 17 dependencies).

| OWASP Top 10 | Covered by | Skill categories |
|---|---|---|
| A01 — Broken Access Control | Access control, ownership checks, RLS/security rules, business-logic authorization gaps | 2 (access control), 3 (database rules), 10 (business logic) |
| A02 — Cryptographic Failures | Password hashing (Argon2/bcrypt), secrets storage and rotation | 1 (secrets), 4 (authentication) |
| A03 — Injection | SQL injection, XSS, SSRF, command/template injection | 8 (injection) |
| A04 — Insecure Design | Business-logic gaps (missing counterpart checks, state machines, self-referential fraud), and the upfront security prompt-engineering that prevents them | 10 (business logic) |
| A05 — Security Misconfiguration | Headers, HTTPS/HSTS, CSP, cookie flags, CORS, debug mode, source maps, exposed `.git`, environment separation | 15 (config/headers/CORS), 16 (deployment) |
| A06 — Vulnerable and Outdated Components | Dependency auditing (npm/pip/bundle/go audits), Dependabot/Renovate | 17 (dependencies) |
| A07 — Identification and Authentication Failures | Password hashing, user enumeration, rate limiting on auth, session/token handling | 4 (authentication), 11 (rate limiting) |
| A08 — Software and Data Integrity Failures | Mass assignment, unverified webhook payloads, SAST/CodeQL/Semgrep in CI | 9 (mass assignment), 12 (payments — webhook signature verification), 17 (dependencies) |
| A09 — Security Logging and Monitoring Failures | Sentry/logging in production, alerting on 429/401/500 spikes, suspicious-pattern detection | 16 (deployment), 10 (business logic — fraud detection) |
| A10 — Server-Side Request Forgery (SSRF) | Backend fetching attacker-controlled URLs (image proxies, avatar URLs, webhook targets) | 8 (injection) |

Additional skill categories without a direct 1:1 OWASP Top 10 entry, but which recur constantly in real audits: **5 (public endpoints)** — server actions/route handlers/Convex functions that are public API surface whether or not they look like one; **6 (race conditions)** — concurrent request handling on financial/toggle/unique-constraint operations, closely related to A04 but frequent and specific enough to warrant its own category; **13 (AI/LLM)** — prompt injection, unbounded model-cost abuse, and data exfiltration through AI-facing endpoints; **14 (mobile)** — bundle-exposed env vars, insecure on-device storage, and deep-link trust in React Native/Expo and native apps.
