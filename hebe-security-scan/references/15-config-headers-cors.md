# Config, Headers, Transport & CORS

Security misconfiguration is one of the most common findings in real audits precisely because it's invisible in normal use — the app works fine for every legitimate user while leaving the door open for an attacker. This category covers everything that sits *around* the application logic: how traffic is transported, what the browser is told to trust, and who is allowed to call the API from where.

## Transport: HTTPS + HSTS

### How the attacker exploits it
Without enforced HTTPS, an attacker positioned on the network path (public Wi-Fi, compromised router, malicious proxy) can downgrade a connection to plain HTTP and read or modify traffic in transit — session cookies, auth tokens, form submissions. Without HSTS, even a site that normally serves HTTPS can be stripped to HTTP on the very first request (SSL-stripping), because the browser doesn't yet know to refuse HTTP for that domain.

### Where to look in the code
- Server/reverse-proxy config: is there an HTTP→HTTPS redirect, and is it applied *before* any sensitive data leaves the server?
- Response headers: absence of `Strict-Transport-Security`.
- Mixed content: HTTPS pages loading scripts/images/iframes over plain `http://`.

### How to reproduce
```bash
curl -I http://yoursite.com
# check whether it redirects to https, and whether Strict-Transport-Security is present on the https response
curl -I https://yoursite.com | grep -i strict-transport-security
```

