# Rate Limiting & Abuse Prevention

## Missing Rate Limits on Sensitive Endpoints

Every one of these endpoints needs rate limiting. AI assistants almost never add it:

- **Auth endpoints** — login, register, password reset, OTP verification, magic link. Without limits, attackers can brute-force passwords or enumerate accounts.
- **AI API calls** — Any endpoint that calls OpenAI, Anthropic, or similar. A single user can drain your entire monthly budget in minutes.
- **Email / SMS sending** — Attackers can use your app as a spam relay.
- **File processing** — Upload, resize, convert. CPU-intensive operations without limits enable denial-of-service.
- **Webhook-like endpoints** — Anything accepting external input at scale.

### How the attacker exploits it

- Scripts a brute-force or credential-stuffing loop against `/login`, `/register`, `/reset-password`, `/verify-otp`, or `/magic-link` with no backoff, since nothing throttles repeated attempts.
- Hammers an AI-backed endpoint (chat, generation, summarization) in a tight loop to run up the victim's OpenAI/Anthropic bill or exhaust a shared quota.
- Uses an email/SMS-sending endpoint (invites, notifications, "resend code") as a free spam relay.
- Sends a flood of upload/resize/convert requests to burn CPU and force a denial-of-service.
- Floods any endpoint that accepts bulk external input (webhook receivers, public form submissions) with no per-source cap.

### Where to look in the code

- Auth routes (`/login`, `/register`, `/reset-password`, `/otp`, `/magic-link`) for any rate-limiting middleware or its absence.
- AI proxy routes/handlers that call an LLM provider.
- Mail/SMS sending routes (invite, resend-code, contact-form, notification triggers).
- Upload/processing routes (image resize, file conversion, PDF generation).
- Any route accepting third-party or public input at scale.

### How to reproduce

- First read the code and edge config for a limiter on the route. To confirm behavior, send a small bounded number of requests just above the configured limit to a local or disposable staging instance with the provider mocked, and check for `429`.
- Never measure this against production or a real paid provider; an unknown edge limit is `needs_validation`, not an absence.

### Fix

Add rate limiting at the endpoint (see Implementation Pattern below) using a per-IP and per-user combined strategy, tuned per endpoint sensitivity (auth stricter than general API traffic).

## Don't Store Rate Limits in Public Tables

If rate limit counters live in a Supabase public table, users can reset their own counters via the REST API.

### How the attacker exploits it

- Reads their own rate-limit counter row through the PostgREST-exposed public table (via the `anon`/`authenticated` key) and issues a `DELETE` or `UPDATE` against it, resetting their own limit and bypassing throttling entirely.

### Where to look in the code

- Any table named like `rate_limits`, `request_counts`, `login_attempts` that lives in the Supabase `public` schema and is queried/mutated via the client-side Supabase SDK.
- Row Level Security policies on that table — if the counter can be read or written by `authenticated`/`anon` roles, it's exploitable.

### How to reproduce

- With a normal user's anon/auth key, call the Supabase REST endpoint for the rate-limit table directly (e.g., `PATCH`/`DELETE` on `/rest/v1/rate_limits?user_id=eq.<self>`) and confirm the counter can be modified or cleared.

### Fix

Use one of:

- **Upstash Redis** — Serverless Redis with built-in rate limiting primitives
- **Private schema table** — Not exposed via PostgREST
- **Middleware-level limiting** — At the edge or API gateway
- **In-memory stores** — For single-server deployments (Redis for multi-server)

## Combine Per-IP and Per-User Limiting

- IP-only limits are defeated by rotating IPs (trivial with VPNs or botnets)
- User-only limits are defeated by creating new accounts
- Apply both as independent limits (one counter per IP, one per user); a single key combining IP+user resets whenever either part changes

### How the attacker exploits it

- If only IP-based limiting is in place, rotates IPs via VPN or a botnet to reset the counter on each request.
- If only user-based limiting is in place, creates disposable new accounts (email aliasing, throwaway signup) to reset the counter each time.

### Where to look in the code

- Rate-limiting logic that keys solely on `req.ip` or solely on `userId`, or on a single combined `ip+userId` key, instead of two independent limits.
- An IP key read from raw `x-forwarded-for` (or the first entry of it) instead of the trusted proxy's header — the client can set any value and get a fresh counter per request.

### How to reproduce

- Simulate requests from multiple IPs against a user-only-limited endpoint (or multiple fresh accounts against an IP-only-limited endpoint) and confirm the limit resets each time.

### Fix

Apply two independent limits — one keyed by client IP, one keyed by user ID — and reject when either is exceeded. Do not key a single limiter on the `IP+userId` pair: rotating IPs or creating accounts gives a fresh counter each time.

## Billing Protection

