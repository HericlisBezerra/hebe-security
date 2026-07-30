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
`Access-Control-Allow-Origin: *` on an authenticated endpoint means **any website on the internet** can make a browser-side request to your API using the victim's own cookies/credentials (if credentials are involved) or can simply read the response if the endpoint returns sensitive data without requiring credentials at all. An attacker only needs to lure the victim to a malicious page — the victim's browser does the rest.

### Where to look in the code
- CORS middleware/config: `cors()` called with no options (defaults to permissive in some setups), or explicitly configured with `origin: '*'`.
- Any endpoint that returns authenticated/personal data and doesn't restrict `Access-Control-Allow-Origin` to known origins.
- `Access-Control-Allow-Credentials: true` paired with a wildcard or reflected origin — this combination should never validate in a correctly implemented server, but home-rolled CORS logic sometimes reflects whatever `Origin` header the client sent back as the allowed origin, which defeats the purpose entirely.

### How to reproduce
```bash
curl -I -X OPTIONS https://api.example.com/api/me \
  -H "Origin: https://evil.example" \
  -H "Access-Control-Request-Method: GET"
# check the Access-Control-Allow-Origin value in the response
```
If it echoes back `https://evil.example` or returns `*` on an authenticated route, CORS is misconfigured.

### Fix
- **Never** use `Access-Control-Allow-Origin: *` on an endpoint that requires authentication.
- Whitelist only your own known domains (production domain, staging domain, local dev origin) — never reflect an arbitrary `Origin` header back as allowed.
- If `Access-Control-Allow-Credentials: true` is needed, it **must** be paired with one specific, explicitly allowed origin — never a wildcard, and never a naively reflected origin.

---

## Webhooks

### How the attacker exploits it
A webhook endpoint (Stripe, payment provider, GitHub, etc.) that doesn't verify the sender's signature will accept forged events from anyone who can guess the URL — fake "payment succeeded" events, fake account events, arbitrary data injection.

### Where to look in the code
- Webhook handlers that parse the body and act on it without calling the provider's signature-verification function (e.g. `stripe.webhooks.constructEvent`).

### Fix
Always verify the provider's signature header (e.g. `Stripe-Signature`) against the raw request body before trusting any webhook payload.