### Fix
Force HTTPS everywhere and set HSTS on every response:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```
Consider HSTS preload once the domain and all subdomains are HTTPS-only permanently.

---

## Content-Security-Policy (CSP)

### How the attacker exploits it
CSP is the last line of defense against XSS: even if an attacker manages to inject a `<script>` tag or an inline event handler, a correctly configured CSP blocks the browser from executing it. Without CSP (or with an overly permissive one, e.g. `script-src *` or heavy use of `'unsafe-inline'`), any successful injection executes with full run of the page — session theft, credential phishing overlays, keylogging.

### Where to look in the code
- Missing `Content-Security-Policy` header entirely.
- A CSP that allows `'unsafe-inline'` or `'unsafe-eval'` for `script-src` without a documented reason.
- A CSP that allows `*` or overly broad wildcards for `script-src`/`connect-src`.

### How to reproduce
```bash
curl -I https://yoursite.com | grep -i content-security-policy
```
Then attempt a benign injection (`<script>alert(1)</script>`) in any field that gets reflected/rendered, and check whether the browser console reports a CSP violation or actually executes it.

### Fix
```
Content-Security-Policy: default-src 'self'; script-src 'self'
```
**Start restrictive and loosen only as needed — never the other way around.** Add specific exceptions (a CDN origin, an inline style hash) only when something legitimately breaks, and prefer nonces/hashes over `'unsafe-inline'`. Treat CSP as a safety net behind proper output escaping/sanitization, not a replacement for it.

---

## The other four security headers

### How the attacker exploits it
Each missing header removes a specific browser-enforced protection:
- No `X-Frame-Options` → the site can be embedded in an invisible `<iframe>` on an attacker's page (clickjacking) — the victim thinks they're clicking a game/button but is actually clicking "Confirm transfer" on your site.
- No `X-Content-Type-Options` → the browser may MIME-sniff a file the app labeled as harmless (e.g. an uploaded `.txt`) and execute it as HTML/JS.
- No/weak `Referrer-Policy` → full URLs (including query strings, which may contain tokens or IDs) leak to third-party sites via the `Referer` header when users click outbound links.
- No `Permissions-Policy` → embedded or compromised third-party scripts can request camera, microphone, or geolocation access the app never needed.

### Where to look in the code
- Server/framework config (`helmet()` in Express, middleware in Next.js, response header config in the reverse proxy) — check which headers it actually sets versus leaves at framework defaults.

### How to reproduce
```bash
curl -I https://yoursite.com
```
Check for the presence and value of each header below.

### Fix
Set all of these on every response:
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

---

## Cookies

### How the attacker exploits it
A cookie without `HttpOnly` is readable by any JavaScript running on the page — so a single successful XSS immediately yields the session token. Without `Secure`, the cookie can be sent over plain HTTP if the attacker manages a downgrade. Without a `SameSite` attribute, the cookie is sent along with cross-site requests, enabling CSRF (an attacker's page silently makes an authenticated request on the victim's behalf).

### Where to look in the code
- Cookie-setting code (`res.cookie(...)`, session middleware config, auth library config) — check the flags passed.

### How to reproduce
Inspect `Set-Cookie` in the response headers (DevTools → Network, or `curl -I -v`) for the session/auth cookie and confirm the flags present.

### Fix
```
Set-Cookie: session=...; HttpOnly; Secure; SameSite=Lax
```
Use `SameSite=Strict` when the cookie never needs to be sent from a cross-site context (no embeds, no third-party redirects into an authenticated page); `Lax` otherwise. Never store tokens meant to be read by JS (e.g. a refresh token) anywhere but an `HttpOnly` cookie — never in `localStorage`.

---

## CORS

### How the attacker exploits it
CORS decides whether a page on another origin may **read** a response in the browser. Separate the cases:

- **`Access-Control-Allow-Origin: *` without credentials.** Browsers refuse `*` for requests made with credentials (`credentials: 'include'`), so the victim's cookies cannot be used to read the response. The risk is only a response that returns sensitive data **without** any credential (e.g. trusted by network location, or data that should not be public). For truly public data, `*` is fine.
- **Reflected `Origin` + `Access-Control-Allow-Credentials: true`.** The dangerous case: home-rolled logic echoes whatever `Origin` arrives, so any site can make a cookie-authenticated request and read the victim's data. Same for a loose allowlist match (suffix/regex like `evil-example.com`, or `null`).
- **API authenticated by bearer token in a header.** The browser does not attach that token on its own, so another site cannot ride the victim's session through CORS; a permissive `*` there is usually not a finding unless the token is also accepted from a cookie.
- **CSRF is a different problem.** CORS does not stop a cross-site form or simple request from being **sent** with cookies; state-changing cookie-authenticated endpoints need `SameSite`, a CSRF token or an `Origin` check regardless of CORS.

### Where to look in the code
- CORS middleware/config that reflects the request `Origin` (e.g. `origin: true`, a callback returning the input) together with `credentials: true`.
- Allowlist checks with `endsWith`, `includes`, unanchored regex, or that accept `null`.
- `origin: '*'` on a route that returns non-public data without requiring a credential.
- Cookie-authenticated state-changing routes with no CSRF defense.

### How to reproduce
```bash
# local or staging instance
curl -s -D - -o /dev/null http://localhost:3000/api/me \
  -H "Origin: https://evil.example" -H "Cookie: <test-user session>"
```
A finding needs `Access-Control-Allow-Origin: https://evil.example` **and** `Access-Control-Allow-Credentials: true` on a response with the test user's data — or `*` on sensitive data served without credentials. `*` alone on a cookie-authenticated route is not readable cross-site.

### Fix
- Allow only exact, known origins (production, staging, local dev); never reflect an arbitrary `Origin` and never use substring/suffix matching.
- Send `Access-Control-Allow-Credentials: true` only with one specific allowed origin, and add `Vary: Origin`.
- Use `*` only for genuinely public, credential-free responses.
- Protect cookie-authenticated mutations against CSRF independently of CORS.

---

## Webhooks

### How the attacker exploits it
A webhook endpoint (Stripe, payment provider, GitHub, etc.) that doesn't verify the sender's signature will accept forged events from anyone who can guess the URL — fake "payment succeeded" events, fake account events, arbitrary data injection.

### Where to look in the code
- Webhook handlers that parse the body and act on it without calling the provider's signature-verification function (e.g. `stripe.webhooks.constructEvent`).

### Fix
Always verify the provider's signature header (e.g. `Stripe-Signature`) against the raw request body before trusting any webhook payload.