- Set billing alerts on every cloud provider (AWS, GCP, Vercel, etc.)
- Set **hard spending caps** on AI API providers (OpenAI, Anthropic)
- Use per-user usage quotas with hard limits, not just soft warnings
- Monitor for anomalous usage patterns (sudden spikes, requests at odd hours)

### How the attacker exploits it

- Exploits an unthrottled AI or cloud-resource endpoint to generate massive, unexpected provider bills before anyone notices, since there are no hard caps or anomaly alerts to stop it early.

### Where to look in the code

- Provider dashboards/config for AWS, GCP, Vercel, OpenAI, Anthropic — check whether billing alerts and hard spending caps are actually configured (not just "available").
- Application-level usage tracking — is there any per-user quota enforcement, or does every request just pass through unmetered?

### How to reproduce

- Do not generate paid traffic. Read the per-user quota code and run it locally with a mocked provider and a tiny quota (e.g. 3) to confirm the 4th call is refused; provider caps and alerts are checked by the account owner in the provider console.

### Fix

- Set billing alerts on every cloud provider (AWS, GCP, Vercel, etc.)
- Set hard spending caps on AI API providers (OpenAI, Anthropic)
- Use per-user usage quotas with hard limits, not just soft warnings
- Monitor for anomalous usage patterns (sudden spikes, requests at odd hours)

## Implementation Pattern

```typescript
// Example: rate limiting with Upstash Redis
import { Ratelimit } from '@upstash/ratelimit';
import { Redis } from '@upstash/redis';

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(10, '1 m'), // 10 requests per minute
});

export async function POST(request: Request) {
  // Client IP from the trusted proxy only. Raw `x-forwarded-for` is client-controlled
  // and spoofable. On Cloudflare (Workers or proxied origin) use CF-Connecting-IP,
  // and on an origin accept it only from Cloudflare IP ranges. Elsewhere use the
  // platform's documented client-IP source, never the raw header.
  const ip = request.headers.get('cf-connecting-ip');
  if (!ip) return new Response('Bad request', { status: 400 });
  const { success } = await ratelimit.limit(`ip:${ip}`);
  if (!success) {
    return new Response('Too many requests', { status: 429 });
  }
  // ... handle request
}
```

## Bot Protection Is Not Rate Limiting

Rate limiting counts requests per origin. Bot protection decides whether the origin is a human. They solve different problems and neither substitutes the other: a distributed bot net stays under every per-IP threshold while still automating the abuse at full scale.

Endpoints that need bot protection **on top of** rate limiting:

- **Signup** — fake account farming, disposable-email churn, seeding accounts to later reset per-user limits.
- **Login** — credential stuffing spread across thousands of residential IPs, each well under the throttle.
- **Public forms** — contact, lead capture, newsletter, support ticket. Spam and lead-list poisoning.
- **Checkout / payment** — card testing (BIN attacks): many low-value authorization attempts to find live cards.
- **Content endpoints** — scraping the catalog, price list, or user-generated content at scale.
- **Anything that costs money per call** — AI generation, SMS, email.

### How the attacker exploits it

- Runs credential stuffing from a residential proxy pool: each IP sends two or three requests, far below the limit, while the campaign as a whole tries millions of credentials.
- Automates signup to farm accounts, then uses those accounts to reset per-user quotas at will — defeating the per-user half of a correctly built limiter.
- Scripts card testing against the payment endpoint, staying under the threshold per source, and reads the success/failure difference to harvest live card numbers.
- Scrapes the entire catalog through the public API with a headless browser that passes as a normal client.

### Where to look in the code

- Signup, login, password-reset and public form handlers — is there ANY human-verification challenge, or only a counter?
- The CDN/edge config (Cloudflare, Vercel, AWS WAF) — is bot management actually enabled **for these routes**, or merely available on the plan?
- Client-side-only defenses: a honeypot field or a challenge validated in the browser and never re-checked on the server is not protection.
- Whether the challenge token is verified **server-side** against the provider's API on every submission.

### How to reproduce

- Against a local or staging instance, replay the endpoint with `curl` — no browser, no JS execution. Success shows the app does not verify a challenge server-side; it does not prove the deployed edge has no bot management. Missing anti-bot is hardening unless a concrete abuse (spend, spam, account farming) is demonstrated.
- Submit the form with the challenge field removed, or set to an arbitrary string, and confirm it is still accepted.
- Distribute N requests across N source IPs and confirm no aggregate detection triggers.

### Fix

- Add a challenge on the abusable endpoints: **Cloudflare Turnstile** (invisible, privacy-preserving), hCaptcha, or reCAPTCHA v3.
- **Verify the token server-side** on every submission — a token the server never validates is decoration.
- Enable bot management at the edge so the traffic is dropped before it reaches your origin and your provider bill.
- For signup specifically, combine with email verification and disposable-domain blocking.
- Keep the rate limiting as well. The two layers catch different attackers; neither replaces the other.
