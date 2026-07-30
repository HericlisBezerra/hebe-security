# Authentication & Session

## Password hashing

### How the attacker exploits it
If the database ever leaks (breach, backup exposure, insider), password hashes are the last line of defense. With a weak hash algorithm, offline cracking turns leaked hashes into plaintext passwords in minutes:
- **SHA/MD5 (even salted):** GPU-crackable at billions of hashes/second. Never acceptable.
- **bcrypt with a low cost factor:** fast enough that large-scale cracking is still practical.

### Where to look in the code
- `grep` for `md5`, `sha1`, `sha256` (used directly on passwords), `bcrypt`, `argon2` in auth/user modules.
- Check the bcrypt cost factor / rounds parameter if bcrypt is used.
- Custom auth implementations (home-grown, not a maintained library) — these almost always have a subtle flaw: session fixation, timing leaks, predictable token generation.

### How to reproduce
Inspect the hash format stored in the `users` table (`$2b$` = bcrypt, `$argon2id$` = Argon2id, a bare 32/40-hex-char string = MD5/SHA1 = broken). If you control a test account, change its password and diff the stored hash format against known algorithm signatures.

### Fix
- Argon2id — current OWASP recommendation, default choice for new projects.
- bcrypt — acceptable, but cost factor must be **≥ 12**.
- scrypt — acceptable.
- SHA/MD5 (even salted) — never, under any circumstance.
- **Do not build authentication from scratch** if an established solution exists for the stack (Supabase Auth, Clerk, Better-Auth, Auth0, Firebase Auth). Custom auth only with a strong, explicit justification — a well-maintained library has a team dedicated to patching exactly this class of bug.

---

## User enumeration

### How the attacker exploits it
If `POST /login` or `POST /reset-password` responds differently for "email doesn't exist" vs. "wrong password" vs. "account locked" vs. "not verified" — via message text, status code, or response timing — an attacker builds a list of valid accounts to target with credential stuffing or phishing. Timing side-channels count too: a slower response when the email exists (because a hash comparison ran) leaks the same information even with identical error text.

### Where to look in the code
- Login and password-reset handlers: compare the exact strings/status codes returned for each failure branch (no such user / wrong password / locked / unverified).
- Password comparison done with `==` on strings, or any early-return before a hash comparison runs (creates a timing gap between "user not found" and "wrong password").
- Reset-password endpoint explicitly stating "no account with this email" instead of a neutral response.

### How to reproduce
Call the login/reset endpoint once with a known-valid email and once with a random nonexistent one. Diff the response body, status code, and rough latency. Any difference is an enumeration vector.

### Fix
- **Identical responses** for "email not found", "wrong password", "account locked", "not verified." Always a generic 401 + constant-time handling.
- Password reset: never say "no account with that email" — always "if an account exists, we've sent an email."
- Ensure the hash comparison (or an equivalent-cost dummy operation) runs on the "user not found" path too, so timing doesn't leak existence.

---

## Rate limiting on login/reset/signup

### How the attacker exploits it
Without a rate limit, an attacker throws thousands of password guesses, resets, or signups at the endpoint — brute force, credential stuffing, mass account creation for abuse.

### Where to look in the code
- Absence of rate-limiting middleware on `/login`, `/reset-password`, `/signup`.
- Rate limiting that only exists at a global level (not per-endpoint, not stricter for auth-sensitive routes).

### How to reproduce
```bash
seq 20 | xargs -P20 -I{} curl -s -X POST https://app/api/login \
  -d '{"email":"victim@example.com","password":"guess{}"}'
```
If all 20 attempts are processed without any lockout/429, there is no rate limit.

### Fix
- Login: 5 attempts / 15 min / IP, plus 10 / email.
- Password reset: 3 / hour / email.
- Signup: 3 / hour / IP.
- Cost-sensitive endpoints (upload, search): their own specific limits.
- Tools: Upstash Ratelimit (edge/serverless), express-rate-limit + Redis, Cloudflare Rate Limiting Rules.

---

## Token handling: JWT verification

