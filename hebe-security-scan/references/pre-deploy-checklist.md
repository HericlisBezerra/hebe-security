# Pre-Deploy Security Checklist

Paste this into the project's `README.md` or `SECURITY.md`. Run through every box before shipping to production.

## Secrets

- [ ] `.env` files are listed in `.gitignore`
- [ ] No secret is grep-able in the source (`gitleaks detect`)
- [ ] `gitleaks detect` has been run against the full repo, including git history, not just the working tree
- [ ] `.env.example` is committed with variable **names** only, no real values
- [ ] Any secret that has ever leaked has been **rotated** (not just removed — old commits and reflog still hold it)

## Authentication

- [ ] Using an established solution (Supabase Auth / Clerk / Auth0 / Better-Auth / etc.) — no custom hashing
- [ ] Argon2id (or bcrypt cost ≥ 12) if a custom hash implementation exists at all
- [ ] Rate limiting on login / password reset / signup
- [ ] Identical responses for both valid and invalid identifiers on login and reset (no user enumeration)
- [ ] JWTs have a refresh + revocation mechanism, or the session is stateful

## Authorization

- [ ] Every authenticated route validates ownership of the resource being accessed, not just that a valid token was presented
- [ ] RLS is enabled (Supabase) — verified by testing with the **anon** key, not `service_role`
- [ ] Non-owned resources return **404**, not 403 (don't reveal existence)
- [ ] Mass assignment is blocked (explicit allowlist of fields per endpoint)

## Input

- [ ] Zod/Valibot (or equivalent) schema on every endpoint
- [ ] Max length enforced on every string field
- [ ] Uploads validated by MIME type + magic bytes + max size + extension allowlist
- [ ] Accepted URLs are restricted to a domain allowlist + max length (including query string)

## Race conditions

- [ ] Financial/critical operations wrapped in transactions with proper locking
- [ ] Database constraints as a final safety net (e.g. `balance >= 0`)
- [ ] Manually tested with 10 parallel requests against each critical operation

## Security headers

- [ ] HTTPS enforced everywhere (HSTS set)
- [ ] Content-Security-Policy configured, starting restrictive
- [ ] `X-Frame-Options: DENY`
- [ ] `X-Content-Type-Options: nosniff`
- [ ] `Referrer-Policy` set (e.g. `strict-origin-when-cross-origin`)
- [ ] `Permissions-Policy` set, denying unused capabilities (camera/microphone/geolocation)
- [ ] Cookies set with `HttpOnly` + `Secure` + `SameSite`

## CORS

- [ ] `Access-Control-Allow-Origin` is never `*` on an authenticated endpoint
- [ ] Only the project's own domains are whitelisted
- [ ] `Access-Control-Allow-Credentials: true` is paired only with specific origins, never a wildcard or reflected `Origin` header

## Deployment

- [ ] Debug mode / verbose logging is disabled in production
- [ ] Source maps are not deployed to production
- [ ] `https://yourdomain.com/.git/HEAD` returns 404, not repo content
- [ ] Preview/staging environments use test/staging keys, never production credentials
- [ ] Error pages return generic messages, no stack traces, no internal paths

## Tests

- [ ] A security regression test suite runs in CI (see `regression-tests.md`)
- [ ] IDOR / mass assignment / rate limiting / race conditions are all covered by tests
- [ ] Semgrep (or equivalent SAST) runs on every PR
- [ ] Dependencies have no critical CVEs (`npm audit` / `pip-audit` / `bundle audit` / `govulncheck` / `composer audit`)

## Monitoring

- [ ] Sentry (or equivalent) capturing production errors
- [ ] Alerts configured for spikes in 429 / 401 / 500 responses
- [ ] Suspicious-pattern detection in place (e.g. one IP generating unusually high volume)