### How the attacker exploits it
- **`jwt.decode()` without `jwt.verify()`:** `decode` reads the payload without checking the signature. An attacker can forge any payload — including an elevated-role claim — and the app trusts it blindly.
- **`"alg":"none"`:** some JWT libraries accept unsigned tokens when the algorithm field is set to `none`. If verification doesn't explicitly reject this, an attacker submits an unsigned token with any payload they want.
- **Missing issuer/audience/expiration checks:** a token signed for a different service, or expired, is still accepted if only the signature is checked.
- **No revocation:** a stolen JWT stays valid until it expires naturally — there's no logout that actually invalidates it.

### Where to look in the code
- `grep` for a decode call used on its own (not paired with a verify call).
- The `algorithms` option passed to the verify function — is it an explicit allowlist, or missing?
- Whether `issuer`, `audience`, `expiresIn` are validated on decode, not just checked for presence.
- Whether there's any blacklist/revocation mechanism, or whether logout is purely client-side (just deletes the local token).

### How to reproduce
Take a valid JWT, decode its payload (base64), modify a claim (e.g. elevate the role), and either strip the signature and set `alg: none`, or leave the original signature. Submit the tampered token. If the app accepts it, verification is broken.

### Fix
```typescript
// BAD: reads token without verifying signature
const payload = jwt.decode(token);

// GOOD: verifies signature, rejects tampered tokens
const payload = jwt.verify(token, secret, {
  algorithms: ['HS256'],
  issuer: 'your-app',
});
```
- **Use `jwt.verify()`, never `jwt.decode()` alone.**
- **Explicitly reject `"alg": "none"`** by passing an explicit `algorithms` allowlist to `verify()`.
- **Validate issuer, audience, and expiration** — not just the signature.
- JWT: short-lived access token (15 min) + rotating refresh token + a real revocation/logout endpoint. Refresh token only in an `HttpOnly` cookie.

---

## Next.js middleware is not enough

### How the attacker exploits it
Next.js middleware runs at the edge and is convenient for auth checks, but it is **not a reliable sole auth layer**. CVE-2025-29927 demonstrated that middleware could be completely bypassed via a spoofed `x-middleware-subrequest` header — an attacker sends that header and skips the middleware auth check entirely, hitting the underlying route unauthenticated.

### Where to look in the code
- Any app where the *only* auth check lives in `middleware.ts`, with Server Actions, route handlers (`app/api/`), and data-access functions all assuming "middleware already checked this."

### How to reproduce
Send a request to a middleware-protected route with a crafted `x-middleware-subrequest` header (per CVE-2025-29927) and see if the auth check is bypassed. More generally: call the Server Action or route handler directly (bypassing the page/middleware path) and see if it still enforces auth on its own.

### Fix
Always verify auth again in:
- Server Actions
- Route Handlers (`app/api/`)
- Data access functions / database queries

Middleware should be a convenience/UX layer (e.g., redirecting logged-out users), never the only wall between an attacker and the data.

---

## Cookie vs. localStorage storage

### How the attacker exploits it
Tokens stored in `localStorage` are readable by any JavaScript running on the page. A single XSS vulnerability anywhere on the site — a stray unsanitized HTML-render path, an unsanitized comment field — lets the attacker's injected script read `localStorage` and exfiltrate every token on the page.

### Where to look in the code
- `localStorage.setItem('token', ...)` / `localStorage.getItem('token')` anywhere in the client code.
- Auth token or refresh token passed to the client for manual storage instead of being set as a cookie by the server.

### How to reproduce
If any XSS vector exists elsewhere in the app (see input-validation / injection references), demonstrate that `document.cookie` returns nothing for the auth cookie (proving `HttpOnly` is working) versus `localStorage.getItem('token')` returning the raw token (proving it is exposed).

### Fix
- Store tokens in `HttpOnly + Secure + SameSite=Lax` (or `Strict` if no cross-site embedding is needed) cookies, **not localStorage**.
- `HttpOnly` cookies are invisible to JavaScript and sent automatically by the browser — an XSS payload cannot read them.
- Guard the refresh token the same way: only in a cookie, never in localStorage or a JS-readable place.
